"""POST /v0/check contract (spec 03): response fields, lookup tiers, pre-flight, bad requests."""

import re
import sqlite3

import pytest
from api_fixtures import IDEMPOTENCY_BODY, IDEMPOTENCY_ID, STRIPE_PI

from apifacts.api.normalize import error_hash

KEYS = {"service", "matched_template", "facts", "observed", "unknown", "registry"}
OBSERVED_EMPTY = {
    "status_distribution_30d": {},
    "p50_latency_ms": None,
    "last_probe": None,
    "rate_limit_headers": ["retry-after"],
}
REGISTRY = {"version": "2026-10-22", "facts_for_service": 4, "license": "CC-BY-4.0"}
IDEMPOTENCY_REQUEST = {
    "target": {"method": "POST", "url": STRIPE_PI},
    "error": {"status": 400, "body_excerpt": IDEMPOTENCY_BODY},
    "context": {"sdk": {"package": "stripe", "ecosystem": "pypi", "version": "12.1.0"},
                "env_hint": "prod"},
}


def check(client, payload, **kwargs):
    return client.post("/v0/check", json=payload, **kwargs)


def ids(body) -> list[str]:
    return [f["id"] for f in body["facts"]]


def test_exact_match_full_response(client, rows):
    r = check(client, IDEMPOTENCY_REQUEST)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == KEYS
    assert body["service"] == "stripe"
    assert body["matched_template"] == {"method": "POST", "path": "/v1/payment_intents"}
    assert ids(body) == [IDEMPOTENCY_ID]
    fact = body["facts"][0]
    assert fact["status"] == "verified:server:prod"
    assert fact["claim"].startswith("Reusing an Idempotency-Key")
    assert fact["fixes"] == [
        {"action": "set_param", "name": "Idempotency-Key",
         "value_source": "new_uuid_per_distinct_request"}
    ]
    assert fact["fixes_rendered"] == [
        "Set parameter Idempotency-Key to new UUID per distinct request"
    ]
    assert body["observed"] == OBSERVED_EMPTY
    assert body["unknown"] == {"reason": None, "stored_as_observation": True}
    assert body["registry"] == REGISTRY
    assert rows() == 1


def test_stored_row_is_normalized_and_anonymous(client, db_path):
    check(client, IDEMPOTENCY_REQUEST, headers={"User-Agent": "apifacts-pytest/0.1.0"})
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = dict(conn.execute("SELECT * FROM observations").fetchone())
    normalized = (
        "keys for idempotent requests can only be used with the same parameters they were "
        "first used with."
    )
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", row.pop("received_at"))
    assert re.fullmatch(r"[0-9a-f]{64}", row.pop("reporter_net"))
    assert row == {
        "id": 1,
        "service": "stripe",
        "method": "POST",
        "path_template": "/v1/payment_intents",
        "status": 400,
        "error_hash": error_hash(normalized),
        "normalized_error": normalized,
        "reporter_ua_class": "pytest-plugin",
        "sdk_package": "stripe",
        "sdk_version": "12.1.0",
        "env_guess": "prod",
        "vantage_country": None,
    }


def test_same_network_same_period_same_reporter_hash(make_client, db_path):
    a = make_client(peer=("203.0.113.7", 1))
    b = make_client(peer=("203.0.200.9", 2))  # same /16
    c = make_client(peer=("198.51.100.1", 3))
    for client in (a, b, c):
        check(client, IDEMPOTENCY_REQUEST)
    with sqlite3.connect(db_path) as conn:
        nets = [r[0] for r in conn.execute("SELECT reporter_net FROM observations ORDER BY id")]
    assert nets[0] == nets[1] != nets[2]


def test_status_tier(client):
    error = {"status": 400, "body_excerpt": "Something else entirely"}
    body = check(client, {"target": {"method": "POST", "url": STRIPE_PI}, "error": error}).json()
    assert ids(body) == [IDEMPOTENCY_ID, "af:stripe:old-sdk-bad-request"]
    assert body["unknown"]["reason"] is None


