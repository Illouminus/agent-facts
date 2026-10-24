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
VALID_AUTH = [
    PATH_PREFIX,
    PATH_PREFIX.replace("/bot{key}", "/v1/{key}"),
    PATH_PREFIX.replace("/bot{key}", "/{key}"),
    SERVICE_ACCOUNT,
    SERVICE_ACCOUNT.replace(
        "datastore]", "spreadsheets.readonly, https://www.googleapis.com/auth/calendar.readonly]"
    ),
]
INVALID_AUTH = [
    PATH_PREFIX.replace(', path_prefix: "/bot{key}"', ""),
    PATH_PREFIX.replace("/bot{key}", "/bot"),  # the key must be in the prefix
    PATH_PREFIX.replace("/bot{key}", "/{key}/x"),  # and end it: the template follows
    PATH_PREFIX.replace("/bot{key}", "bot{key}"),
    PATH_PREFIX.replace("/bot{key}", "/b?t{key}"),
    PATH_PREFIX.replace("/bot{key}", "/{key}{key}"),
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
