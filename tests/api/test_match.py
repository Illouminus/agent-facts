"""Target parsing, template choice, UA classes and reporter networks (spec 03 step 1, 4)."""

import pytest

from agentfacts.api.match import (
    HostTarget,
    Locator,
    UrlTarget,
    best_template,
    classify_ua,
    client_ip,
    network_of,
    parse_proxies,
    parse_target,
    version_in,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        (
            "https://api.stripe.com/v1/payment_intents?key=sk_x#frag",
            UrlTarget("api.stripe.com", "/v1/payment_intents"),
        ),
        ("HTTP://API.Stripe.COM:443/v1/x", UrlTarget("api.stripe.com", "/v1/x")),
        ("api.stripe.com/v1/x", UrlTarget("api.stripe.com", "/v1/x")),
        ("api.stripe.com", HostTarget("api.stripe.com")),
        ("https://api.stripe.com/", HostTarget("api.stripe.com")),
        ("api.stripe.com.", HostTarget("api.stripe.com")),
        ("pypi:stripe@12.1.0", Locator("pypi", "stripe", "12.1.0")),
        ("pypi:stripe", Locator("pypi", "stripe", None)),
        ("npm:@slack/web-api@7.9.0", Locator("npm", "@slack/web-api", "7.9.0")),
        ("npm:@slack/web-api", Locator("npm", "@slack/web-api", None)),
    ],
)
def test_parse_target(raw, expected):
    assert parse_target(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "ftp://api.stripe.com/x",
        "https://user:pw@api.stripe.com/v1/x",
        "https://user@api.stripe.com/v1/x",
        "pypi:",
        "pypi:bad name@1",
        "npm:@scope@1",
        "cargo:serde@1",
        "https://api.stripe.com:99999/x",
        "https:///v1/x",
        "not a host",
        "",
    ],
)
def test_unparseable_targets(raw):
    assert parse_target(raw) is None


TEMPLATES = frozenset(
    {
        ("GET", "/v1/customers/{id}"),
        ("GET", "/v1/customers/search"),
        ("POST", "/v1/customers/{id}"),
        ("POST", "/v1/payment_intents"),
    }
)


def test_literal_template_beats_placeholder():
    found = best_template(TEMPLATES, "GET", "/v1/customers/search")
    assert found == ("GET", "/v1/customers/search")


def test_placeholder_matches_one_segment():
    assert best_template(TEMPLATES, "GET", "/v1/customers/cus_123") == ("GET", "/v1/customers/{id}")
    assert best_template(TEMPLATES, "GET", "/v1/customers/cus_123/x") is None


def test_method_must_match():
    assert best_template(TEMPLATES, "DELETE", "/v1/customers/cus_1") is None
    assert best_template(TEMPLATES, "POST", "/v1/customers/cus_1") == ("POST", "/v1/customers/{id}")


@pytest.mark.parametrize(
    "path", ["/v1/customers/..", "/v1/customers/%2e%2e", "/v1/payment_intents/"]
)
def test_unsafe_or_trailing_paths_do_not_match(path):
    assert best_template(TEMPLATES, "GET", path) is None
    assert best_template(TEMPLATES, "POST", path) is None


@pytest.mark.parametrize(
    "ua, cls",
    [
        ("agentfacts-pytest/0.1.0 python/3.12", "pytest-plugin"),
        ("pytest/8.3", "pytest-plugin"),
        ("@agent-facts/jest 0.1", "jest-plugin"),
        ("vitest-reporter/1", "jest-plugin"),
        ("agentfacts-mcp/0.1", "mcp"),
        ("claude-code-mcp-client", "mcp"),
        ("python-httpx/0.28.1", "sdk"),
        ("python-requests/2.32", "sdk"),
        ("axios/1.7.2", "sdk"),
        ("agentfacts-sdk/0.1", "sdk"),
        ("curl/8.7.1", "other"),
        ("", "other"),
        (None, "other"),
    ],
)
def test_classify_ua(ua, cls):
    assert classify_ua(ua) == cls


@pytest.mark.parametrize(
    "ip, net",
    [
        ("203.0.113.7", "203.0.0.0/16"),
        ("10.1.255.255", "10.1.0.0/16"),
        ("2001:db8:1::5", "2001:db8::/32"),
        ("::ffff:198.51.100.9", "198.51.0.0/16"),
        ("testclient", "unparsed"),
    ],
)
def test_network_of(ip, net):
    assert network_of(ip) == net


TRUSTED = parse_proxies(("127.0.0.1", "::1"))


def test_client_ip_ignores_forwarded_for_from_untrusted_peer():
    assert client_ip("198.51.100.1", "1.2.3.4", TRUSTED) == "198.51.100.1"


def test_client_ip_takes_rightmost_untrusted_hop_behind_proxy():
    assert client_ip("127.0.0.1", "1.2.3.4, 198.51.100.1", TRUSTED) == "198.51.100.1"
    assert client_ip("127.0.0.1", "1.2.3.4, 127.0.0.1", TRUSTED) == "1.2.3.4"


def test_client_ip_behind_proxy_without_header_is_the_proxy():
    assert client_ip("127.0.0.1", None, TRUSTED) == "127.0.0.1"


def test_client_ip_trusts_cidrs():
    assert client_ip("172.18.0.3", "9.9.9.9", parse_proxies([" 172.16.0.0/12 ", ""])) == "9.9.9.9"


def test_bad_proxy_entry_fails_at_startup():
    with pytest.raises(ValueError):
        parse_proxies(["127.0.0.1", "proxy.local"])


@pytest.mark.parametrize(
    "version, constraint, inside",
    [
        ("12.1.0", ">=7,<13", True),
        ("13.0", ">=7,<13", False),
        ("6.9.9", ">=7,<13", False),
        ("12.1.0", "==12.1.0", True),
        ("12.1.1", "==12.1.0", False),
        ("12.1.0", "!=12.1.0", False),
        ("12.1.0rc1", "<12.2", True),
        ("7", ">7", False),
        ("7.0.0", "<=7", True),
        ("7.9.0", "^7.0.0", True),  # unparseable constraint: kept, never hidden
        ("dev", ">=1", True),  # unparseable version: kept
    ],
)
def test_version_in(version, constraint, inside):
    assert version_in(version, constraint) is inside
