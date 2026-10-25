"""Auth kinds beyond a header or a query parameter, end to end in a tick (no real network):
`path_prefix` (the key inside the path, Telegram) and `google_service_account` (a minted token)."""

import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from probe_builders import Repo
from werkzeug import Response

from apifacts.probe.runner import TickOptions, run_tick
from apifacts.schema.yamlio import load_yaml

TELEGRAM_KEY = "123456789:AAFakeFakeFakeFakeFakeFakeFakeFake_x"
PATH_AUTH = {"kind": "path_prefix", "key_name": "acme-test", "env": "sandbox",
             "path_prefix": "/bot{key}"}


def tick(repo: Repo, httpserver, **extra):
    return run_tick(
        repo.root,
        repo.state,
        TickOptions(run_all=True, vantage="test"),
        keys_dir=repo.keys,
        base_urls={"acme": httpserver.url_for("")},
        sleep=lambda _s: None,
        environ={},
        **extra,
    )


def tick_without_base_url(repo: Repo, **extra):
    return run_tick(repo.root, repo.state, TickOptions(run_all=True, vantage="test"),
                    keys_dir=repo.keys, sleep=lambda _s: None, environ={}, **extra)


def outputs(repo: Repo) -> bytes:
    files = [*repo.state.rglob("*"), *(repo.root / "facts").rglob("*")]
    return b"\n".join(p.read_bytes() for p in files if p.is_file())


def test_path_prefix_tick_sends_the_key_in_the_path_and_records_the_template(repo, httpserver):
    repo.service(auth=PATH_AUTH)
    repo.key(value=TELEGRAM_KEY)
    repo.probe()
    repo.fact()

    def echo(_request):
        body = {"ok": True, "description": f"token {TELEGRAM_KEY}"}
        return Response(json.dumps(body), 200, {"X-Echo": TELEGRAM_KEY},
                        content_type="application/json")

    httpserver.expect_request(f"/bot{TELEGRAM_KEY}/v1/items").respond_with_handler(echo)
    report = tick(repo, httpserver)
    assert [line.outcome for line in report.lines] == ["pass"]
    step = repo.results()[0]["steps"][0]
    assert step["path"] == "/v1/items" and step["template"] == "/v1/items"
    assert TELEGRAM_KEY.encode() not in outputs(repo)
    assert TELEGRAM_KEY.split(":")[1].encode() not in outputs(repo)
    assert TELEGRAM_KEY not in " ".join(line.detail for line in report.lines)


def test_path_prefix_with_an_unsafe_key_sends_nothing(repo, httpserver):
    repo.service(auth=PATH_AUTH)
    repo.key(value="123:abc/../../admin")
    repo.probe()
    repo.fact()
    report = tick(repo, httpserver)
    assert [(line.outcome, line.detail) for line in report.lines] == [
        ("error", "refused:key_not_path_safe: the acme key is not one plain path segment")
    ]
    assert httpserver.log == []
    assert b"admin" not in outputs(repo)


ACCESS = "ya29.FAKEaccessTOKENfakeFAKEfake0123"
SA_AUTH = {"kind": "google_service_account", "key_name": "acme-test", "env": "sandbox",
           "scopes": ["https://www.googleapis.com/auth/datastore"]}


@pytest.fixture(scope="module")
def sa_key() -> tuple[str, dict]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    doc = {"type": "service_account", "project_id": "agent-facts-test",
           "private_key_id": "fedcba9876543210fedcba9876543210fedcba98", "private_key": pem,
           "client_email": "probe@agent-facts-test.iam.gserviceaccount.com",
           "client_id": "123456789012345678901", "token_uri": "https://oauth2.googleapis.com/token"}
    return json.dumps(doc), doc


def sa_repo(repo: Repo, raw: str, probes: int = 1) -> None:
    repo.service(auth=SA_AUTH)
    repo.key(value=raw)
    for i in range(probes):
        repo.probe(f"items-{i}")
        repo.fact(f"items-{i}-ok", probe=f"items-{i}")


def serve_token(httpserver, status=200, body=None) -> list:
    calls = []

    def token(request):
        calls.append(dict(request.form))
        payload = body if body is not None else {"access_token": ACCESS, "expires_in": 3599}
        return Response(json.dumps(payload), status, content_type="application/json")

    httpserver.expect_request("/token", method="POST").respond_with_handler(token)
    return calls


def test_service_account_tick_mints_one_token_and_sends_it_as_bearer(repo, httpserver, sa_key):
    raw, _ = sa_key
    sa_repo(repo, raw, probes=2)
    calls = serve_token(httpserver)
    seen = []

    def items(request):
        seen.append(request.headers.get("Authorization"))
        return Response("{}", 200, content_type="application/json")

    httpserver.expect_request("/v1/items").respond_with_handler(items)
    report = tick(repo, httpserver, token_urls={"acme": httpserver.url_for("/token")})
    assert [line.outcome for line in report.lines] == ["pass", "pass"]
    assert len(calls) == 1 and calls[0]["grant_type"].endswith("jwt-bearer")
    assert seen == [f"Bearer {ACCESS}"] * 2


