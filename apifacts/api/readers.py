"""Who reads apifacts.dev: a count per (UTC day, User-Agent family, path class, status class).

Caddy keeps no access log and uvicorn runs `--no-access-log` (spec 03: no raw IP is ever stored or
logged), so without this nothing tells whether AI crawlers or agents read the site at all. The
middleware keeps only fixed tokens: the family from `FAMILIES`, the class of the path from
`path_class`, the status class. Never the raw User-Agent, the path, the query or the IP — and
the key space is bounded (families × path classes × status classes per day), whatever the traffic.

A User-Agent is a claim: nobody verifies that "ClaudeBot" is Anthropic's (that needs the IP, which
is not kept). Read the numbers as "who says they read us".

Persistence without a schema change: the counters live in memory and are merged into
`<dir>/<YYYY-MM-DD>.json` every few minutes and at shutdown (lifespan). `<dir>` is
`APIFACTS_READERS_DIR`, default `readers/` next to the db (`var/readers/` on the host), like
`own-nets.txt`. The merge holds an exclusive lock on `<dir>/.lock` and replaces the file through
a temp file and `os.replace`, so two processes (or a reader) never see half a file. A failed write
keeps the counts in memory for the next flush.
"""

import json
import os
import re
import sys
import tempfile
import threading
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from starlette.types import ASGIApp, Message, Receive, Scope, Send

try:
    import fcntl
except ImportError:  # Windows: the CLI reads files there, the API never runs there
    fcntl = None  # type: ignore[assignment]

FLUSH_SECONDS = 300
FORMAT = 1

# ── User-Agent → family ─────────────────────────────────────────────────────────────────────────
#
# (family, group, pattern on the lowercased User-Agent). First match wins, so the order matters: a
# vendor's live-fetch agent before its crawler where one name contains the other, every named bot
# before the generic `other-bot`, `other-bot` before `browser` (most bots say "Mozilla/5.0 …
# compatible"). A new family is one row here; the groups are what the digest sums.

AI_AGENT, AI_CRAWLER, SEARCH, SCRIPT, BROWSER, OURS, OTHER = (
    "ai_agent",
    "ai_crawler",
    "search",
    "script",
    "browser",
    "ours",
    "other",
)
GROUPS = (AI_AGENT, AI_CRAWLER, SEARCH, SCRIPT, BROWSER, OURS, OTHER)

FAMILIES: tuple[tuple[str, str, str], ...] = (
    # ours (apifacts/cli_check.py, apifacts/mcp_server.py, plugins/pytest, apifacts/probe)
    ("apifacts-cli", OURS, r"^apifacts-cli/"),
    ("apifacts-mcp", OURS, r"^apifacts-mcp/"),
    ("apifacts-pytest", OURS, r"^apifacts-pytest/"),
    ("apifacts-probe", OURS, r"^apifacts-probe/"),
    ("apifacts-other", OURS, r"^apifacts"),
    # AI agents: one fetch because a person asked the assistant right now
    ("ChatGPT-User", AI_AGENT, r"chatgpt-user"),
    ("Claude-User", AI_AGENT, r"claude-user"),
    ("Perplexity-User", AI_AGENT, r"perplexity-user"),
    ("MistralAI-User", AI_AGENT, r"mistralai-user"),
    ("meta-externalfetcher", AI_AGENT, r"meta-externalfetcher"),
    ("DuckAssistBot", AI_AGENT, r"duckassistbot"),
    # AI crawlers: training sets and AI search indexes
    ("OAI-SearchBot", AI_CRAWLER, r"oai-searchbot"),
    ("GPTBot", AI_CRAWLER, r"gptbot"),
    ("Claude-SearchBot", AI_CRAWLER, r"claude-searchbot"),
    ("ClaudeBot", AI_CRAWLER, r"claudebot"),
    ("anthropic-ai", AI_CRAWLER, r"anthropic-ai"),
    ("PerplexityBot", AI_CRAWLER, r"perplexitybot"),
    (
        "Google-other",
        AI_CRAWLER,
        r"googleother|google-cloudvertexbot|google-extended|google-notebooklm",
    ),
    ("meta-externalagent", AI_CRAWLER, r"meta-externalagent"),
    ("Bytespider", AI_CRAWLER, r"bytespider"),
    ("CCBot", AI_CRAWLER, r"ccbot"),
    ("Amazonbot", AI_CRAWLER, r"amazonbot"),
    ("ExaBot", AI_CRAWLER, r"exabot"),
    ("cohere-ai", AI_CRAWLER, r"cohere-ai|cohere-training-data-crawler"),
    # search engines
    ("Googlebot", SEARCH, r"googlebot|google-inspectiontool|storebot-google"),
    ("Bingbot", SEARCH, r"bingbot|bingpreview|adidxbot"),
    ("Applebot", SEARCH, r"applebot"),
    ("DuckDuckBot", SEARCH, r"duckduckbot"),
    ("YandexBot", SEARCH, r"yandex"),
    # HTTP libraries and command-line tools
    (
        "script",
        SCRIPT,
        r"^(curl|wget|httpie|python-requests|python-httpx|python-urllib|python/|aiohttp|node-fetch"
        r"|undici|node|axios|deno|bun/|go-http-client|okhttp|java/|apache-httpclient|libwww-perl"
        r"|ruby|faraday|guzzlehttp|php|reqwest|postmanruntime|insomnia)",
    ),
    # anything else that calls itself a robot
    (
        "other-bot",
        OTHER,
        r"bot|crawl|spider|slurp|archiver|externalhit|headlesschrome|lighthouse|uptime|monitor",
    ),
    ("browser", BROWSER, r"^mozilla/|^opera/"),
)
UNKNOWN = "unknown"  # no User-Agent at all
UNMATCHED = "other"  # a User-Agent no row knows

