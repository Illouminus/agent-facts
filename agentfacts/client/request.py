"""The request a client may send to `POST /v0/check`, and the filters that make it safe to send.

Privacy rules (spec 07): no request bodies, headers, query strings or tokens ever leave the machine.
The URL keeps only scheme, host and path (secret-looking path segments replaced); the error body is
redacted here, before truncation to 2 KB, so the server never sees a secret even once.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any
from urllib.parse import unquote, urlsplit, urlunsplit

EXCERPT_BYTES = 2048  # spec 03: body_excerpt kept, 2 KB in
RAW_CHARS = 16_384  # redaction runs on this prefix; output is cut far inside it
REDACTED, ID, EMAIL = "<redacted>", "<id>", "<email>"  # same placeholders as the server (spec 03)

HTTP_METHODS = frozenset({"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"})

_TOKEN_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/_=.:-")

_PEM = re.compile(
    r"-----BEGIN[A-Z0-9 ]*PRIVATE KEY-----.*?(?:-----END[A-Z0-9 ]*PRIVATE KEY-----|\Z)", re.S
)
_URL = re.compile(r"\b[A-Za-z][A-Za-z0-9+.-]{1,15}://[^\s\"'<>]*")
# Vendor token shapes; every branch is anchored so a long run is scanned once.
_SHAPES = re.compile(
    "|".join(
        (
            r"\b(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{8,}",
            r"\bwhsec_[A-Za-z0-9]{8,}",
            r"\b[A-Za-z0-9_]+_secret_[A-Za-z0-9]{6,}",
            r"\bgh[pousr]_[A-Za-z0-9]{20,}",
            r"\bgithub_pat_[A-Za-z0-9_]{20,}",
            r"\bxox[abposr]-[A-Za-z0-9-]{10,}",
            r"\bsk-[A-Za-z0-9_-]{16,}",
            r"\bAIza[0-9A-Za-z_-]{30,}",
            r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
            r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}",
            r"(?<![0-9])[0-9]{6,12}:[A-Za-z0-9_-]{30,}",  # Telegram bot token
            r"\bSG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}",
            r"\bglpat-[A-Za-z0-9_-]{20,}",
            r"\bhf_[A-Za-z0-9]{30,}",
            r"\bnpm_[A-Za-z0-9]{36,}",
        )
    )
)
_AUTH_SCHEME = re.compile(r"\b(Bearer|Basic)(\s+)([A-Za-z0-9._~+/=-]{8,})", re.I)
_STRICT_NAMES = (
    r"api[_-]?key|apikey|access[_-]?token|refresh[_-]?token|auth[_-]?token|id[_-]?token"
    r"|client[_-]?secret|secret[_-]?key|private[_-]?key|password|passwd"
)
# A quoted value runs to its closing quote (it may hold spaces), a bare one to a delimiter.
_NAMED = re.compile(
    rf"(?<![A-Za-z0-9])((?:{_STRICT_NAMES}|secret|token)[\"']?\s*[:=]\s*)"
    r"(\"[^\"\n]*\"|'[^'\n]*'|[^\s\"'&,;{}<>]+)",
    re.I,
)
_STRICT_NAME = re.compile(rf"(?:{_STRICT_NAMES})", re.I)
_EMAIL = re.compile(
    r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+(?:@|%40)[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", re.I
)
_RUN = re.compile(r"(?<![A-Za-z0-9+/_=-])[A-Za-z0-9+/_=-]{32,}")
_HEX_RUN = re.compile(r"[0-9a-fA-F-]+")
_DIGIT, _LETTER = re.compile(r"[0-9]"), re.compile(r"[A-Za-z]")
_SEGMENT_RUN = re.compile(r"[A-Za-z0-9_-]{24,}")

_HOST = re.compile(r"^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
_LOCATOR = re.compile(
    r"^(pypi|npm):(@[a-z0-9][a-z0-9._-]*/)?[A-Za-z0-9][A-Za-z0-9._-]{0,127}(@[A-Za-z0-9.+-]{1,64})?$"
)
_PACKAGE = re.compile(r"^(@[a-z0-9][a-z0-9._-]*/)?[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_VERSION = re.compile(r"^[A-Za-z0-9.+-]{1,64}$")


def _looks_secret(value: str) -> bool:
    """A value, not a word: a digit, both cases, or base64/JWT punctuation."""
    return bool(
        _DIGIT.search(value)
        or (value.lower() != value and value.upper() != value)
        or any(c in value for c in ".~+/=")
    )


def _url(match: re.Match[str]) -> str:
    """Any scheme: drop query and fragment; a URL that may carry credentials goes whole.

    No guessing where userinfo ends (a password may hold `/ ? #`, a query may hold `@`): any `@`,
    or a non-numeric port, redacts the URL. Nothing is lost: the server normalizes URLs to <url>.
    """
    scheme, _, rest = match.group(0).partition("://")
    if "@" in rest:
        return f"{scheme}://{REDACTED}"
    rest = rest[: min((i for i in (rest.find("?"), rest.find("#")) if i >= 0), default=len(rest))]
    _, colon, port = rest.split("/", 1)[0].rpartition(":")
    if colon and not port.isdigit():
        return f"{scheme}://{REDACTED}"
    return f"{scheme}://{rest}"


def _auth_scheme(match: re.Match[str]) -> str:
    scheme, space, value = match.groups()
    return f"{scheme}{space}{REDACTED}" if _looks_secret(value) else match.group(0)


def _named(match: re.Match[str]) -> str:
    prefix, value = match.groups()
    quote = value[0] if value[:1] in ("'", '"') else ""
    bare = value.strip("'\"")
    if _STRICT_NAME.match(prefix) or _looks_secret(bare) or len(bare) >= 12:
        return f"{prefix}{quote}{REDACTED}{quote}"
    return match.group(0)


def _run(match: re.Match[str]) -> str:
    run = match.group(0)
    if not _DIGIT.search(run):
        return run
    if _HEX_RUN.fullmatch(run):
        return ID
    return REDACTED if _LETTER.search(run) else run


def redact(text: str) -> str:
    """Replace secret-shaped substrings; keep everything else byte for byte."""
    text = _PEM.sub(REDACTED, text)
    text = _URL.sub(_url, text)
    text = _SHAPES.sub(REDACTED, text)
    text = _AUTH_SCHEME.sub(_auth_scheme, text)
    text = _NAMED.sub(_named, text)
    text = _EMAIL.sub(EMAIL, text)
    return _RUN.sub(_run, text)


def excerpt(text: str) -> str:
    """Redacted prefix of `text`, at most `EXCERPT_BYTES` of UTF-8 (no split character)."""
    if len(text) > RAW_CHARS:
        # Drop the token cut in half at the edge: a partial secret no longer matches a pattern.
        end, floor = RAW_CHARS, RAW_CHARS - 128
        while end > floor and text[end - 1] in _TOKEN_CHARS:
            end -= 1
        text = text[:end]
    data = redact(text).encode("utf-8")[:EXCERPT_BYTES]
    return data.decode("utf-8", "ignore")


def _scrub_segment(segment: str) -> str:
    segment = unquote(segment)  # judge what the server will decode, not the encoding
    if "@" in segment or _SHAPES.search(segment):
        return REDACTED
    for run in _SEGMENT_RUN.findall(segment):
        if _DIGIT.search(run) and _LETTER.search(run):
            return REDACTED
    return segment


def scrub_url(url: str) -> str | None:
    """`scheme://host/path` of an http(s) URL; query, fragment, userinfo and port dropped."""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    scheme = parts.scheme.lower()
    host = parts.hostname
    if scheme not in ("http", "https") or not host or not _HOST.match(host):
        return None
    path = "/".join(_scrub_segment(s) for s in parts.path.split("/")) or "/"
    return urlunsplit((scheme, host, path, "", ""))


def _target(value: str) -> str | None:
    value = value.strip()
    if "://" in value:
        return scrub_url(value)
    if _LOCATOR.match(value):
        return value
    host = value.lower()
    return host if _HOST.match(host) else None


def _sdk(sdk: Mapping[str, Any] | None) -> dict[str, str] | None:
    if not isinstance(sdk, Mapping):
        return None
    package, ecosystem, version = sdk.get("package"), sdk.get("ecosystem"), sdk.get("version")
    if not (isinstance(package, str) and _PACKAGE.match(package)):
        return None
    if ecosystem not in ("pypi", "npm"):
        return None
    out = {"package": package, "ecosystem": ecosystem}
    if isinstance(version, str) and _VERSION.match(version):
        out["version"] = version
    return out


@dataclass(frozen=True)
class Signal:
    """What one failure tells the registry. `make_signal` builds it and applies the filters."""

    url: str  # scrubbed URL, bare host, or pypi:/npm: locator
    method: str | None = None
    status: int | None = None
    body_excerpt: str | None = None
    sdk: Mapping[str, str] | None = None

    @property
    def host(self) -> str | None:
        if "://" in self.url:
            return urlsplit(self.url).hostname
        return None if _LOCATOR.match(self.url) else self.url

    def with_host(self, host: str) -> "Signal":
        parts = urlsplit(self.url)
        return replace(self, url=urlunsplit((parts.scheme, host, parts.path, "", "")))

    def payload(self) -> dict[str, Any]:
        """The `POST /v0/check` body: only the keys spec 03 accepts, unknown parts omitted."""
        target: dict[str, Any] = {"url": self.url}
        if self.method:
            target = {"method": self.method, **target}
        body: dict[str, Any] = {"target": target}
        error = {
            k: v
            for k, v in (("status", self.status), ("body_excerpt", self.body_excerpt))
            if v is not None
        }
        if error:
            body["error"] = error
        if self.sdk:
            body["context"] = {"sdk": dict(self.sdk)}
        return body


def make_signal(
    target: str,
    *,
    method: str | None = None,
    status: int | None = None,
    body: str | None = None,
    sdk: Mapping[str, Any] | None = None,
) -> Signal | None:
    """A filtered `Signal`, or None when `target` is not an http(s) URL, a host or a locator."""
    url = _target(target) if isinstance(target, str) else None
    if url is None:
        return None
    method = method.upper() if isinstance(method, str) else None
    ok_status = isinstance(status, int) and not isinstance(status, bool) and 100 <= status <= 599
    return Signal(
        url=url,
        method=method if method in HTTP_METHODS else None,
        status=status if ok_status else None,
        body_excerpt=(excerpt(body) or None) if isinstance(body, str) else None,
        sdk=_sdk(sdk),
    )
