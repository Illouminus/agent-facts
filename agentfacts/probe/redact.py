"""Redaction filter applied to every string before it reaches results.jsonl or a log (spec 04).

Three levels:
- exact key values (the runner's injected secrets and their derived forms) — everywhere;
- strict patterns `sk_[a-z]+_[A-Za-z0-9]{8,}`, `Bearer [A-Za-z0-9._-]{16,}` and the vendor key
  shapes of the keyed seed (PEM private keys, Google API keys and access tokens, Telegram bot
  tokens) — everywhere;
- generic runs: hex ≥ 32 always, base64 ≥ 32 when the run holds a digit and a letter (so words,
  slugs and URL paths survive) — on every field except the identifiers the runner itself produces,
  named by their full path in the run record (`EXEMPT_PATHS`), which a generic rule would otherwise
  eat (sha256 fingerprints, slugs with digits). Vendor-derived subtrees are never exempt.
"""

import base64
import re
from collections.abc import Iterable
from typing import Any
from urllib.parse import quote, quote_plus

REDACTED = "[redacted]"

_STRICT = (
    re.compile(r"sk_[a-z]+_[A-Za-z0-9]{8,}", re.IGNORECASE),
    re.compile(r"Bearer [A-Za-z0-9._-]{16,}", re.IGNORECASE),
    # Vendor key shapes of the keyed seed: a PEM private-key block (to its END line, or to the end
    # of a clipped string), a Google API key, a Google OAuth access token, a Telegram bot token.
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)",
               re.DOTALL),
    re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
    re.compile(r"ya29\.[0-9A-Za-z_-]{16,}"),
    re.compile(r"(?<![0-9])[0-9]{6,12}:[A-Za-z0-9_-]{30,}")  # also inside /bot<token>/,
)
_HEX_RUN = re.compile(r"[0-9a-fA-F]{32,}")
_B64_RUN = re.compile(r"[A-Za-z0-9+/_=-]{32,}")
_DIGIT = re.compile(r"[0-9]")
_LETTER = re.compile(r"[A-Za-z]")

# Fields of a run record the runner fills from the repository or computes itself; `*` = any list
# item. Never vendor-controlled.
EXEMPT_PATHS = frozenset(
    {
        *((name,) for name in (
            "probe_id", "service", "vantage", "selection", "env", "account_state", "outcome",
            "run_id", "started", "version",
        )),
        ("steps", "*", "do"),
        ("steps", "*", "body_fingerprint"),
        ("asserts", "*", "kind"),
        ("facts", "*", "id"),
        ("facts", "*", "change"),
    }
)


def secret_forms(key: str) -> set[str]:
    """A key and the encodings it travels in: URL-encoded (query auth) and base64 (basic auth)."""
    key = key.strip()
    if not key:
        return set()
    user_pass = key if ":" in key else key + ":"
    return {
        key,
        quote(key, safe=""),
        quote_plus(key),
        base64.b64encode(key.encode()).decode(),
        base64.b64encode(user_pass.encode()).decode(),
    }


def _generic(match: re.Match[str]) -> str:
    run = match.group(0)
    return REDACTED if _DIGIT.search(run) and _LETTER.search(run) else run


class Redactor:
    def __init__(self, secrets: Iterable[str]):
        self._secrets: set[str] = set()
        self._exact: re.Pattern[str] | None = None
        self.add(secrets)

    def add(self, secrets: Iterable[str]) -> None:
        """More exact secrets, e.g. an access token the runner minted mid-tick."""
        self._secrets |= {s.strip() for s in secrets if s and s.strip()}
        cleaned = sorted(self._secrets, key=len, reverse=True)
        # Case-insensitive: a vendor may echo a key lowercased, and `normalized` lowercases.
        self._exact = (
            re.compile("|".join(re.escape(s) for s in cleaned), re.IGNORECASE) if cleaned else None
        )

    def text_strict(self, value: str) -> str:
        if self._exact is not None:
            value = self._exact.sub(REDACTED, value)
        for pattern in _STRICT:
            value = pattern.sub(REDACTED, value)
        return value

    def text(self, value: str) -> str:
        value = self.text_strict(value)
        value = _HEX_RUN.sub(REDACTED, value)
        return _B64_RUN.sub(_generic, value)

    @classmethod
    def for_keys(cls, keys: Iterable[str]) -> "Redactor":
        return cls(set().union(*(secret_forms(k) for k in keys)))

    def record(self, data: Any, _path: tuple[str, ...] = ()) -> Any:
        """Redact every string in a run record (dict keys included); `EXEMPT_PATHS` get the
        strict level only."""
        if isinstance(data, str):
            return self.text_strict(data) if _path in EXEMPT_PATHS else self.text(data)
        if isinstance(data, dict):
            return {self.text(str(k)): self.record(v, (*_path, str(k))) for k, v in data.items()}
        if isinstance(data, list | tuple):
            return [self.record(v, (*_path, "*")) for v in data]
        return data

    def line(self, value: str) -> str:
        """Last scan of a serialized line: exact secrets and strict patterns."""
        return self.text_strict(value)
