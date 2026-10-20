"""Talking to the registry: the `GET /v0/services` host list (cached 24 h) and `POST /v0/check`.

Standard-library `urllib`, on purpose: a test suite often mocks `requests`/`httpx` (responses,
pytest-httpx, respx), and the plugin runs while those mocks are still active. Every failure is
quiet (`None`, reason in `last_error`) and opens a breaker for the rest of the session; identical
checks are answered from memory; a session sends at most `max_checks` checks and spends at most
`budget_s` seconds on the network, so a red suite never gets much slower.
"""

import ipaddress
import json
import os
import threading
import time
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from agentfacts.schema.registry import match_host

TIMEOUT_S = 2.0  # spec 07
CACHE_TTL_S = 24 * 3600
MAX_RESPONSE_BYTES = 1_000_000
LOCAL_SUFFIXES = (
    ".local",
    ".localhost",
    ".test",
    ".internal",
    ".example",
    ".invalid",
    ".lan",
    ".home.arpa",
)


def default_cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME", "").strip()
    return (Path(base) if base else Path.home() / ".cache") / "agentfacts"


def is_local(host: str) -> bool:
    """Hosts no registry can know: test servers, LAN names, IP addresses."""
    if "." not in host or host == "localhost" or host.endswith(LOCAL_SUFFIXES):
        return True
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def hosts_of(answer: Any) -> frozenset[str]:
    """Hosts from a `GET /v0/services` answer: `{"services": [...]}`, a bare list, or a mapping."""
    services = answer.get("services", answer) if isinstance(answer, Mapping) else answer
    entries = services.values() if isinstance(services, Mapping) else services
    found: set[str] = set()
    for entry in entries if isinstance(entries, Iterable) else ():
        hosts = entry.get("hosts") if isinstance(entry, Mapping) else None
        if isinstance(hosts, list):
            found.update(h.strip().lower() for h in hosts if isinstance(h, str) and h.strip())
    return frozenset(found)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None  # a 3xx becomes an HTTPError: the registry never moves the request elsewhere


