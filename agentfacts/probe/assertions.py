"""Assertions over step responses (spec 04): status, header, json_path, body_contains, latency_ms,
schema_fingerprint. A failed assertion is data, never an exception.

`schema_fingerprint` = sha256 of `json.dumps(sorted(top-level keys), separators=(",", ":"))` of a
JSON object body; every step record carries it as `body_fingerprint`, so a probe author copies the
value from `results.jsonl`.
"""

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agentfacts.probe.http import StepResponse
from agentfacts.probe.templating import NOT_JSON, lookup
from agentfacts.schema.models import (
    AssertBodyContains,
    AssertHeader,
    Assertion,
    AssertJsonPath,
    AssertLatency,
    AssertSchemaFingerprint,
    AssertStatus,
)


@dataclass(frozen=True)
class AssertResult:
    step: int
    kind: str
    ok: bool
    detail: str

    def to_record(self) -> dict[str, Any]:
        return {"step": self.step, "kind": self.kind, "ok": self.ok, "detail": self.detail}


def schema_fingerprint(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    keys = json.dumps(sorted(body), separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(keys.encode("utf-8")).hexdigest()


def _shown(value: Any) -> str:
    # Never truncated here: a cut could leave part of a secret that redaction no longer matches.
    # The results log clips long strings after redaction.
    return json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else repr(value)


def _same(actual: Any, expected: Any) -> bool:
    """JSON equality without Python's True == 1: booleans only equal booleans, numbers compare by
    value (1 == 1.0), null only null."""
    if isinstance(actual, bool) or isinstance(expected, bool):
        return type(actual) is type(expected) and actual == expected
    if expected is None or actual is None:
        return actual is expected
    if isinstance(expected, int | float) and isinstance(actual, int | float):
        return actual == expected
    return type(actual) is type(expected) and actual == expected


def _kind(a: Assertion) -> str:
    return {
        AssertStatus: "status",
        AssertHeader: "header",
        AssertJsonPath: "json_path",
        AssertBodyContains: "body_contains",
        AssertLatency: "latency_ms",
        AssertSchemaFingerprint: "schema_fingerprint",
    }[type(a)]


def _status(a: AssertStatus, r: StepResponse) -> tuple[bool, str]:
    if r.status == a.status:
        return True, f"status {r.status}"
    return False, f"status {r.status} != {a.status}"


def _header(a: AssertHeader, r: StepResponse) -> tuple[bool, str]:
    value = r.headers.get(a.header)
    if a.present is not None:
        seen = "present" if value is not None else "absent"
        return (value is not None) is a.present, f"{a.header} {seen}"
    if value is None:
        return False, f"{a.header} absent"
    if a.equals is not None:
        if value == a.equals:
            return True, f"{a.header} = {_shown(value)}"
        return False, f"{a.header} = {_shown(value)} != {_shown(a.equals)}"
    try:
        found = re.search(a.matches, value) is not None
    except re.error as exc:
        return False, f"invalid regex {_shown(a.matches)}: {exc}"
    return found, f"{a.header} = {_shown(value)} {'matches' if found else 'does not match'}"


def _json_path(a: AssertJsonPath, r: StepResponse) -> tuple[bool, str]:
    if r.json is NOT_JSON:
        return False, "body is not JSON"
    try:
        value = lookup(r.json, a.json_path[1:])
    except ValueError:
        return False, f"unsupported json_path {a.json_path}"
    except LookupError:
        if a.exists is False:
            return True, f"{a.json_path} absent"
        return False, f"{a.json_path} absent"
    if a.exists is not None:
        return a.exists, f"{a.json_path} present"
    if "equals" in a.model_fields_set:
        if _same(value, a.equals):
            return True, f"{a.json_path} = {_shown(value)}"
        return False, f"{a.json_path} = {_shown(value)} != {_shown(a.equals)}"
    if isinstance(value, str):
        found = a.contains in value
    elif isinstance(value, list):
        found = any(isinstance(v, str) and v == a.contains for v in value)
    else:
        return False, f"{a.json_path} = {_shown(value)} is neither a string nor a list"
    verb = "contains" if found else "does not contain"
    return found, f"{a.json_path} {verb} {_shown(a.contains)}"


def _body_contains(a: AssertBodyContains, r: StepResponse) -> tuple[bool, str]:
    found = a.body_contains in r.body.decode("utf-8", errors="replace")
    return found, f"body {'contains' if found else 'does not contain'} {_shown(a.body_contains)}"


def _latency(a: AssertLatency, r: StepResponse) -> tuple[bool, str]:
    ok = r.latency_ms < a.latency_ms.lt
    return ok, f"latency {r.latency_ms} ms {'<' if ok else '>='} {a.latency_ms.lt} ms"


def _fingerprint(a: AssertSchemaFingerprint, r: StepResponse) -> tuple[bool, str]:
    seen = schema_fingerprint(r.json) if r.json is not NOT_JSON else None
    if seen is None:
        return False, "body is not a JSON object"
    return seen == a.schema_fingerprint, f"fingerprint {seen}"


_CHECKS = {
    AssertStatus: _status,
    AssertHeader: _header,
    AssertJsonPath: _json_path,
    AssertBodyContains: _body_contains,
    AssertLatency: _latency,
    AssertSchemaFingerprint: _fingerprint,
}


def evaluate(a: Assertion, responses: Mapping[int, StepResponse]) -> AssertResult:
    kind = _kind(a)
    r = responses.get(a.step)
    if r is None:
        return AssertResult(a.step, kind, False, f"step {a.step} has no response")
    if r.error is not None:
        return AssertResult(a.step, kind, False, f"step {a.step} failed: {r.error}")
    ok, detail = _CHECKS[type(a)](a, r)
    return AssertResult(a.step, kind, ok, detail)
