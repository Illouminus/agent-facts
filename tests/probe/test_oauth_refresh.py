"""OAuth refresh-token grants for probes (Salesforce sfdx auth URLs): parsing, the token request,
where the probe may then send its requests. No real network."""

import json

import httpx
import pytest
from probe_builders import make_service
from werkzeug import Request, Response

from agentfacts.probe.google_sa import AuthError
from agentfacts.probe.http import make_client
from agentfacts.probe.oauth_refresh import (
    instance_base_url,
    parse_auth_url,
    refresh_access_token,
    secrets_of,
    token_url,
)

# Fake tokens split in two: a literal in vendor shape trips GitHub push protection.
REFRESH = "5A" "ep861FAKErefreshFAKErefreshFAKErefresh.FAKE_refresh0123456789"
RAW = f"force://PlatformCLI::{REFRESH}@acme-dev-ed.develop.my.salesforce.com"
ACCESS = "00D" "FAKEfake000000!AQEAQFAKEaccessFAKEaccessFAKEaccess.FAKE_0123"
SF = {"kind": "oauth_refresh_token", "key_name": "acme-test", "env": "sandbox",
      "token_path": "/services/oauth2/token",
      "instance_hosts": ["my.salesforce.com", "login.salesforce.com"]}


def sf_service(**overrides):
    # Tenant domains are instance_hosts only: service hosts stay what check() matches exactly.
    return make_service(auth=SF, hosts=["login.salesforce.com"],
                        surfaces={"http": {"base_url": "https://login.salesforce.com",
                                           "templates": [{"method": "GET", "path": "/v1/items"}]}},
                        dimensions={"env": {"sandbox": "https://login.salesforce.com"}},
                        **overrides)


def test_an_sfdx_auth_url_parses():
    grant = parse_auth_url(RAW)
    assert (grant.client_id, grant.client_secret, grant.refresh_token, grant.host) == (
        "PlatformCLI", "", REFRESH, "acme-dev-ed.develop.my.salesforce.com")


def test_a_client_secret_is_kept():
    grant = parse_auth_url(f"force://Cid:s3cret:{REFRESH}@acme.my.salesforce.com")
    assert grant.client_secret == "s3cret"


@pytest.mark.parametrize("raw", [
    "", "not a url", f"https://PlatformCLI::{REFRESH}@acme.my.salesforce.com",
    f"force://PlatformCLI:{REFRESH}@acme.my.salesforce.com",  # two fields only
    "force://PlatformCLI::@acme.my.salesforce.com",  # no refresh token
    f"force://PlatformCLI::{REFRESH}",  # no host
    f"force://PlatformCLI::{REFRESH}@acme.my.salesforce.com/path",
    f"force://PlatformCLI::{REFRESH}@acme.my.salesforce.com:8443",
    f"force://:: {REFRESH}@acme.my.salesforce.com",
])
def test_bad_auth_urls_are_refused_without_their_content(raw):
    with pytest.raises(AuthError) as exc:
        parse_auth_url(raw)
    assert exc.value.code == "bad_key_file" and REFRESH not in str(exc.value)


def test_secrets_cover_the_url_and_the_refresh_token():
    found = secrets_of(RAW)
    assert {RAW, REFRESH} <= found
    assert secrets_of(f"force://Cid:s3cret:{REFRESH}@acme.my.salesforce.com") >= {"s3cret"}
    assert secrets_of("garbage") == {"garbage"}


def test_the_token_url_is_on_the_key_host_and_the_instance_hosts():
    service = sf_service()
    assert token_url(service, parse_auth_url(RAW)) == (
        "https://acme-dev-ed.develop.my.salesforce.com/services/oauth2/token")
    elsewhere = parse_auth_url(f"force://PlatformCLI::{REFRESH}@collector.example.org")
    with pytest.raises(AuthError) as exc:
        token_url(service, elsewhere)
    assert exc.value.code == "foreign_host"
    # Service hosts alone do not admit a key host: login.salesforce.com is not an instance host.
    narrow = sf_service().model_copy(update={"auth": sf_service().auth.model_copy(
        update={"instance_hosts": ("my.salesforce.com",)})})
    with pytest.raises(AuthError):
        token_url(narrow, parse_auth_url(f"force://PlatformCLI::{REFRESH}@login.salesforce.com"))


@pytest.mark.parametrize(("instance", "expected"), [
    ("https://acme-dev-ed.develop.my.salesforce.com", "https://acme-dev-ed.develop.my.salesforce.com"),
    ("https://acme.my.salesforce.com/", "https://acme.my.salesforce.com"),
    ("http://acme.my.salesforce.com", None),
    ("https://collector.example.org", None),
    ("https://acme.my.salesforce.com.example.org", None),
    ("https://user@acme.my.salesforce.com", None),
    ("https://acme.my.salesforce.com/services", None),
    (None, None),
])
def test_instance_url_must_be_an_https_origin_on_the_instance_hosts(instance, expected):
    if expected is None:
        with pytest.raises(AuthError) as exc:
            instance_base_url(sf_service(), instance)
        assert exc.value.code == "foreign_instance"
    else:
        assert instance_base_url(sf_service(), instance) == expected


def test_refresh_posts_the_grant_and_returns_token_and_instance(httpserver):
    seen = []

    def token(request: Request) -> Response:
        seen.append(dict(request.form))
        body = {"access_token": ACCESS, "instance_url": "https://acme.my.salesforce.com",
                "token_type": "Bearer"}
        return Response(json.dumps(body), 200, content_type="application/json")

    httpserver.expect_request("/services/oauth2/token", method="POST").respond_with_handler(token)
    with make_client() as client:
        result = refresh_access_token(client, parse_auth_url(RAW),
                                      httpserver.url_for("/services/oauth2/token"))
    assert result == (ACCESS, "https://acme.my.salesforce.com")
    assert seen == [{"grant_type": "refresh_token", "client_id": "PlatformCLI",
                     "refresh_token": REFRESH}]  # no client_secret when it is empty


def test_a_client_secret_is_sent_when_there_is_one(httpserver):
    seen = []
    httpserver.expect_request("/t").respond_with_handler(
        lambda r: seen.append(dict(r.form)) or Response(
            '{"access_token": "x", "instance_url": "https://a.my.salesforce.com"}', 200))
    with make_client() as client:
        refresh_access_token(client, parse_auth_url(f"force://Cid:s3cret:{REFRESH}@a.my.salesforce.com"),
                             httpserver.url_for("/t"))
    assert seen[0]["client_secret"] == "s3cret"


@pytest.mark.parametrize(("status", "body", "detail"), [
    (400, '{"error": "invalid_grant", "error_description": "expired access/refresh token"}',
     "400 invalid_grant"),
    (200, '{"instance_url": "https://a.my.salesforce.com"}', "200 no access_token"),
    (500, "oops", "500"),
])
def test_refresh_failures_are_auth_errors(httpserver, status, body, detail):
    httpserver.expect_request("/t").respond_with_data(body, status=status)
    with make_client() as client, pytest.raises(AuthError) as exc:
        refresh_access_token(client, parse_auth_url(RAW), httpserver.url_for("/t"))
    assert (exc.value.code, exc.value.message) == ("token_exchange", detail)


def test_refresh_transport_error_is_an_auth_error():
    with httpx.Client(timeout=1.0, trust_env=False) as client, pytest.raises(AuthError) as exc:
        refresh_access_token(client, parse_auth_url(RAW), "http://127.0.0.1:9/t")
    assert (exc.value.code, exc.value.message) == ("token_exchange", "connect_error")