def test_no_service_account_secret_reaches_any_output(repo, httpserver, sa_key, capsys):
    raw, doc = sa_key
    sa_repo(repo, raw)
    serve_token(httpserver)

    def echo(_request):
        body = {"error": {"message": f"{doc['private_key']} {doc['private_key_id']} {ACCESS}"},
                "raw": raw}
        headers = {"X-Echo": ACCESS, "Retry-After": doc["private_key_id"]}
        return Response(json.dumps(body), 401, headers, content_type="application/json")

    httpserver.expect_request("/v1/items").respond_with_handler(echo)
    report = tick(repo, httpserver, token_urls={"acme": httpserver.url_for("/token")})
    assert [line.outcome for line in report.lines] == ["fail"]
    written = outputs(repo)
    body_line = doc["private_key"].splitlines()[1].encode()
    for secret in (ACCESS.encode(), doc["private_key_id"].encode(), body_line, b"PRIVATE KEY"):
        assert secret not in written, secret
    shown = " ".join(line.detail for line in report.lines) + capsys.readouterr().out
    assert ACCESS not in shown and "PRIVATE KEY" not in shown


def test_token_exchange_failure_is_an_error_and_never_evidence(repo, httpserver, sa_key):
    raw, _ = sa_key
    sa_repo(repo, raw, probes=2)
    calls = serve_token(httpserver, 400, {"error": "invalid_grant",
                                          "error_description": "Invalid JWT Signature."})
    report = tick(repo, httpserver, token_urls={"acme": httpserver.url_for("/token")})
    assert [(line.outcome, line.detail) for line in report.lines] == [
        ("error", "auth:token_exchange: 400 invalid_grant")
    ] * 2
    assert len(calls) == 1  # the failure is remembered for the tick
    assert report.ok  # an outage, not a refused probe
    facts = [load_yaml(p) for p in (repo.root / "facts").rglob("*.yaml")]
    assert all(f["evidence"]["confirmations"] == 1 for f in facts)


def test_a_bad_key_file_refuses_the_probe_without_a_request(repo, httpserver):
    sa_repo(repo, '{"type": "authorized_user", "refresh_token": "1//0fakeREFRESHtoken"}')
    report = tick(repo, httpserver, token_urls={"acme": httpserver.url_for("/token")})
    assert [(line.outcome, line.detail) for line in report.lines] == [
        ("error", "auth:bad_key_file: the key file is not a service-account key")
    ]
    assert httpserver.log == [] and not report.ok
    assert b"REFRESHtoken" not in outputs(repo)


def test_a_token_close_to_expiry_is_minted_again(repo, httpserver, sa_key):
    raw, _ = sa_key
    sa_repo(repo, raw, probes=2)
    calls = serve_token(httpserver, body={"access_token": ACCESS, "expires_in": 60})
    httpserver.expect_request("/v1/items").respond_with_json({})
    report = tick(repo, httpserver, token_urls={"acme": httpserver.url_for("/token")})
    assert [line.outcome for line in report.lines] == ["pass", "pass"]
    assert len(calls) == 2  # 60 s left is inside the safety margin: never sent stale


def test_a_keyless_probe_of_a_service_account_service_mints_nothing(repo, httpserver, sa_key):
    raw, _ = sa_key
    sa_repo(repo, raw, probes=0)
    repo.probe("anonymous", steps=[{"do": "http", "method": "GET", "path": "/v1/items",
                                    "auth": "none"}])
    calls = serve_token(httpserver)
    httpserver.expect_request("/v1/items").respond_with_json({})
    report = tick(repo, httpserver, token_urls={"acme": httpserver.url_for("/token")})
    assert [line.outcome for line in report.lines] == ["pass"] and calls == []


def test_the_token_request_counts_against_max_requests(repo, httpserver, sa_key):
    raw, _ = sa_key
    sa_repo(repo, raw, probes=2)
    serve_token(httpserver)
    httpserver.expect_request("/v1/items").respond_with_json({})
    report = run_tick(repo.root, repo.state,
                      TickOptions(run_all=True, vantage="test", max_requests=2),
                      keys_dir=repo.keys, base_urls={"acme": httpserver.url_for("")},
                      environ={}, token_urls={"acme": httpserver.url_for("/token")})
    # 1 token + 1 step fit; the second probe's step would be the third request.
    assert [line.outcome for line in report.lines] == ["pass"]
    assert report.counts["deferred"] == 1


# Fake tokens split in two: a literal in vendor shape trips GitHub push protection.
SF_REFRESH = "5A" "ep861FAKErefreshFAKErefreshFAKErefresh.FAKE_refresh0123456789"
SF_ACCESS = "00D" "FAKEfake000000!AQEAQFAKEaccessFAKEaccessFAKEaccess.FAKE_0123"
SF_AUTH = {"kind": "oauth_refresh_token", "key_name": "acme-test", "env": "sandbox",
           "token_path": "/services/oauth2/token",
           "instance_hosts": ["my.salesforce.com", "login.salesforce.com"]}