_COMPILED = tuple((family, re.compile(pattern)) for family, _, pattern in FAMILIES)
GROUP_OF = {family: group for family, group, _ in FAMILIES} | {UNKNOWN: OTHER, UNMATCHED: OTHER}


def family_of(user_agent: str | None) -> str:
    """User-Agent → one family token of `FAMILIES`, `unknown` (empty) or `other` (no row)."""
    ua = (user_agent or "").strip().lower()[:512]
    if not ua:
        return UNKNOWN
    return next((family for family, pattern in _COMPILED if pattern.search(ua)), UNMATCHED)


def group_of(family: str) -> str:
    """A family read back from an older file that this table no longer has is `other`."""
    return GROUP_OF.get(family, OTHER)


# ── path → class ────────────────────────────────────────────────────────────────────────────────

PATH_CLASSES = (
    "home",
    "registry",
    "service_index",
    "fact_page",
    "llms",
    "robots",
    "sitemap",
    "api_check",
    "api_read",
    "docs",
    "other",
)
_EXACT = {
    "/": "home",
    "/registry": "registry",
    "/llms.txt": "llms",
    "/llms-full.txt": "llms",
    "/robots.txt": "robots",
    "/v0/check": "api_check",
    "/healthz": "api_read",  # a read endpoint of spec 03
    "/docs": "docs",
    "/docs/oauth2-redirect": "docs",
    "/redoc": "docs",
    "/openapi.json": "docs",
}


def path_class(path: str) -> str:
    """The shape of the path (spec 06 routes), never the path: `/<service>` and `/<service>/` →
    service_index, `/<service>/<slug>` → fact_page, whatever the status. A segment with a dot or
    starting with one (favicon.ico, wp-login.php, .env, .well-known) is `other`: no page has one."""
    if path in _EXACT:
        return _EXACT[path]
    if path.startswith("/sitemap"):
        return "sitemap"
    if path.startswith("/v0/"):
        return "api_read"
    parts = path.strip("/").split("/")
    if any(not p or "." in p for p in parts):
        return "other"
    if len(parts) == 1:
        return "service_index"
    if len(parts) == 2:
        return "fact_page"
    return "other"


def status_class(status: int) -> str:
    return f"{status // 100}xx" if 100 <= status < 600 else "other"


STATUS_CLASSES = ("2xx", "3xx", "4xx", "5xx")

# ── counters ────────────────────────────────────────────────────────────────────────────────────

Key = tuple[str, str, str]  # family, path class, status class


class ReaderCounts:
    """In-memory counts per UTC day, flushed into `<directory>/<day>.json`. The middleware counts
    on the event loop, the flush runs in a worker thread: one lock around the counter."""

    def __init__(self, directory: Path | None = None):
        self.directory = directory
        self._lock = threading.Lock()
        self._days: dict[str, Counter[Key]] = {}

    def add(self, day: str, key: Key, n: int = 1) -> None:
        with self._lock:
            self._days.setdefault(day, Counter())[key] += n

    def pending(self) -> dict[str, dict[Key, int]]:
        with self._lock:
            return {day: dict(c) for day, c in self._days.items()}

    def _take(self) -> dict[str, Counter[Key]]:
        with self._lock:
            taken, self._days = self._days, {}
            return taken

    def _give_back(self, days: dict[str, Counter[Key]]) -> None:
        with self._lock:
            for day, counts in days.items():
                self._days.setdefault(day, Counter()).update(counts)

    def flush(self) -> int:
        """Merge every pending day into its file; returns the requests written. Without a
        directory, or when a write fails, the counts stay in memory."""
        if self.directory is None:
            return 0
        taken = self._take()
        failed: dict[str, Counter[Key]] = {}
        written = 0
        for day, counts in sorted(taken.items()):
            try:
                merge_day(self.directory, day, counts)
                written += sum(counts.values())
            except OSError as exc:
                print(f"readers: {self.directory}/{day}.json not written: {exc}", file=sys.stderr)
                failed[day] = counts
        if failed:
            self._give_back(failed)
        return written


# ── files ───────────────────────────────────────────────────────────────────────────────────────


@contextmanager
def _locked(directory: Path) -> Iterator[None]:
    with (directory / ".lock").open("a") as fh:
        if fcntl is not None:
            fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(fh, fcntl.LOCK_UN)


