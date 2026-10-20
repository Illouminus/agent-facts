"""errors/<hash12>.md stubs: one per distinct normalized string of a published, live fact."""

import hashlib

import pytest

from agentfacts.pages import PagesError, errors_index
from agentfacts.pages.build import load_registry
from agentfacts.pages.errors_index import error_groups, error_hash

IDEMPOTENCY = (
    "keys for idempotent requests can only be used with the same parameters"
    " they were first used with"
)


def test_error_hash_is_sha256_of_the_normalized_string():
    assert error_hash("abc") == hashlib.sha256(b"abc").hexdigest()


def test_groups_by_hash_prefix_and_skips_retracted_and_stringless(fixture_root):
    _, facts = load_registry(fixture_root)
    groups = error_groups(facts)
    assert list(groups) == sorted(groups)
    assert all(len(prefix) == 12 for prefix in groups)
    by_string = {normalized: [f.id for f in group] for normalized, group in groups.values()}
    assert by_string[IDEMPOTENCY] == [
        "af:stripe:idempotency-key-reuse-different-params",
        "af:stripe:idempotency-key-reuse-different-params-sandbox",
    ]
    assert error_hash(IDEMPOTENCY)[:12] in groups
    ids = {i for group in by_string.values() for i in group}
    assert "af:stripe:amount-too-small" not in ids  # retracted
    assert "af:stripe:deleted-customer-returns-200" not in ids  # no normalized string


def test_prefix_collision_is_an_error(fixture_root, monkeypatch):
    _, facts = load_registry(fixture_root)
    monkeypatch.setattr(errors_index, "error_hash", lambda normalized: "0" * 64)
    with pytest.raises(PagesError, match="collision"):
        error_groups(facts)
