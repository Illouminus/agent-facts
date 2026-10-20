"""Service checks added for the probe runner (W2): where a key may be sent is decided in CI too."""

from pathlib import Path

import pytest

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
