"""Signal extraction and error string normalization (spec 03 steps 2 and 6, spec 05 drops).

The normalized string is what gets hashed, grouped by the quorum job and shown on pages, so it must
be the same for every reporter of the same error and must never carry a secret. Order matters:
URLs and emails go first (whatever they carry goes with them), secrets are redacted on the raw text
(the patterns are case-sensitive), then lowercase, ids, digits, whitespace, truncation.
"""

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

MAX_EXCERPT = 2048  # spec 03: body_excerpt kept, 2 KB in
MAX_NORMALIZED = 512  # spec 01/03: normalized error stored

REDACTED = "<redacted>"

_URL = re.compile(r"(?i)\b(?:(?:https?|wss?|ftp)://|www\.)[^\s<>\"'\])}]+")
_EMAIL = re.compile(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,}\b")
_UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
_HEX = re.compile(r"\b[0-9a-f]{16,}\b")
_DIGIT = re.compile(r"[0-9]")

# Vendor-shaped credentials, most specific first. Each is replaced whole by <redacted>.
_SECRET_PATTERNS = tuple(
    re.compile(p)
    for p in (
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----(?:[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----|[\s\S]*)",
        r"\b(?:sk|rk|pk)_(?:live|test)_[A-Za-z0-9]{10,}",
        r"\bwhsec_[A-Za-z0-9]{16,}",
        r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}",
        r"\bgh[pousr]_[A-Za-z0-9]{30,}",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}",
        r"\bxox[abposr]-[A-Za-z0-9-]{10,}",
        r"\bAIza[0-9A-Za-z_-]{30,}",
        r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
        r"\bya29\.[0-9A-Za-z_-]{20,}",
        r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}",
        r"\b[0-9]{8,10}:[A-Za-z0-9_-]{35}\b",  # Telegram bot token
        # Generic opaque token: ≥ 32 word chars mixing digits and non-hex letters (pure hex is an
        # id, handled by normalize()).
        r"\b(?=[A-Za-z0-9_]*[0-9])(?=[A-Za-z0-9_]*[G-Zg-z_])[A-Za-z0-9_]{32,}\b",
    )
)
# `name: value` / `name=value` / `"name": "value"`; the name is kept, the value redacted.
_NAMED_SECRET = re.compile(
    r"(?i)\b(?P<name>x-api-key|api[_-]?key|access[_-]?token|refresh[_-]?token|auth[_-]?token"
    r"|id[_-]?token|client[_-]?secret|secret[_-]?key|private[_-]?key|authorization"
    r"|password|passwd|pwd|token|secret)"
    r"(?P<sep>[\"']?\s*[:=]\s*[\"']?)"
    r"(?P<value>(?:(?:bearer|basic|token)\s+)?[^\s\"'&,;]+)"
)
_SCHEME_VALUE = re.compile(r"(?i)^(?:bearer|basic|token)\s")
_AUTH_SCHEME = re.compile(r"(?i)\b(?P<scheme>bearer|basic)\s+(?=\S*[0-9])[A-Za-z0-9._~+/=-]{8,}")

_PROMPT_MARKERS = re.compile(
    r"ignore (?:all |any |the )*(?:previous|prior|above)"
    r"|disregard (?:all |any |the )*(?:previous|prior|above)"
    r"|\bsystem\s*:|\bassistant\s*:|<\|im_(?:start|end)\|>|\[/?inst\]"
)


def _named_secret(m: re.Match[str]) -> str:
    value, sep = m["value"], m["sep"]
    if "=" in sep or '"' in sep or "'" in sep or _SCHEME_VALUE.match(value):
        secret = len(value) >= 4
    else:  # prose like "Invalid token: expired" is not a credential
        secret = len(value) >= 8 and any(c.isdigit() for c in value)
    return f"{m['name']}{sep}{REDACTED}" if secret else m[0]


def redact_secrets(text: str) -> str:
    """Replace secret-shaped substrings with `<redacted>` (spec 03 step 6, invariant 4)."""
    text = _NAMED_SECRET.sub(_named_secret, text)
    text = _AUTH_SCHEME.sub(lambda m: f"{m['scheme']} {REDACTED}", text)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(REDACTED, text)
    return text


