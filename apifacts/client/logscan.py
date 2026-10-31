"""Failed HTTP calls in a CI log, for `apifacts scan` and the GitHub Action (spec 07).

An agent fixing red CI reads the failing step's log, not a test report: this module finds the HTTP
errors that common clients print there and turns each into a filtered `Signal` (same filters as the
plugin and `apifacts check`: scheme, host and path only; the body excerpt redacted).

Formats, each a real message shape, not a guess at one:

- python requests `raise_for_status()`: ``401 Client Error: Unauthorized for url: https://…``
- httpx `raise_for_status()`: ``Client error '404 Not Found' for url 'https://…'``
- httpx's INFO log, which the OpenAI and Anthropic SDKs inherit:
  ``HTTP Request: POST https://… "HTTP/1.1 401 Unauthorized"``, with the SDK's
  ``Error code: 401 - {…}`` a few lines below as the body
- stripe-python's logfmt log (``message='Stripe API response' path=… response_code=…``)
- gh CLI: ``HTTP 404: Not Found (https://api.github.com/…)``; the message is the body
- axios: ``Request failed with status code 401`` + the `config` dump that Node prints below it
  (`method`, `url`, `baseURL`); ky and ofetch print method and URL on the line itself
- curl ``-f``: ``curl: (22) The requested URL returned error: 404``, the URL from the `-v` request
  lines or from the echoed command above it; ``--fail-with-body`` prints the body right before

The method: the server refuses a URL with a path and no method (spec 03), and a guessed method would
be stored as an observation under the wrong template and count toward a quorum. So `method` is set
only when the log states it (an explicit method, curl's own defaults on a visible command line);
otherwise it stays None and the caller decides (`apifacts scan` asks without reporting, see
`cli_scan`). Bodies: only text the client prints as the response (never axios `config.data`, which
is the request body).

Our own output is skipped: the "Known facts" section (pytest plugin, `apifacts check`, a previous
scan) and `::warning title=apifacts` lines are never reported again.
"""

import re
import shlex
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urljoin

from apifacts.client.render import TITLE
from apifacts.client.request import HTTP_METHODS, Signal, make_signal

MAX_LOG_BYTES = 2_000_000  # the tail of a log: the failure is at the end, the setup noise first
AXIOS_WINDOW = 150  # lines of the `config` dump Node prints under an AxiosError
CURL_WINDOW = 60  # lines above `curl: (22)` that may hold its -v request or command line
SECTION_MAX_LINES = 80  # a "Known facts" section never runs longer (5 facts × a few lines)

_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_GHA_TIME = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z ")  # downloaded job logs
_URL = r"https?://[^\s'\"<>()\[\]{}`]+"
_METHOD = "|".join(sorted(HTTP_METHODS))

_REQUESTS = re.compile(rf"\b([1-5]\d\d) (?:Client|Server) Error: .*? for url: ({_URL})")
_HTTPX = re.compile(r"\b(?:Client|Server) error '([1-5]\d\d)[^']*' for url '(https?://[^']+)'")
_HTTPX_LOG = re.compile(rf"HTTP Request: ({_METHOD}) ({_URL}) \"HTTP/[\d.]+ ([1-5]\d\d)\b")
_SDK_ERROR = re.compile(r"\bError code: ([1-5]\d\d) - (.+)$")  # openai/anthropic python SDKs
_STRIPE_RESPONSE = re.compile(rf"Stripe API response'? path=({_URL}) response_code=([1-5]\d\d)")
_STRIPE_REQUEST = re.compile(rf"Request to Stripe api'? method=(\w+) url=({_URL})")
_STRIPE_ERROR = re.compile(r"Stripe API error received'? (.+)$")
_GH = re.compile(rf"\bHTTP ([1-5]\d\d): (.*?) ?\(({_URL})\)")
_KY = re.compile(rf"Request failed with status code ([1-5]\d\d)[^:\n]*: ({_METHOD}) ({_URL})")
_OFETCH = re.compile(rf"\[({_METHOD})\] \"({_URL})\": ([1-5]\d\d)\b")
_AXIOS = re.compile(r"Request failed with status code ([1-5]\d\d)\b")
_AXIOS_URL = re.compile(r"^\s*url: ['\"]([^'\"]+)['\"]")
_AXIOS_BASE = re.compile(rf"^\s*baseURL: ['\"]({_URL})['\"]")
_AXIOS_METHOD = re.compile(r"^\s*method: ['\"](\w+)['\"]")
_AXIOS_RESPONSE = re.compile(r"^\s*response: ")
_AXIOS_DATA = re.compile(r"^\s*data: (\{.*\}|'.*'|\".*\"),?$")
_CURL_FAIL = re.compile(r"curl: \(22\) The requested URL returned error: ([1-5]\d\d)\b")
_CURL_VERBOSE_REQUEST = re.compile(rf"^> ({_METHOD}) (/\S*) HTTP/")
_CURL_VERBOSE_HOST = re.compile(r"^> [Hh]ost: ([A-Za-z0-9.-]+)(?::(\d+))?\s*$")
_CURL_PORT_80 = re.compile(r"^\* (?:Connected to|Trying) .* port 80\b")
_BARE_URL = re.compile(_URL)
_PYTEST_E = re.compile(r"^E\s+")  # pytest's error lines


