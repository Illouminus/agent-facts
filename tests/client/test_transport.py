import json
import time

import pytest
from werkzeug import Response

from agentfacts.client.settings import DEFAULT_ENDPOINT, Settings
from agentfacts.client.transport import CACHE_TTL_S, Client

SERVICES = {
    "services": [
        {"key": "stripe", "hosts": ["api.stripe.com"], "facts": 1},
        {"key": "salesforce", "hosts": ["my.salesforce.com"], "facts": 0},
    ]
}
ANSWER = {"service": "stripe", "facts": [], "registry": {"version": "2026-10-20"}}
PAYLOAD = {
    "target": {"method": "POST", "url": "https://api.stripe.com/v1/payment_intents"},
    "error": {"status": 400},
}


class Clock:
    def __init__(self, now=1_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def make(httpserver, tmp_path, clock):
    def make(**kw):
        kw.setdefault("cache_dir", tmp_path / "cache")
        kw.setdefault("clock", clock)
        return Client(httpserver.url_for("").rstrip("/"), "agentfacts-test/0", **kw)

    return make


def requests_to(httpserver, path):
    return [req for req, _ in httpserver.log if req.path == path]


def test_services_are_fetched_once_and_cached(httpserver, make, tmp_path, clock):
    httpserver.expect_request("/v0/services", method="GET").respond_with_json(SERVICES)
    client = make()
    assert client.registered_host("api.stripe.com") == "api.stripe.com"
    assert client.registered_host("api.github.com") is None
    assert len(requests_to(httpserver, "/v0/services")) == 1
    cached = json.loads((tmp_path / "cache" / "services.json").read_text())
    assert cached["endpoint"] == client.endpoint
    assert cached["fetched_at"] == clock.now
    assert sorted(cached["hosts"]) == ["api.stripe.com", "my.salesforce.com"]

    again = make()  # a new session reads the file, not the network
    assert again.registered_host("api.stripe.com") == "api.stripe.com"
    assert len(requests_to(httpserver, "/v0/services")) == 1


def test_cache_expires_after_24_hours(httpserver, make, clock):
    httpserver.expect_request("/v0/services").respond_with_json(SERVICES)
    make().registered_host("api.stripe.com")
    clock.now += CACHE_TTL_S + 1
    make().registered_host("api.stripe.com")
    assert len(requests_to(httpserver, "/v0/services")) == 2


def test_cache_of_another_endpoint_is_ignored(httpserver, make, tmp_path):
    (tmp_path / "cache").mkdir()
    (tmp_path / "cache" / "services.json").write_text(
        json.dumps(
            {
                "endpoint": "https://other.example",
                "fetched_at": 1_000_000.0,
                "hosts": ["api.github.com"],
            }
        )
    )
    httpserver.expect_request("/v0/services").respond_with_json(SERVICES)
    client = make()
    assert client.registered_host("api.github.com") is None
    assert client.registered_host("api.stripe.com") == "api.stripe.com"


def test_corrupt_cache_is_refetched(httpserver, make, tmp_path):
    (tmp_path / "cache").mkdir()
    (tmp_path / "cache" / "services.json").write_text("{not json")
    httpserver.expect_request("/v0/services").respond_with_json(SERVICES)
    assert make().registered_host("api.stripe.com") == "api.stripe.com"


@pytest.mark.parametrize(
    "answer",
    [
        [{"key": "stripe", "hosts": ["api.stripe.com"]}],
        {"services": {"stripe": {"hosts": ["API.Stripe.com"]}}},
    ],
)
def test_other_services_shapes_are_read(httpserver, make, answer):
    httpserver.expect_request("/v0/services").respond_with_json(answer)
    assert make().registered_host("api.stripe.com") == "api.stripe.com"


def test_subdomain_maps_to_the_registered_host(httpserver, make):
    httpserver.expect_request("/v0/services").respond_with_json(SERVICES)
    client = make()
    assert client.registered_host("acme.my.salesforce.com") == "my.salesforce.com"
    assert client.registered_host("evilmy.salesforce.com") is None
    assert client.registered_host("API.STRIPE.COM") == "api.stripe.com"


@pytest.mark.parametrize(
    "host",
    [
        "localhost",
        "127.0.0.1",
        "db",
        "api.local",
        "x.test",
        "svc.internal",
        "a.localhost",
        "",
        None,
    ],
)
def test_local_hosts_never_ask_the_registry(httpserver, make, host):
    assert make().registered_host(host) is None
    assert httpserver.log == []


def test_unreachable_registry_is_silent_and_empty(tmp_path, clock):
    client = Client("http://127.0.0.1:9", "ua", cache_dir=tmp_path, clock=clock, timeout=0.5)
    assert client.registered_host("api.stripe.com") is None
    assert client.check(PAYLOAD) is None
    assert client.last_error
    assert not (tmp_path / "services.json").exists()


def test_check_posts_json_and_returns_the_answer(httpserver, make):
    httpserver.expect_request("/v0/check", method="POST", json=PAYLOAD).respond_with_json(ANSWER)
    assert make().check(PAYLOAD) == ANSWER
    (req,) = requests_to(httpserver, "/v0/check")
    assert req.headers["User-Agent"] == "agentfacts-test/0"
    assert req.headers["Content-Type"] == "application/json"
    assert "Authorization" not in req.headers and "Cookie" not in req.headers


def test_identical_checks_are_sent_once(httpserver, make):
    httpserver.expect_request("/v0/check").respond_with_json(ANSWER)
    client = make()
    assert client.check(PAYLOAD) == client.check(dict(PAYLOAD)) == ANSWER
    assert len(requests_to(httpserver, "/v0/check")) == 1


def test_checks_per_session_are_capped(httpserver, make):
    httpserver.expect_request("/v0/check").respond_with_json(ANSWER)
    client = make(max_checks=2)
    answers = [
        client.check({"target": {"url": f"https://api.stripe.com/v1/x{i}"}}) for i in range(4)
    ]
    assert answers == [ANSWER, ANSWER, None, None]
    assert len(requests_to(httpserver, "/v0/check")) == 2


@pytest.mark.parametrize(
    "response",
    [
        Response("boom", status=500),
        Response("{not json", status=200, content_type="application/json"),
        Response("[1, 2]", status=200, content_type="application/json"),
        Response("", status=302, headers={"Location": "https://elsewhere.example/v0/check"}),
        Response('{"error": "unknown_field"}', status=400, content_type="application/json"),
        Response("x" * 2_000_000, status=200),
    ],
    ids=["500", "garbage", "not-an-object", "redirect", "400", "oversize"],
)
def test_bad_answers_give_none_and_open_the_breaker(httpserver, make, response):
    httpserver.expect_request("/v0/check").respond_with_response(response)
    client = make()
    assert client.check(PAYLOAD) is None
    assert client.last_error
    assert client.check({"target": {"url": "https://api.stripe.com/v1/other"}}) is None
    assert len(requests_to(httpserver, "/v0/check")) == 1


def test_timeout_gives_none_quickly(httpserver, make):
    def slow(_request):
        time.sleep(0.6)
        return Response("{}", content_type="application/json")

    httpserver.expect_request("/v0/check").respond_with_handler(slow)
    started = time.monotonic()
    assert make(timeout=0.2).check(PAYLOAD) is None
    assert time.monotonic() - started < 0.5


def test_time_budget_stops_further_requests(httpserver, make):
    httpserver.expect_request("/v0/check").respond_with_json(ANSWER)
    client = make(budget_s=0.0)
    assert client.check(PAYLOAD) is None
    assert httpserver.log == []


@pytest.mark.parametrize("endpoint", ["ftp://facts.example", "facts.example", ""])
def test_invalid_endpoint_never_sends(endpoint, tmp_path):
    client = Client(endpoint, "ua", cache_dir=tmp_path)
    assert client.registered_host("api.stripe.com") is None
    assert client.check(PAYLOAD) is None


def test_offline_client_never_touches_the_network(httpserver, make):
    client = make(offline=True)
    assert client.registered_host("api.stripe.com") is None  # packaged snapshot is empty
    answer = client.check(PAYLOAD)
    assert answer["facts"] == []
    assert httpserver.log == []


def test_cache_write_failure_is_ignored(httpserver, tmp_path, clock):
    blocker = tmp_path / "file"
    blocker.write_text("not a directory")
    httpserver.expect_request("/v0/services").respond_with_json(SERVICES)
    client = Client(
        httpserver.url_for("").rstrip("/"), "ua", cache_dir=blocker / "sub", clock=clock
    )
    assert client.registered_host("api.stripe.com") == "api.stripe.com"


def test_settings_from_env(tmp_path):
    assert Settings.from_env({}) == Settings(DEFAULT_ENDPOINT, False, None)
    assert DEFAULT_ENDPOINT == "https://facts.baillot.dev"
    env = {
        "AGENTFACTS_ENDPOINT": "http://localhost:8000/",
        "AGENTFACTS_DISABLE": "1",
        "AGENTFACTS_SNAPSHOT": str(tmp_path),
    }
    assert Settings.from_env(env) == Settings("http://localhost:8000", True, tmp_path)
    for value in ("true", "YES", "on"):
        assert Settings.from_env({"AGENTFACTS_DISABLE": value}).disabled
    for value in ("0", "", "no", "false"):
        assert not Settings.from_env({"AGENTFACTS_DISABLE": value}).disabled
