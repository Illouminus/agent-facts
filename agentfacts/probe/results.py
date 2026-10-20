"""Run records and `results.jsonl`: one redacted JSON line per probe run (spec 04 Execution).

A step records what spec 04 lists — status, latency, whitelisted headers, body fingerprint, error
string — and never the URL query (it may carry a `query` auth key) or the body itself. Headers kept:
a fixed rate-limit/content set, the service's `signal_fields` that are header names, and headers the
probe asserts on; never credentials or cookies.

Order matters for secrets: vendor text is redacted *before* it is clipped or lowercased (a cut or a
case change would hide a key from exact matching), and the log clips long strings only after the
whole record has been redacted.
"""

import json
import re
from pathlib import Path
from typing import Any

from agentfacts.probe.assertions import schema_fingerprint
from agentfacts.probe.http import PreparedRequest, Refused, StepResponse
from agentfacts.probe.redact import Redactor
from agentfacts.probe.templating import NOT_JSON, lookup
from agentfacts.schema.models import AssertHeader, HttpStep, Probe, Service

BASE_HEADERS = frozenset(
    {
        "content-type",
        "retry-after",
        "ratelimit",
        "ratelimit-policy",
        "ratelimit-limit",
        "ratelimit-remaining",
        "ratelimit-reset",
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-reset",
        "x-ratelimit-used",
        "x-ratelimit-resource",
    }
)
NEVER_HEADERS = frozenset({"authorization", "proxy-authorization", "cookie", "set-cookie"})
_HEADER_NAME = re.compile(r"^[A-Za-z0-9-]{1,128}$")
# Where vendors put the human-readable error, most specific first.
_ERROR_PATHS = (
    ".error.message",
    ".error_description",
    ".message",
    ".detail",
    ".error",
    ".errors[0].message",
    ".title",
)
ERROR_MAX = 512
_TEXT_ERROR_MAX = 200
FIELD_MAX = 1024  # any string in a record, clipped after redaction
DETAIL_MAX = 200  # run and assertion details
_DETAIL_PATHS = frozenset({("detail",), ("asserts", "*", "detail")})


def header_whitelist(service: Service, probe: Probe) -> frozenset[str]:
    names = set(BASE_HEADERS)
    http = service.surfaces.http
    for name in (http.signal_fields or ()) if http else ():
        if _HEADER_NAME.match(name):
            names.add(name.lower())
    names.update(a.header.lower() for a in probe.assertions if isinstance(a, AssertHeader))
    if service.auth is not None and service.auth.header_name:
        names.discard(service.auth.header_name.lower())
    return frozenset(names - NEVER_HEADERS)


def _squash(text: str, limit: int = ERROR_MAX) -> str:
    return " ".join(text.split())[:limit]


def error_text(response: StepResponse, redactor: Redactor) -> str | None:
    """The vendor's error message of a ≥ 400 response, or the transport error: redacted, then
    squashed and clipped."""
    if response.error is not None:
        return response.error
    if response.status is None or response.status < 400:
        return None
    if response.json is not NOT_JSON:
        for path in _ERROR_PATHS:
            try:
                value = lookup(response.json, path)
            except LookupError:
                continue
            if isinstance(value, str) and value.strip():
                return _squash(redactor.text(value))
        return None
    body = redactor.text(response.body.decode("utf-8", errors="replace"))
    return _squash(body, _TEXT_ERROR_MAX) or None


def normalize(text: str) -> str:
    """Spec 01 `signal.normalized`: lowercase, squashed whitespace, no trailing period."""
    return " ".join(text.lower().split()).rstrip(".")[:ERROR_MAX]


def http_step_record(
    index: int,
    request: PreparedRequest,
    response: StepResponse,
    whitelist: frozenset[str],
    redactor: Redactor,
) -> dict[str, Any]:
    error = error_text(response, redactor)
    return {
        "step": index,
        "do": "http",
        "method": request.method,
        "path": request.path,
        "template": request.template,
        "status": response.status,
        "latency_ms": response.latency_ms,
        "headers": {k: v for k, v in sorted(response.headers.items()) if k.lower() in whitelist},
        "body_fingerprint": schema_fingerprint(response.json),
        "body_bytes": len(response.body),
        "error_string": error,
        "normalized": normalize(error) if error else None,
    }


def sleep_step_record(index: int, seconds: float) -> dict[str, Any]:
    return {"step": index, "do": "sleep", "seconds": seconds}


def refused_step_record(index: int, step: HttpStep, refused: Refused) -> dict[str, Any]:
    return {
        "step": index,
        "do": "http",
        "method": step.method,
        "path": step.path,
        "refused": refused.code,
        "error_string": _squash(refused.message),
    }


def _clip(data: Any, path: tuple[str, ...] = ()) -> Any:
    if isinstance(data, str):
        limit = DETAIL_MAX if path in _DETAIL_PATHS else FIELD_MAX
        return data if len(data) <= limit else data[: limit - 1] + "…"
    if isinstance(data, dict):
        return {k: _clip(v, (*path, k)) for k, v in data.items()}
    if isinstance(data, list):
        return [_clip(v, (*path, "*")) for v in data]
    return data


class ResultsLog:
    def __init__(self, path: Path, redactor: Redactor):
        self.path = path
        self.redactor = redactor

    def append(self, record: dict[str, Any]) -> dict[str, Any]:
        """Redact, clip, serialize, scan the line once more, append; returns what was written."""
        redacted = _clip(self.redactor.record(record))
        line = json.dumps(redacted, ensure_ascii=False, separators=(",", ":"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(self.redactor.line(line) + "\n")
        return redacted