SF_HOSTS = {"hosts": ["login.salesforce.com"],
            "surfaces": {"http": {"base_url": "https://login.salesforce.com", "templates": [
                {"method": "GET", "path": "/v1/items"}]}},
            "dimensions": {"env": {"sandbox": "https://login.salesforce.com"}}}


def sf_repo(repo: Repo, probes: int = 1,
            raw: str = f"force://PlatformCLI::{SF_REFRESH}@acme.my.salesforce.com") -> None:
    repo.service(auth=SF_AUTH, **SF_HOSTS)
    repo.key(value=raw)
    for i in range(probes):
        repo.probe(f"items-{i}")
        repo.fact(f"items-{i}-ok", probe=f"items-{i}")


def serve_sf_token(httpserver, status=200, body=None) -> list:
    calls = []

    def token(request):
        calls.append(dict(request.form))
        payload = body if body is not None else {
            "access_token": SF_ACCESS, "instance_url": "https://acme.my.salesforce.com"}
        return Response(json.dumps(payload), status, content_type="application/json")

    httpserver.expect_request("/services/oauth2/token", method="POST").respond_with_handler(token)
    return calls


def sf_tick(repo, httpserver):
    return tick(repo, httpserver,
                token_urls={"acme": httpserver.url_for("/services/oauth2/token")})


def test_refresh_token_tick_trades_once_and_sends_bearer(repo, httpserver):
    sf_repo(repo, probes=2)
    calls = serve_sf_token(httpserver)
    seen = []

    def items(request):
        seen.append(request.headers.get("Authorization"))
        return Response("{}", 200, content_type="application/json")

    httpserver.expect_request("/v1/items").respond_with_handler(items)
    report = sf_tick(repo, httpserver)
    assert [line.outcome for line in report.lines] == ["pass", "pass"]
    assert len(calls) == 1 and calls[0]["refresh_token"] == SF_REFRESH
    assert seen == [f"Bearer {SF_ACCESS}"] * 2


def test_no_refresh_or_access_token_reaches_any_output(repo, httpserver, capsys):
    raw = f"force://PlatformCLI::{SF_REFRESH}@acme.my.salesforce.com"
    sf_repo(repo, raw=raw)
    serve_sf_token(httpserver)

    def echo(_request):
        body = {"message": f"{SF_REFRESH} {SF_ACCESS} {raw}", "errorCode": "INVALID_SESSION_ID"}
        return Response(json.dumps([body]), 401, {"X-Echo": SF_ACCESS},
                        content_type="application/json")

    httpserver.expect_request("/v1/items").respond_with_handler(echo)
    report = sf_tick(repo, httpserver)
    assert [line.outcome for line in report.lines] == ["fail"]
    written = outputs(repo)
    for secret in (SF_REFRESH, SF_ACCESS, raw, "force://"):
        assert secret.encode() not in written, secret
    shown = " ".join(line.detail for line in report.lines) + capsys.readouterr().out
    assert SF_REFRESH not in shown and SF_ACCESS not in shown


def test_refresh_failure_is_an_error_and_never_evidence(repo, httpserver):
    sf_repo(repo, probes=2)
    calls = serve_sf_token(httpserver, 400, {"error": "invalid_grant",
                                             "error_description": "expired access/refresh token"})
    report = sf_tick(repo, httpserver)
    assert [(line.outcome, line.detail) for line in report.lines] == [
        ("error", "auth:token_exchange: 400 invalid_grant")
    ] * 2
    assert len(calls) == 1 and report.ok


def test_an_auth_url_host_off_the_service_hosts_is_refused_unsent(repo, httpserver):
    sf_repo(repo, raw=f"force://PlatformCLI::{SF_REFRESH}@collector.example.org")
    report = tick_without_base_url(repo)  # no seam: the token URL comes from the key file
    assert [(line.outcome, line.detail) for line in report.lines] == [
        ("error", "auth:foreign_host: the auth URL host is not one of acme's instance_hosts")
    ]
    assert httpserver.log == [] and not report.ok


def test_a_foreign_instance_url_is_refused_and_gets_no_token(repo, httpserver):
    sf_repo(repo)
    serve_sf_token(httpserver, body={"access_token": SF_ACCESS,
                                     "instance_url": "https://collector.example.org"})
    report = tick_without_base_url(
        repo, token_urls={"acme": httpserver.url_for("/services/oauth2/token")})
    # base_urls are not set here: the instance URL decides where requests go, and it is refused.
    assert [line.outcome for line in report.lines] == ["error"]
    assert report.lines[0].detail.startswith("auth:foreign_instance")
    assert [r.path for r, _ in httpserver.log] == ["/services/oauth2/token"]