class Client:
    def __init__(
        self,
        endpoint: str,
        user_agent: str,
        *,
        timeout: float = TIMEOUT_S,
        cache_dir: Path | None = None,
        offline: bool = False,
        snapshot: Path | None = None,
        max_checks: int = 20,
        budget_s: float = 10.0,
        clock: Callable[[], float] = time.time,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.user_agent = user_agent
        self.timeout = timeout
        self.cache_dir = cache_dir or default_cache_dir()
        self.offline = offline
        self.snapshot_root = snapshot
        self.max_checks = max_checks
        self.budget_s = budget_s
        self.clock = clock
        self.last_error: str | None = None
        self._hosts: frozenset[str] | None = None
        self._snapshot: Any = None
        self._memo: dict[str, dict[str, Any]] = {}
        self._checks = 0
        self._spent = 0.0
        self._opener = urllib.request.build_opener(_NoRedirect())
        parts = urlsplit(self.endpoint)
        self._broken = offline is False and not (
            parts.scheme in ("http", "https") and parts.hostname
        )
        if self._broken:
            self.last_error = f"invalid endpoint {endpoint!r}"

    # ── public ──────────────────────────────────────────────────────────────────────────────────

    def registered_host(self, host: str | None) -> str | None:
        """The registry host to report `host` under, or None (then nothing may be sent)."""
        if not host:
            return None
        host = host.lower()
        if is_local(host):
            return None
        return match_host(host, self._known_hosts())

    def check(self, payload: Mapping[str, Any]) -> dict[str, Any] | None:
        """The `POST /v0/check` answer for `payload`, or None on any failure or limit."""
        key = json.dumps(payload, sort_keys=True)
        if key in self._memo:
            return self._memo[key]
        if self.offline:
            try:
                answer = self._offline().check(payload)
            except Exception as exc:  # a malformed snapshot is "no answer", like a bad server
                return self._fail(f"offline snapshot: {type(exc).__name__}: {exc}")
        else:
            if self._checks >= self.max_checks:
                self.last_error = f"check limit of {self.max_checks} per session reached"
                return None
            self._checks += 1
            answer = self._request("POST", "/v0/check", payload)
            if not isinstance(answer, dict):
                return self._fail("answer is not a JSON object") if answer is not None else None
        self._memo[key] = answer
        return answer

    # ── internals ───────────────────────────────────────────────────────────────────────────────

    def _offline(self) -> Any:
        if self._snapshot is None:
            from agentfacts.client.offline import Snapshot

            self._snapshot = Snapshot.load(self.snapshot_root)
        return self._snapshot

    def _known_hosts(self) -> frozenset[str]:
        if self._hosts is None:
            if self.offline:
                self._hosts = self._offline().hosts
            else:
                self._hosts = self._cached_hosts()
                if self._hosts is None:
                    answer = self._request("GET", "/v0/services")
                    self._hosts = hosts_of(answer) if answer is not None else frozenset()
                    if answer is not None:
                        self._write_cache(self._hosts)
        return self._hosts

    @property
    def _cache_file(self) -> Path:
        return self.cache_dir / "services.json"

    def _cached_hosts(self) -> frozenset[str] | None:
        try:
            data = json.loads(self._cache_file.read_text(encoding="utf-8"))
            age = self.clock() - float(data["fetched_at"])
            if data["endpoint"] != self.endpoint or not 0 <= age < CACHE_TTL_S:
                return None
            hosts = data["hosts"]
            if not isinstance(hosts, list) or not all(isinstance(h, str) for h in hosts):
                return None
            return frozenset(hosts)
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _write_cache(self, hosts: frozenset[str]) -> None:
        data = {"endpoint": self.endpoint, "fetched_at": self.clock(), "hosts": sorted(hosts)}
        tmp = self._cache_file.with_name(f"services.json.{os.getpid()}.tmp")
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(data), encoding="utf-8")
            os.replace(tmp, self._cache_file)
        except OSError:
            pass  # a read-only home still works, with an in-memory list

    def _fail(self, reason: str) -> None:
        self._broken = True
        self.last_error = reason
        return None

    def _request(self, method: str, path: str, body: Any = None) -> Any:
        if self._broken:
            return None
        if self._spent >= self.budget_s:
            self.last_error = f"network time budget of {self.budget_s} s spent"
            return None
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"User-Agent": self.user_agent, "Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.endpoint + path, data, headers, method=method)
        box: dict[str, Any] = {}

        def fetch() -> None:
            try:
                with self._opener.open(request, timeout=self.timeout) as response:
                    box["raw"] = response.read(MAX_RESPONSE_BYTES + 1)
            except Exception as exc:  # network, TLS, HTTP status: all mean "no answer"
                box["error"] = exc

        # urllib's timeout bounds each socket operation, not the request: a server dripping one
        # byte a second would never trip it. The thread gives a hard deadline; a straggler dies
        # with the process (daemon) and the breaker stops any further request.
        worker = threading.Thread(target=fetch, name="agentfacts-request", daemon=True)
        started = time.monotonic()
        worker.start()
        worker.join(self.timeout)
        self._spent += time.monotonic() - started
        if worker.is_alive():
            return self._fail(f"{method} {path}: no complete answer within {self.timeout} s")
        if "error" in box:
            exc = box["error"]
            return self._fail(f"{method} {path}: {type(exc).__name__}: {exc}")
        raw = box["raw"]
        if len(raw) > MAX_RESPONSE_BYTES:
            return self._fail(f"{method} {path}: answer larger than {MAX_RESPONSE_BYTES} bytes")
        try:
            return json.loads(raw)
        except ValueError as exc:
            return self._fail(f"{method} {path}: not JSON: {exc}")
