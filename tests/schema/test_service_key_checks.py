"""Service checks added for the probe runner (W2): where a key may be sent is decided in CI too."""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from agentfacts.schema.models import Auth
from agentfacts.schema.registry import key_bound_to_service
from agentfacts.schema.validate import validate_paths

SERVICE = (Path(__file__).parents[1] / "fixtures" / "valid" / "service-stripe.yaml").read_text(
    encoding="utf-8"
)


def codes(tmp_path: Path, text: str) -> set[str]:
    path = tmp_path / "services" / "stripe.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return {p.code for p in validate_paths([path], root=tmp_path).problems}


def swap(old: str, new: str) -> str:
    assert old in SERVICE, old
    return SERVICE.replace(old, new)


def test_fixture_service_is_clean(tmp_path):
    assert codes(tmp_path, SERVICE) == set()


@pytest.mark.parametrize("name", ["stripe", "stripe-test", "stripe_live"])
def test_key_named_after_the_service(tmp_path, name):
    assert codes(tmp_path, swap("key_name: stripe-test", f"key_name: {name}")) == set()


@pytest.mark.parametrize("name", ["github-test", "stripes-test", "test-stripe"])
def test_key_not_bound_to_the_service(tmp_path, name):
    assert codes(tmp_path, swap("key_name: stripe-test", f"key_name: {name}")) == {"key_not_bound"}


def test_env_url_must_be_on_a_service_host(tmp_path):
    text = swap("sandbox: https://api.stripe.com}", "sandbox: https://evil.example.org}")
    assert codes(tmp_path, text) == {"foreign_env_url"}


def test_base_url_must_be_on_a_service_host(tmp_path):
    text = swap("base_url: https://api.stripe.com", "base_url: https://evil.example.org")
    assert codes(tmp_path, text) == {"foreign_env_url"}


def test_binding_rule():
    assert key_bound_to_service("acme", "acme")
    assert key_bound_to_service("acme-test", "acme")
    assert not key_bound_to_service("acmecorp", "acme")


PATH_PREFIX = (
    'auth: {kind: path_prefix, key_name: stripe-test, env: sandbox, path_prefix: "/bot{key}"}'
)
SERVICE_ACCOUNT = (
    "auth: {kind: google_service_account, key_name: stripe-test, env: sandbox,"
    " scopes: [https://www.googleapis.com/auth/datastore]}"
)
OAUTH = (
    "auth: {kind: oauth_refresh_token, key_name: stripe-test, env: sandbox,"
    " token_path: /services/oauth2/token}"
)
VALID_AUTH = [
    OAUTH,
    PATH_PREFIX,
    PATH_PREFIX.replace("/bot{key}", "/v1/{key}"),
    PATH_PREFIX.replace("/bot{key}", "/{key}"),
    SERVICE_ACCOUNT,
    SERVICE_ACCOUNT.replace(
        "datastore]", "spreadsheets.readonly, https://www.googleapis.com/auth/calendar.readonly]"
    ),
]
INVALID_AUTH = [
    OAUTH.replace(", token_path: /services/oauth2/token", ""),
    OAUTH.replace("/services/oauth2/token", "services/oauth2/token"),
    OAUTH.replace("/services/oauth2/token", "/services/../token"),
    OAUTH.replace("/services/oauth2/token", '"/services/oauth2/token?x=1"'),
    PATH_PREFIX.replace('path_prefix: "/bot{key}"', "token_path: /services/oauth2/token"),
    PATH_PREFIX.replace(', path_prefix: "/bot{key}"', ""),
    PATH_PREFIX.replace("/bot{key}", "/bot"),  # the key must be in the prefix
    PATH_PREFIX.replace("/bot{key}", "/{key}/x"),  # and end it: the template follows
    PATH_PREFIX.replace("/bot{key}", "bot{key}"),
    PATH_PREFIX.replace("/bot{key}", "/b?t{key}"),
    PATH_PREFIX.replace("/bot{key}", "/{key}{key}"),
    PATH_PREFIX.replace("/bot{key}", "/../{key}"),  # no dot segment before the key
    PATH_PREFIX.replace("/bot{key}", "/v1/./{key}"),
    SERVICE_ACCOUNT.replace(", scopes: [https://www.googleapis.com/auth/datastore]", ""),
    SERVICE_ACCOUNT.replace("[https://www.googleapis.com/auth/datastore]", "[]"),
    SERVICE_ACCOUNT.replace("https://www.googleapis.com/auth/", "https://evil.example/auth/"),
    SERVICE_ACCOUNT.replace("datastore", "data store"),
    PATH_PREFIX.replace('path_prefix: "/bot{key}"', "scopes: [https://www.googleapis.com/auth/x]"),
]


def with_auth(auth: str) -> str:
    """The fixture service with its block `auth:` replaced by a one-line flow mapping."""
    start = SERVICE.index("auth:\n")
    end = SERVICE.index("tos:\n")
    return SERVICE[:start] + auth + "\n" + SERVICE[end:]


@pytest.mark.parametrize("auth", VALID_AUTH)
def test_path_prefix_and_service_account_kinds(tmp_path, auth):
    assert codes(tmp_path, with_auth(auth)) == set()