def normalize(text: str) -> str:
    """Spec 03 step 2: lowercase, collapse whitespace, digits → #, UUID/hex ≥ 16 → <id>,
    emails → <email>, URLs → <url>, truncate 512; secrets → <redacted> before anything is kept."""
    text = _URL.sub("<url>", text)
    text = _EMAIL.sub("<email>", text)
    text = redact_secrets(text).lower()
    text = _UUID.sub("<id>", text)
    text = _HEX.sub("<id>", text)
    text = _DIGIT.sub("#", text)
    return " ".join(text.split())[:MAX_NORMALIZED].rstrip()


def error_hash(normalized: str) -> str:
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def find_urls(text: str) -> list[str]:
    """Absolute URLs in `text` (bare `www.` ones get `https://`), in order of appearance."""
    urls = []
    for m in _URL.finditer(text):
        url = m[0]
        urls.append(f"https://{url}" if url[:4].lower() == "www." else url)
    return urls


def looks_like_prompt(text: str) -> bool:
    """Spec 05: strings that read like instructions to a model are dropped, never stored."""
    return bool(_PROMPT_MARKERS.search(" ".join(text.lower().split())))


# ── signal extraction ──────────────────────────────────────────────────────────────────────────

# Which whitelisted fields carry a vendor code and which a message, by their last path segment.
_CODE_LEAVES = frozenset({"code", "error_code", "errorcode", "type", "reason", "status"})
_MESSAGE_LEAVES = frozenset(
    {"message", "msg", "detail", "description", "error_description", "error_message"}
)
_ERROR_CODE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}(?!\n)$")  # = Signal.error_code in models


@dataclass(frozen=True)
class ExtractedSignal:
    status: int | None
    error_code: str | None
    raw_string: str | None  # never stored; used only for the drop rules
    normalized: str | None
    error_hash: str | None

    @property
    def empty(self) -> bool:
        return self.status is None and self.normalized is None


def _path(field: str) -> list[str] | None:
    """A `signal_fields` entry as path segments: JSON pointer (`/a/b`) or dotted (`a.b`).
    A bare name without a dot is a header or the HTTP status, not a body field."""
    if field.startswith("/"):
        return [p.replace("~1", "/").replace("~0", "~") for p in field[1:].split("/")]
    return field.split(".") if "." in field else None


def _lookup(data: Any, path: list[str]) -> Any:
    for part in path:
        if not isinstance(data, dict) or part not in data:
            return None
        data = data[part]
    return data


def _json_body(excerpt: str) -> Any:
    if not excerpt.lstrip().startswith(("{", "[")):
        return None
    try:
        return json.loads(excerpt)
    except ValueError:
        return None


def _first_line(excerpt: str) -> str | None:
    return next((line.strip() for line in excerpt.splitlines() if line.strip()), None)


def extract_signal(
    status: int | None, body_excerpt: str | None, signal_fields: Iterable[str]
) -> ExtractedSignal:
    """Spec 03 step 2: status; vendor code and message through the service's whitelist; error
    string = first whitelisted message field, else the first line of the excerpt."""
    excerpt = (body_excerpt or "")[:MAX_EXCERPT]
    data = _json_body(excerpt)
    code: str | None = None
    message: str | None = None
    for field in signal_fields:
        path = _path(field)
        if path is None or data is None:
            continue
        value = _lookup(data, path)
        leaf = path[-1].lower()
        if code is None and leaf in _CODE_LEAVES and isinstance(value, str | int):
            if not isinstance(value, bool) and _ERROR_CODE.match(str(value)):
                code = str(value)
        elif message is None and leaf in _MESSAGE_LEAVES and isinstance(value, str):
            message = value.strip() or None
    raw = message or _first_line(excerpt)
    normalized = normalize(raw) if raw else None
    normalized = normalized or None
    return ExtractedSignal(
        status=status,
        error_code=code,
        raw_string=raw,
        normalized=normalized,
        error_hash=error_hash(normalized) if normalized else None,
    )
