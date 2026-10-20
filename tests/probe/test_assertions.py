"""One pass and one fail case per assertion kind (spec 04 table)."""

import hashlib
import json

import httpx
import pytest

from agentfacts.probe.assertions import evaluate, schema_fingerprint
from agentfacts.probe.http import StepResponse
from agentfacts.probe.templating import NOT_JSON
from agentfacts.schema.models import (
    AssertBodyContains,
    AssertHeader,
    AssertJsonPath,
    AssertLatency,
    AssertSchemaFingerprint,
    AssertStatus,
)


def response(status=400, body=None, headers=None, latency_ms=120, text=None, error=None):
    raw = text.encode() if text is not None else json.dumps(body or {}).encode()
    parsed = body if text is None else NOT_JSON
    return StepResponse(
        status=status,
        headers=httpx.Headers(headers or {}),
        body=raw,
        json=parsed,
        latency_ms=latency_ms,
        error=error,
    )


BODY = {"error": {"code": "idempotency_error", "message": "same parameters", "n": 1, "t": True,
                  "none": None, "tags": ["a", "b"]}}
R = {1: response(body=BODY, headers={"Retry-After": "30", "Stripe-Version": "2024-06-20"})}


def check(**fields):
    model = {
        "status": AssertStatus,
        "header": AssertHeader,
        "json_path": AssertJsonPath,
        "body_contains": AssertBodyContains,
        "latency_ms": AssertLatency,
        "schema_fingerprint": AssertSchemaFingerprint,
    }[next(k for k in fields if k != "step" and k in (
        "status", "header", "json_path", "body_contains", "latency_ms", "schema_fingerprint"))]
    return evaluate(model.model_validate({"step": 1, **fields}), R)


@pytest.mark.parametrize(
    ("fields", "ok"),
    [
        ({"status": 400}, True),
        ({"status": 200}, False),
        ({"header": "retry-after", "present": True}, True),
        ({"header": "X-Missing", "present": True}, False),
        ({"header": "X-Missing", "present": False}, True),
        ({"header": "Retry-After", "present": False}, False),
        ({"header": "Stripe-Version", "equals": "2024-06-20"}, True),
        ({"header": "Stripe-Version", "equals": "2024-06-21"}, False),
        ({"header": "X-Missing", "equals": "x"}, False),
        ({"header": "Retry-After", "matches": r"^\d+$"}, True),
        ({"header": "Retry-After", "matches": r"^[a-z]+$"}, False),
        ({"header": "Retry-After", "matches": "("}, False),  # invalid regex fails, no crash
        ({"json_path": "$.error.code", "equals": "idempotency_error"}, True),
        ({"json_path": "$.error.code", "equals": "other"}, False),
        ({"json_path": "$.error.n", "equals": 1}, True),
        ({"json_path": "$.error.n", "equals": 1.0}, True),
        ({"json_path": "$.error.n", "equals": True}, False),  # strict: True is not 1
        ({"json_path": "$.error.t", "equals": 1}, False),
        ({"json_path": "$.error.t", "equals": True}, True),
        ({"json_path": "$.error.none", "equals": None}, True),
        ({"json_path": "$.error.code", "equals": None}, False),
        ({"json_path": "$.error.message", "contains": "same param"}, True),
        ({"json_path": "$.error.message", "contains": "other"}, False),
        ({"json_path": "$.error.tags", "contains": "b"}, True),
        ({"json_path": "$.error.tags", "contains": "c"}, False),
        ({"json_path": "$.error.n", "contains": "1"}, False),
        ({"json_path": "$.error.code", "exists": True}, True),
        ({"json_path": "$.error.absent", "exists": True}, False),
        ({"json_path": "$.error.absent", "exists": False}, True),
        ({"json_path": "$.error.code", "exists": False}, False),
        ({"json_path": "$['error']", "exists": True}, False),  # unsupported syntax fails
        ({"body_contains": "idempotency_error"}, True),
        ({"body_contains": "nope"}, False),
        ({"latency_ms": {"lt": 500}}, True),
        ({"latency_ms": {"lt": 100}}, False),
        ({"schema_fingerprint": schema_fingerprint(BODY)}, True),
        ({"schema_fingerprint": "0" * 64}, False),
    ],
)
def test_assertion_kinds(fields, ok):
    result = check(**fields)
    assert result.ok is ok, result.detail
    assert result.step == 1 and result.detail


def test_failure_detail_says_what_was_seen():
    assert check(status=200).detail == "status 400 != 200"


def test_fingerprint_is_sha256_of_sorted_top_level_keys():
    expected = hashlib.sha256(b'["a","b"]').hexdigest()
    assert schema_fingerprint({"b": 1, "a": {"z": 2}}) == expected
    assert schema_fingerprint([1, 2]) is None
    assert schema_fingerprint(NOT_JSON) is None


def test_json_assertions_fail_on_non_json_body():
    responses = {1: response(text="<html>oops</html>")}
    a = AssertJsonPath.model_validate({"step": 1, "json_path": "$.x", "exists": False})
    assert not evaluate(a, responses).ok
    f = AssertSchemaFingerprint.model_validate({"step": 1, "schema_fingerprint": "0" * 64})
    assert not evaluate(f, responses).ok


def test_step_without_response_fails():
    a = AssertStatus.model_validate({"step": 2, "status": 200})
    result = evaluate(a, R)
    assert not result.ok and "no response" in result.detail


def test_transport_error_fails_every_assertion():
    responses = {1: response(status=None, error="timeout")}
    a = AssertLatency.model_validate({"step": 1, "latency_ms": {"lt": 60000}})
    result = evaluate(a, responses)
    assert not result.ok and "timeout" in result.detail


def test_record_shape():
    rec = check(status=400).to_record()
    assert rec == {"step": 1, "kind": "status", "ok": True, "detail": "status 400"}


def test_details_never_carry_whole_json_values():
    responses = {1: response(body={"user": {"email": "a@b.example", "name": "Ann"},
                                   "ids": [1, 2, 3]})}
    for fields in ({"json_path": "$.user", "equals": "x"},
                   {"json_path": "$.user", "contains": "x"},
                   {"json_path": "$.ids", "equals": 1}):
        detail = evaluate(AssertJsonPath.model_validate({"step": 1, **fields}), responses).detail
        assert "a@b.example" not in detail and "Ann" not in detail
    detail = evaluate(AssertJsonPath.model_validate(
        {"step": 1, "json_path": "$.user", "equals": "x"}), responses).detail
    assert "object (2 keys)" in detail
    detail = evaluate(AssertJsonPath.model_validate(
        {"step": 1, "json_path": "$.ids", "equals": 1}), responses).detail
    assert "array (3 items)" in detail


def test_fingerprint_detail_points_to_the_step_record():
    result = check(schema_fingerprint="0" * 64)
    assert result.detail == "fingerprint differs (see steps[1].body_fingerprint)"
    assert check(schema_fingerprint=schema_fingerprint(BODY)).detail == "fingerprint matches"
