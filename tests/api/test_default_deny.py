"""Default-deny ingestion (spec 03 step 1, invariant 3): an unregistered target is answered, never
stored; only one anonymous counter moves."""

import pytest
from api_fixtures import STRIPE_PI

KEYS = {"service", "matched_template", "facts", "observed", "unknown", "registry"}


@pytest.mark.parametrize(
    "target",
    [
        {"method": "GET", "url": "https://api.notion.com/v1/pages/abc"},
        {"method": "POST", "url": "https://eu.api.stripe.com/v1/payment_intents"},  # subdomain
        {"method": "DELETE", "url": STRIPE_PI},  # registered path, other method
        {"method": "POST", "url": "https://api.stripe.com/v1/charges"},  # unregistered path
        {"method": "POST", "url": "https://api.stripe.com/v1/payment_intents/"},
        {"method": "GET", "url": "https://api.stripe.com/v1/customers/%2e%2e"},
        {"method": "GET", "url": "https://api.stripe.com/v1/customers/../payment_intents"},
        {"url": "npm:left-pad@1.3.0"},
        {"url": "api.notion.com"},
        {"url": "ftp://api.stripe.com/v1/payment_intents"},
        {"url": "not a url at all"},
    ],
)
def test_unregistered_target_is_answered_but_not_stored(client, rows, counters, target):
    r = client.post(
        "/v0/check",
        json={"target": target, "error": {"status": 429, "body_excerpt": "Too many requests"}},
    )
    assert r.status_code == 200
    body = r.json()
    assert set(body) == KEYS
    assert body["matched_template"] is None
    assert body["unknown"] == {"reason": "unregistered_target", "stored_as_observation": False}
    assert body["registry"]["license"] == "CC-BY-4.0"
    assert rows() == 0
    assert counters() == {"unregistered_target": 1}


def test_unregistered_path_on_known_host_still_gets_service_facts(client, rows):
    body = client.post(
        "/v0/check",
        json={"target": {"method": "POST", "url": "https://api.stripe.com/v1/charges"}},
    ).json()
    assert body["service"] == "stripe"
    assert [f["id"] for f in body["facts"]] == ["af:stripe:payment-intents-429"]
    assert rows() == 0


def test_unknown_host_names_nothing(client, db_path):
    body = client.post(
        "/v0/check",
        json={"target": {"method": "GET", "url": "https://api.notion.com/v1/secret-project"}},
    ).json()
    assert body["service"] is None and body["facts"] == []
    assert body["registry"]["facts_for_service"] == 0
    assert b"notion" not in db_path.read_bytes()
    assert b"secret-project" not in db_path.read_bytes()


def test_query_string_of_a_registered_target_is_never_stored(client, db_path, rows):
    url = STRIPE_PI + "?client_secret=pi_123_secret_456&expand=customer"
    client.post("/v0/check", json={"target": {"method": "POST", "url": url}})
    assert rows() == 1
    data = db_path.read_bytes()
    assert b"client_secret" not in data and b"expand" not in data