@pytest.mark.parametrize("auth", INVALID_AUTH)
def test_new_kinds_need_their_own_fields(tmp_path, auth):
    found = codes(tmp_path, with_auth(auth))
    assert found and found <= {"schema_required", "schema_pattern", "schema_minItems",
                               "schema_not"}, found


@pytest.mark.parametrize(
    "field", ['path_prefix: "/bot{key}"', "scopes: [https://www.googleapis.com/auth/x]"]
)
def test_kind_fields_are_refused_on_other_kinds(tmp_path, field):
    auth = f"auth: {{kind: bearer, key_name: stripe-test, env: sandbox, {field}}}"
    assert codes(tmp_path, with_auth(auth)) == {"schema_not"}


@pytest.mark.parametrize(
    ("auth", "ok"), [(a, True) for a in VALID_AUTH] + [(a, False) for a in INVALID_AUTH]
)
def test_model_agrees_with_the_schema(auth, ok):
    doc = yaml.safe_load(auth)["auth"]
    if ok:
        Auth.model_validate(doc)
    else:
        with pytest.raises(ValidationError):
            Auth.model_validate(doc)


@pytest.mark.parametrize(
    ("key", "service", "hosts", "bound"),
    [
        # A family key (google-…) serves google-<x> services whose hosts all sit on googleapis.com.
        ("google-api-key", "google-sheets", ["sheets.googleapis.com"], True),
        ("google-service-account", "google-firestore", ["firestore.googleapis.com"], True),
        ("google-api-key", "google-calendar", ["www.googleapis.com"], True),
        ("google-api-key", "google-sheets", ["sheets.googleapis.com", "evil.example"], False),
        ("google-api-key", "google-sheets", ["googleapis.com.evil.example"], False),
        ("google-api-key", "google-sheets", ["evilgoogleapis.com"], False),
        ("google-api-key", "google-sheets", [], False),
        ("google-api-key", "googlesheets", ["sheets.googleapis.com"], False),  # not google-<x>
        ("google-api-key", "github", ["api.github.com"], False),
        ("stripe-test", "stripe-terminal", ["api.stripe.com"], False),  # stripe is no family
        ("stripe-terminal-test", "stripe-terminal", [], True),  # the name rule, hosts unused
        ("github-token", "google-sheets", ["sheets.googleapis.com"], False),  # no such family
        # A family key obeys the family hosts even when the name rule alone would bind it.
        ("google-api-key", "google", ["collector.example.org"], False),
        ("google-api-key", "google-api", ["collector.example.org"], False),
        ("google-api-key", "google", ["sheets.googleapis.com"], True),
        # Only the listed API hosts, not every googleapis.com host (storage serves user buckets).
        ("google-api-key", "google-storage", ["storage.googleapis.com"], False),
        ("google-api-key", "google-sheets", ["evil.sheets.googleapis.com"], False),
    ],
)
def test_key_families(key, service, hosts, bound):
    assert key_bound_to_service(key, service, hosts) is bound


GOOGLE_SHEETS = """key: google-sheets
name: Google Sheets API
hosts: [sheets.googleapis.com]
surfaces:
  http:
    base_url: https://sheets.googleapis.com
    templates:
      - {method: GET, path: "/v4/spreadsheets/{id}"}
dimensions:
  env: {prod: https://sheets.googleapis.com}
auth: {kind: query, key_name: google-api-key, env: prod, param_name: key}
tos: {automated_access: allowed, publish_measurements: allowed, source: https://developers.google.com/terms}
"""


def google_codes(tmp_path: Path, text: str) -> set[str]:
    path = tmp_path / "services" / "google-sheets.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return {p.code for p in validate_paths([path], root=tmp_path).problems}


def test_validator_accepts_a_family_key_on_family_hosts(tmp_path):
    assert google_codes(tmp_path, GOOGLE_SHEETS) == set()


def test_validator_refuses_a_family_key_with_a_host_off_the_family_domain(tmp_path):
    text = GOOGLE_SHEETS.replace("hosts: [sheets.googleapis.com]",
                                 "hosts: [sheets.googleapis.com, collector.example.org]")
    assert google_codes(tmp_path, text) == {"key_not_bound"}


@pytest.mark.parametrize(
    ("scopes", "bound"),
    [
        ((), True),
        (("https://www.googleapis.com/auth/spreadsheets.readonly",), True),
        (("https://www.googleapis.com/auth/calendar.readonly",
          "https://www.googleapis.com/auth/datastore"), True),
        (("https://www.googleapis.com/auth/cloud-platform",), False),
        (("https://www.googleapis.com/auth/spreadsheets",), False),  # write scope
        (("https://www.googleapis.com/auth/spreadsheets.readonly",
          "https://www.googleapis.com/auth/drive"), False),
    ],
)
def test_family_service_accounts_get_only_the_family_scopes(scopes, bound):
    hosts = ["sheets.googleapis.com"]
    assert key_bound_to_service("google-service-account", "google-sheets", hosts, scopes) is bound


def test_validator_refuses_a_family_service_account_with_a_broad_scope(tmp_path):
    text = GOOGLE_SHEETS.replace(
        "auth: {kind: query, key_name: google-api-key, env: prod, param_name: key}",
        "auth: {kind: google_service_account, key_name: google-service-account, env: prod,"
        " scopes: [https://www.googleapis.com/auth/cloud-platform]}",
    )
    assert google_codes(tmp_path, text) == {"key_not_bound"}
