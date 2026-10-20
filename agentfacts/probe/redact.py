"""Redaction filter applied to every string before it reaches results.jsonl or a log (spec 04).

Three levels:
- exact key values (the runner's injected secrets and their derived forms) — everywhere;
- strict patterns `sk_[a-z]+_[A-Za-z0-9]{8,}` and `Bearer [A-Za-z0-9._-]{16,}` — everywhere;
- generic runs: hex ≥ 32 always, base64 ≥ 32 when the run holds a digit and a letter (so words,
  slugs and URL paths survive) — on every field except identifiers the runner itself produces
  (`EXEMPT_FIELDS`), which a generic rule would otherwise eat (sha256 fingerprints, digit slugs).
"""

import re
from collections.abc import Iterable
from typing import Any

REDACTED = "[redacted]"

_STRICT = (
    re.compile(r"sk_[a-z]+_[A-Za-z0-9]{8,}"),
    re.compile(r"Bearer [A-Za-z0-9._-]{16,}"),
)
_HEX_RUN = re.compile(r"[0-9a-fA-F]{32,}")
_B64_RUN = re.compile(r"[A-Za-z0-9+/_=-]{32,}")
_DIGIT = re.compile(r"[0-9]")
_LETTER = re.compile(r"[A-Za-z]")

# Values the runner generates from the repository or computes itself; never vendor-controlled.
EXEMPT_FIELDS = frozenset(
    {"probe_id", "service", "vantage", "env", "account_state", "outcome", "id", "change",
     "kind", "do", "body_fingerprint", "run_id", "started", "finished", "version"}
)


def _generic(match: re.Match[str]) -> str:
    run = match.group(0)
    return REDACTED if _DIGIT.search(run) and _LETTER.search(run) else run


class Redactor:
    def __init__(self, secrets: Iterable[str]):
        cleaned = {s.strip() for s in secrets if s and s.strip()}
        self._secrets = sorted(cleaned, key=len, reverse=True)

    def text_strict(self, value: str) -> str:
        for secret in self._secrets:
            value = value.replace(secret, REDACTED)
        for pattern in _STRICT:
            value = pattern.sub(REDACTED, value)
        return value

    def text(self, value: str) -> str:
        value = self.text_strict(value)
        value = _HEX_RUN.sub(REDACTED, value)
        return _B64_RUN.sub(_generic, value)

    def record(self, data: Any, *, exempt: bool = False) -> Any:
        """Redact every string in a JSON-like structure (dict keys included)."""
        if isinstance(data, str):
            return self.text_strict(data) if exempt else self.text(data)
        if isinstance(data, dict):
            return {
                self.text(str(k)): self.record(v, exempt=k in EXEMPT_FIELDS)
                for k, v in data.items()
            }
        if isinstance(data, list | tuple):
            return [self.record(v, exempt=exempt) for v in data]
        return data

    def line(self, value: str) -> str:
        """Last scan of a serialized line: exact secrets and strict patterns."""
        return self.text_strict(value)