def test_sdk_version_filters_facts(client):
    payload = {"target": {"method": "POST", "url": STRIPE_PI},
               "error": {"status": 400, "body_excerpt": "Something else"},
               "context": {"sdk": {"package": "stripe", "ecosystem": "pypi", "version": "12.1.0"}}}
    assert ids(check(client, payload).json()) == [IDEMPOTENCY_ID]


def test_vendor_code_tier(client):
    excerpt = '{"error": {"code": "resource_missing", "message": "No such customer: \'cus_9z\'"}}'
    body = check(client, {"target": {"method": "GET",
                                     "url": "https://api.stripe.com/v1/customers/cus_9z"},
                          "error": {"status": 404, "body_excerpt": excerpt}}).json()
    assert body["matched_template"] == {"method": "GET", "path": "/v1/customers/{id}"}
    assert ids(body) == ["af:stripe:customer-not-found"]


def test_service_level_fallback_is_no_fact_for_signal(client):
    body = check(client, {"target": {"method": "POST", "url": STRIPE_PI},
                          "error": {"status": 500, "body_excerpt": "Internal error"}}).json()
    assert ids(body) == ["af:stripe:payment-intents-429"]
    assert body["unknown"] == {"reason": "no_fact_for_signal", "stored_as_observation": True}


def test_signal_not_extractable(client, rows):
    body = check(client, {"target": {"method": "POST", "url": STRIPE_PI},
                          "error": {"body_excerpt": "   \n  "}}).json()
    assert body["unknown"] == {"reason": "signal_not_extractable", "stored_as_observation": False}
    assert ids(body) == ["af:stripe:payment-intents-429"]
    assert rows() == 0


def test_registered_service_without_facts_still_answers(client, rows):
    error = {"status": 404, "body_excerpt": '{"message": "Not Found"}'}
    target = {"method": "GET", "url": "https://pypi.org/pypi/requests/json"}
    body = check(client, {"target": target, "error": error}).json()
    assert set(body) == KEYS
    assert body["service"] == "pypi" and body["facts"] == []
    assert body["observed"] == {**OBSERVED_EMPTY, "rate_limit_headers": []}
    assert body["unknown"] == {"reason": "no_fact_for_signal", "stored_as_observation": True}
    assert body["registry"] == {**REGISTRY, "facts_for_service": 0}
    assert rows() == 1


def test_preflight_url_lists_template_and_service_facts(client, rows):
    body = check(client, {"target": {"method": "GET",
                                     "url": "https://api.stripe.com/v1/customers/cus_1"}}).json()
    assert ids(body) == ["af:stripe:customer-not-found", "af:stripe:payment-intents-429"]
    assert body["unknown"] == {"reason": None, "stored_as_observation": False}  # Q5
    assert rows() == 0


def test_preflight_bare_host(client, rows):
    body = check(client, {"target": {"url": "api.stripe.com"}}).json()
    assert body["service"] == "stripe" and body["matched_template"] is None
    assert len(body["facts"]) == 4
    assert body["unknown"] == {"reason": None, "stored_as_observation": False}
    assert rows() == 0


@pytest.mark.parametrize(
    "locator, expected",
    [
        ("pypi:stripe@11.0.0", [IDEMPOTENCY_ID, "af:stripe:old-sdk-bad-request"]),
        ("pypi:stripe@12.1.0", [IDEMPOTENCY_ID]),
        ("pypi:stripe", [IDEMPOTENCY_ID, "af:stripe:old-sdk-bad-request"]),
    ],
)
def test_preflight_locator(client, rows, locator, expected):
    body = check(client, {"target": {"url": locator}}).json()
    assert body["service"] == "stripe" and ids(body) == expected
    assert body["unknown"]["stored_as_observation"] is False
    assert rows() == 0


def test_locator_without_facts(client):
    body = check(client, {"target": {"url": "npm:stripe@15.0.0"}}).json()
    assert body["facts"] == [] and body["unknown"]["reason"] == "no_fact_for_signal"


def test_method_is_case_insensitive(client):
    body = check(client, {"target": {"method": "post", "url": STRIPE_PI}}).json()
    assert body["matched_template"] == {"method": "POST", "path": "/v1/payment_intents"}