def _parse(doc: object) -> Counter[Key]:
    """`{"counts": {family: {path_class: {status_class: n}}}}` → a Counter; ValueError if the
    shape is not that."""
    if not isinstance(doc, dict) or not isinstance(doc.get("counts"), dict):
        raise ValueError("no counts mapping")
    out: Counter[Key] = Counter()
    for family, by_path in doc["counts"].items():
        if not isinstance(by_path, dict):
            raise ValueError(f"{family}: not a mapping")
        for path, by_status in by_path.items():
            if not isinstance(by_status, dict):
                raise ValueError(f"{family}.{path}: not a mapping")
            for status, n in by_status.items():
                if not isinstance(n, int) or isinstance(n, bool) or n < 0:
                    raise ValueError(f"{family}.{path}.{status}: not a count")
                out[(str(family), str(path), str(status))] += n
    return out


def _render(day: str, counts: Counter[Key]) -> str:
    nested: dict[str, dict[str, dict[str, int]]] = {}
    for (family, path, status), n in sorted(counts.items()):
        if n:
            nested.setdefault(family, {}).setdefault(path, {})[status] = n
    return (
        json.dumps({"format": FORMAT, "day": day, "counts": nested}, indent=1, sort_keys=True)
        + "\n"
    )


def merge_day(directory: Path, day: str, counts: Counter[Key]) -> None:
    """Add `counts` to `<directory>/<day>.json` under the directory lock, atomically. A file that
    does not parse is set aside as `<day>.json.bad` (never overwritten silently, never fatal)."""
    date.fromisoformat(day)  # a day is a date: never a path from elsewhere
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{day}.json"
    with _locked(directory):
        merged: Counter[Key] = Counter()
        if path.is_file():
            try:
                merged = _parse(json.loads(path.read_text(encoding="utf-8")))
            except ValueError as exc:  # JSONDecodeError is a ValueError
                print(f"readers: {path}: {exc}; kept as {path.name}.bad", file=sys.stderr)
                os.replace(path, path.with_name(f"{path.name}.bad"))
        merged.update(counts)
        fd, tmp = tempfile.mkstemp(prefix=f".{day}.", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(_render(day, merged))
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise


@dataclass(frozen=True)
class Readers:
    """Counts summed over some UTC days. `available` = the directory exists."""

    available: bool
    counts: Counter[Key]
    days_found: int = 0
    bad_files: int = 0

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    def by_family(self) -> Counter[str]:
        out: Counter[str] = Counter()
        for (family, _, _), n in self.counts.items():
            out[family] += n
        return out

    def by_group(self) -> Counter[str]:
        out: Counter[str] = Counter()
        for family, n in self.by_family().items():
            out[group_of(family)] += n
        return out

    def paths_of(self, family: str) -> Counter[str]:
        out: Counter[str] = Counter()
        for (f, p, _), n in self.counts.items():
            if f == family:
                out[p] += n
        return out

    def statuses(self, family: str | None = None) -> Counter[str]:
        out: Counter[str] = Counter()
        for (f, _, s), n in self.counts.items():
            if family is None or f == family:
                out[s] += n
        return out


def read_readers(directory: Path, days: Iterable[str]) -> Readers:
    """Read-only: a missing directory is `available=False`; a missing day is zero; a file that
    does not parse is counted in `bad_files` and skipped."""
    if not directory.is_dir():
        return Readers(available=False, counts=Counter())
    counts: Counter[Key] = Counter()
    found = bad = 0
    for day in days:
        path = directory / f"{day}.json"
        if not path.is_file():
            continue
        try:
            counts.update(_parse(json.loads(path.read_text(encoding="utf-8"))))
            found += 1
        except (OSError, ValueError):
            bad += 1
    return Readers(available=True, counts=counts, days_found=found, bad_files=bad)


def readers_dir_from_env(db_path: Path) -> Path:
    return Path(os.environ.get("APIFACTS_READERS_DIR") or db_path.parent / "readers")


# ── middleware ──────────────────────────────────────────────────────────────────────────────────


class ReadersMiddleware:
    """Outermost: it sees what the rate limiter and the size guard answer too. An exception that
    escapes the app is counted 5xx (Starlette's error middleware answers 500 above us)."""

    def __init__(self, app: ASGIApp, counts: ReaderCounts, utcnow: Callable[[], datetime]):
        self.app, self.counts, self.utcnow = app, counts, utcnow

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        status = 0

        async def watched(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, watched)
        except Exception:
            status = status or 500
            raise
        finally:
            if status:  # 0: the client went away before any answer
                self._count(scope, status)

    def _count(self, scope: Scope, status: int) -> None:
        ua = None
        for name, value in scope.get("headers") or ():
            if name == b"user-agent":
                ua = value.decode("latin-1")
                break
        day = self.utcnow().astimezone(UTC).date().isoformat()
        self.counts.add(day, (family_of(ua), path_class(scope["path"]), status_class(status)))
