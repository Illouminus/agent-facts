"""GET endpoints (spec 03 § Read endpoints) and the rate limit as the caller sees it."""

from api_fixtures import IDEMPOTENCY_ID, STRIPE_PI

CHECK = {"target": {"method": "POST", "url": STRIPE_PI}, "error": {"status": 429}}


def test_facts_of_a_service(client):
    r = client.get("/v0/facts/stripe")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "public, max-age=300"
    assert r.headers["etag"].startswith('"')
    body = r.json()
    assert body["service"] == "stripe"
    assert [f["id"] for f in body["facts"]] == [
        "af:stripe:customer-not-found",
        IDEMPOTENCY_ID,
        "af:stripe:old-sdk-bad-request",
        "af:stripe:payment-intents-429",
    ]  # the retracted one is not listed
    assert all(f["fixes_rendered"] for f in body["facts"])
    assert body["registry"] == {"version": "2026-10-22", "facts_for_service": 4,
                                "license": "CC-BY-4.0"}


def test_etag_round_trip(client):
    etag = client.get("/v0/facts/stripe").headers["etag"]
    r = client.get("/v0/facts/stripe", headers={"If-None-Match": etag})
    assert r.status_code == 304 and r.content == b""
    assert r.headers["etag"] == etag
    assert client.get("/v0/facts/stripe", headers={"If-None-Match": f"W/{etag}"}).status_code == 304
    assert client.get("/v0/facts/stripe", headers={"If-None-Match": '"x"'}).status_code == 200


def test_unknown_service(client):
    r = client.get("/v0/facts/nope")
    assert r.status_code == 404
    assert r.json() == {"error": {"code": "unknown_service", "message": "no service nope",
                                  "field": None}}


def test_one_fact(client):
    r = client.get("/v0/facts/stripe/idempotency-key-reuse-different-params")
    assert r.status_code == 200 and r.headers["etag"]
    assert r.json()["id"] == IDEMPOTENCY_ID
    assert client.get("/v0/facts/stripe/withdrawn").json()["status"] == "retracted"
    r = client.get("/v0/facts/stripe/missing")
    assert r.status_code == 404 and r.json()["error"]["code"] == "unknown_fact"


def test_services(client):
    r = client.get("/v0/services")
    assert r.status_code == 200 and r.headers["cache-control"] == "public, max-age=300"
    assert r.json() == {
        "services": [
            {"key": "pypi", "name": "PyPI", "hosts": ["pypi.org"], "instance_hosts": [],
             "templates": 1, "facts": 0},
            {"key": "stripe", "name": "Stripe", "hosts": ["api.stripe.com"], "instance_hosts": [],
             "templates": 2, "facts": 4},
        ],
        "registry": {"version": "2026-10-22", "license": "CC-BY-4.0"},
    }


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "registry_version": "2026-10-22", "probes_last_run": None}


# ── rate limits through the app ─────────────────────────────────────────────────────────────────


class Clock:
    now = 0.0

    def __call__(self) -> float:
        return self.now


def test_per_network_limit_returns_429_with_retry_after(make_client, rows):
    clock = Clock()
    client = make_client(per_net=3, clock=clock)
    for _ in range(3):
        assert client.post("/v0/check", json=CHECK).status_code == 200
    r = client.post("/v0/check", json=CHECK)
    assert r.status_code == 429
    assert r.headers["retry-after"] == "60"
    assert r.json()["error"]["code"] == "rate_limited"
    assert client.post("/v0/check", content=b"garbage").status_code == 429  # before any parse
    assert rows() == 3
    clock.now = 61
    assert client.post("/v0/check", json=CHECK).status_code == 200


def test_global_limit(make_client):
    clock = Clock()
    client = make_client(per_net=100, global_limit=2, clock=clock)
    assert client.post("/v0/check", json=CHECK).status_code == 200
    assert client.post("/v0/check", json=CHECK).status_code == 200
    assert client.post("/v0/check", json=CHECK).status_code == 429


def test_read_endpoints_are_not_rate_limited(make_client):
    client = make_client(per_net=1, clock=Clock())
    for _ in range(5):
        assert client.get("/v0/services").status_code == 200


def test_forwarded_for_is_believed_only_from_a_trusted_proxy(make_client):
    clock = Clock()
    proxy = make_client(peer=("127.0.0.1", 1), per_net=1, clock=clock)
    assert proxy.post("/v0/check", json=CHECK,
                      headers={"X-Forwarded-For": "198.51.100.1"}).status_code == 200
    assert proxy.post("/v0/check", json=CHECK,
                      headers={"X-Forwarded-For": "203.0.113.1"}).status_code == 200
    assert proxy.post("/v0/check", json=CHECK,
                      headers={"X-Forwarded-For": "198.51.7.7"}).status_code == 429  # same /16
    direct = make_client(peer=("192.0.2.1", 1), per_net=1, clock=clock)
    assert direct.post("/v0/check", json=CHECK,
                       headers={"X-Forwarded-For": "198.51.100.1"}).status_code == 200
    assert direct.post("/v0/check", json=CHECK,
                       headers={"X-Forwarded-For": "203.0.113.9"}).status_code == 429