def test_registry_version_override(make_client, monkeypatch):
    monkeypatch.setenv("APIFACTS_REGISTRY_VERSION", "2026-11-01")
    body = check(make_client(), IDEMPOTENCY_REQUEST).json()
    assert body["registry"]["version"] == "2026-11-01"


# ── bad requests ────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "payload, field",
    [
        ({"target": {"url": STRIPE_PI, "method": "POST"}, "extra": 1}, "extra"),
        ({"target": {"url": STRIPE_PI, "method": "POST", "headers": {"a": "b"}}}, "target.headers"),
        ({"target": {"url": STRIPE_PI, "method": "POST"}, "error": {"status": 400, "body": "x"}},
         "error.body"),
        ({"target": {"url": "pypi:stripe"},
          "context": {"sdk": {"package": "stripe", "ecosystem": "pypi", "token": "x"}}},
         "context.sdk.token"),
    ],
)
def test_unknown_fields_are_refused(client, rows, payload, field):
    r = check(client, payload)
    assert r.status_code == 400
    assert r.json() == {"error": {"code": "unknown_field", "message": f"unknown field {field}",
                                  "field": field}}
    assert rows() == 0


@pytest.mark.parametrize(
    "content, field",
    [
        (b"", None),
        (b"{}", "target"),
        (b"[]", None),
        (b"not json", None),
        (b'{"target": {}}', "target.url"),
        (b'{"target": {"url": ""}}', "target.url"),
        (b'{"target": {"url": 5}}', "target.url"),
        (b'{"target": {"method": "BREW", "url": "https://api.stripe.com/v1/x"}}', "target.method"),
        (b'{"target": {"url": "https://api.stripe.com/v1/payment_intents"}}', "target.method"),
        (b'{"target": {"method": "POST", "url": "x"}, "error": {"status": "400"}}', "error.status"),
        (b'{"target": {"method": "POST", "url": "x"}, "error": {"status": 99}}', "error.status"),
        (b'{"target": {"url": "x"}, "context": {"env_hint": "staging"}}', "context.env_hint"),
        (b'{"target": {"url": "x"}, "context": {"sdk": {"package": "a b", "ecosystem": "pypi"}}}',
         "context.sdk.package"),
    ],
)
def test_invalid_requests(client, rows, content, field):
    r = client.post("/v0/check", content=content, headers={"Content-Type": "application/json"})
    assert r.status_code == 400
    error = r.json()["error"]
    assert error["code"] == "invalid_request"
    if field is not None:
        assert error["field"] == field
    assert rows() == 0


def test_error_messages_never_echo_the_input(client):
    r = check(client, {"target": {"url": "x", "method": "sk_live_51HxAbCdEfGhIjKlMnOpQr"}})
    assert r.status_code == 400 and "sk_live" not in r.text


def test_body_over_8kb_is_refused(client, rows):
    payload = {"target": {"method": "POST", "url": STRIPE_PI},
               "error": {"status": 400, "body_excerpt": "x" * 8200}}
    r = check(client, payload)
    assert r.status_code == 413 and r.json()["error"]["code"] == "body_too_large"
    assert rows() == 0


def test_streamed_body_over_8kb_is_refused(client, rows):
    def chunks():
        yield b'{"target": {"method": "POST", "url": "' + STRIPE_PI.encode() + b'"}, '
        yield b'"error": {"body_excerpt": "' + b"x" * 9000 + b'"}}'

    r = client.post("/v0/check", content=chunks(), headers={"Content-Type": "application/json"})
    assert r.status_code == 413
    assert rows() == 0


def test_malformed_content_length_is_a_bad_request(client):
    r = client.post("/v0/check", content=b"{}", headers={"Content-Length": "abc"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_request"


def test_body_just_under_8kb_is_fine(client):
    payload = {"target": {"method": "POST", "url": STRIPE_PI},
               "error": {"status": 400, "body_excerpt": "x" * 8000}}
    assert check(client, payload).status_code == 200


def test_unknown_route_uses_the_error_envelope(client):
    r = client.get("/v0/nothing")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