@dataclass(frozen=True)
class Failure:
    """One failed call as the log shows it. `url` is raw (it may hold a query): never print it."""

    url: str
    status: int
    method: str | None
    body: str | None
    line: int  # 1-based, in the scanned text
    source: str  # which format matched: requests, httpx, gh, axios, curl, …


@dataclass(frozen=True)
class Found:
    """A distinct failure after the request filters: what may be shown and sent."""

    signal: Signal
    line: int
    source: str


def clean_lines(text: str) -> list[str]:
    """Lines without colour codes and without the timestamps of a downloaded job log."""
    return [_GHA_TIME.sub("", _ANSI.sub("", line)) for line in text.splitlines()]


def _own_output(lines: list[str]) -> set[int]:
    """Indexes of lines inside a "Known facts" section or carrying our own annotations."""
    skip: set[int] = set()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("::") and "title=apifacts" in line:
            skip.add(i)
        elif TITLE in line:
            skip.add(i)
            j = i + 1
            while j < len(lines) and j - i <= SECTION_MAX_LINES:
                stripped = lines[j].strip()
                if not stripped or stripped[0] in "─=_":
                    break
                skip.add(j)
                j += 1
            i = j
            continue
        i += 1
    return skip


def _trim_url(url: str) -> str:
    return url.rstrip(".,;:!?")


def _json_line(line: str) -> str | None:
    """A response body printed on its own line: JSON, starting with `{` or `[`."""
    text = _PYTEST_E.sub("", line).strip()
    return text if text[:1] in ("{", "[") else None


def _body_below(lines: list[str], i: int, reach: int = 2) -> str | None:
    for j in range(i + 1, min(i + 1 + reach, len(lines))):
        if (body := _json_line(lines[j])) is not None:
            return body
    return None


def _axios(lines: list[str], i: int, status: int) -> Failure | None:
    """The `config` dump under an AxiosError: method, url (joined to baseURL), response data."""
    url = base = method = body = None
    in_response = False
    for j in range(i + 1, min(i + 1 + AXIOS_WINDOW, len(lines))):
        line = lines[j]
        if _AXIOS.search(line):
            break  # the next error's dump
        if url is None and (m := _AXIOS_URL.match(line)):
            url = m[1]
        elif base is None and (m := _AXIOS_BASE.match(line)):
            base = m[1]
        elif method is None and (m := _AXIOS_METHOD.match(line)):
            method = m[1].upper()
        elif _AXIOS_RESPONSE.match(line):
            in_response = True  # `data:` before this is config.data, the request body
        elif in_response and body is None and (m := _AXIOS_DATA.match(line)):
            body = m[1].strip("'\"") if m[1][0] in "'\"" else m[1]
    if url is None:
        return None
    if not url.startswith(("http://", "https://")):
        if base is None:
            return None
        url = urljoin(base.rstrip("/") + "/", url.lstrip("/"))
    return Failure(url, status, method if method in HTTP_METHODS else None, body, i + 1, "axios")


def _curl_command(text: str) -> tuple[str | None, str | None]:
    """URL and method of an echoed `curl …` line; curl's own rules for the method."""
    try:
        words = shlex.split(text, posix=True)
    except ValueError:
        words = text.split()
    try:
        start = next(k for k, w in enumerate(words) if w == "curl" or w.endswith("/curl"))
    except StopIteration:
        return None, None
    url = method = None
    implied = None
    words = words[start + 1 :]
    for k, word in enumerate(words):
        nxt = words[k + 1] if k + 1 < len(words) else ""
        if word in ("-X", "--request"):
            method = nxt.upper()
        elif word.startswith("-X") and len(word) > 2:
            method = word[2:].upper()
        elif word.startswith("--request="):
            method = word.split("=", 1)[1].upper()
        elif word in ("-I", "--head"):
            implied = "HEAD"
        elif word in ("-T", "--upload-file"):
            implied = implied or "PUT"
        elif word in ("-G", "--get"):
            implied = "GET"
        elif word.split("=", 1)[0] in (
            "-d",
            "--data",
            "--data-raw",
            "--data-binary",
            "--data-urlencode",
            "--data-ascii",
            "-F",
            "--form",
            "--form-string",
            "--json",
        ) or (word.startswith(("-d", "-F")) and len(word) > 2 and not word.startswith("--")):
            implied = implied or "POST"
        elif url is None and _BARE_URL.fullmatch(word.strip("'\"")):
            url = word.strip("'\"")
    if url is None:
        return None, None
    return url, method or implied or "GET"


def _curl(lines: list[str], i: int, status: int, before: str) -> Failure | None:
    """`curl -f` failed at line i: the -v request above it, else the echoed command, else a URL
    on the same or previous line (method unknown then)."""
    floor = max(0, i - CURL_WINDOW)
    for j in range(i - 1, floor - 1, -1):
        if _CURL_FAIL.search(lines[j]):
            floor = j + 1  # the previous curl's lines are not ours
            break
    url = method = None
    path = host = port = None
    plain = False
    for j in range(floor, i):
        line = lines[j]
        if m := _CURL_VERBOSE_REQUEST.match(line):
            method, path, host, port = m[1], m[2], None, None
        elif path is not None and host is None and (m := _CURL_VERBOSE_HOST.match(line)):
            host, port = m[1], m[2]
        elif _CURL_PORT_80.match(line):
            plain = True
    if path is not None and host is not None:
        scheme = "http" if plain or port == "80" else "https"
        url = f"{scheme}://{host}{path}"
    else:
        method = None
        for j in range(i - 1, floor - 1, -1):
            joined = lines[j]
            k = j - 1
            while k >= floor and lines[k].rstrip().endswith("\\"):  # a wrapped command line
                joined = lines[k].rstrip()[:-1] + " " + joined
                k -= 1
            if "curl" in joined:
                url, method = _curl_command(joined.lstrip("+ $"))
                if url is not None:
                    break
        previous = lines[i - 1] if i > 0 else ""
        if url is None and not before.strip() and _json_line(previous) is None:
            # Not a body (whose documentation_url is not the call): a URL the script printed.
            if m := _BARE_URL.search(previous):
                url = _trim_url(m[0])
    if url is None:
        return None
    body = before.strip() or (_json_line(lines[i - 1]) if i > 0 else None)
    return Failure(url, status, method, body or None, i + 1, "curl")


def failures(text: str) -> list[Failure]:
    """Every failed call (status ≥ 400) the known formats show, in log order, duplicates kept."""
    lines = clean_lines(text)
    skip = _own_output(lines)
    found: list[Failure] = []
    for i, line in enumerate(lines):
        if i in skip:
            continue
        found.extend(_line_failures(lines, i, line))
    return [f for f in found if 400 <= f.status <= 599]


def _line_failures(lines: list[str], i: int, line: str) -> Iterable[Failure]:
    n = i + 1
    for m in _REQUESTS.finditer(line):
        yield Failure(_trim_url(m[2]), int(m[1]), None, _body_below(lines, i), n, "requests")
    for m in _HTTPX.finditer(line):
        yield Failure(m[2], int(m[1]), None, _body_below(lines, i), n, "httpx")
    if m := _HTTPX_LOG.search(line):
        status, body = int(m[3]), None
        for j in range(i + 1, min(i + 30, len(lines))):
            if _HTTPX_LOG.search(lines[j]):
                break  # a retry or the next call: its own error line
            if (e := _SDK_ERROR.search(lines[j])) and int(e[1]) == status:
                body = e[2]
                break
        yield Failure(_trim_url(m[2]), status, m[1], body, n, "httpx-log")
    if m := _STRIPE_RESPONSE.search(line):
        url, method, body = m[1], None, None
        for j in range(i - 1, max(-1, i - 10), -1):
            if (r := _STRIPE_REQUEST.search(lines[j])) and r[2] == url:
                method = r[1].upper()
                break
        for j in range(i + 1, min(i + 4, len(lines))):
            if e := _STRIPE_ERROR.search(lines[j]):
                body = e[1]
                break
        yield Failure(url, int(m[2]), method, body, n, "stripe-log")
    for m in _GH.finditer(line):
        yield Failure(_trim_url(m[3]), int(m[1]), None, m[2].strip() or None, n, "gh")
    if m := _KY.search(line):
        yield Failure(_trim_url(m[3]), int(m[1]), m[2], _body_below(lines, i), n, "ky")
    elif m := _AXIOS.search(line):
        if (found := _axios(lines, i, int(m[1]))) is not None:
            yield found
    if m := _OFETCH.search(line):
        yield Failure(_trim_url(m[2]), int(m[3]), m[1], _body_below(lines, i), n, "ofetch")
    if m := _CURL_FAIL.search(line):
        if (found := _curl(lines, i, int(m[1]), line[: m.start()])) is not None:
            yield found


def distinct(found: Iterable[Failure]) -> list[Found]:
    """Filtered and deduplicated: one per (method, scrubbed URL, status), first body kept. A call
    seen without a method is dropped when the same URL and status also appear with one."""
    out: dict[tuple[str | None, str, int], Found] = {}
    for failure in found:
        signal = make_signal(
            failure.url, method=failure.method, status=failure.status, body=failure.body
        )
        if signal is None or "://" not in signal.url:
            continue
        key = (signal.method, signal.url, failure.status)
        if key not in out:
            out[key] = Found(signal, failure.line, failure.source)
    with_method = {(url, status) for method, url, status in out if method is not None}
    return [
        found
        for (method, url, status), found in out.items()
        if method is not None or (url, status) not in with_method
    ]


def scan(text: str) -> list[Found]:
    return distinct(failures(text))
