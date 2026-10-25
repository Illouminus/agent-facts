"""The facts index: what is loaded from services/ and facts/, and the three lookup tiers."""

import logging

from api_fixtures import IDEMPOTENCY_BODY, IDEMPOTENCY_ID

from apifacts.api.facts_index import FactsIndex
from apifacts.api.match import Locator
from apifacts.api.normalize import extract_signal


def _ids(facts) -> list[str]:
    return [f.fact.id for f in facts]


def test_loads_services_and_valid_facts_only(repo, caplog):
    with caplog.at_level(logging.WARNING, logger="apifacts.api"):
        index = FactsIndex.load(repo)
    assert sorted(index.services) == ["pypi", "stripe"]
    stripe = index.services["stripe"]
    assert _ids(stripe.facts) == [
        "af:stripe:customer-not-found",
        IDEMPOTENCY_ID,
        "af:stripe:old-sdk-bad-request",
        "af:stripe:payment-intents-429",
    ]
    assert "broken.yaml" in caplog.text
    assert [p.name for p in index.skipped] == ["broken.yaml"]


def test_retracted_fact_is_reachable_by_slug_only(repo):
    index = FactsIndex.load(repo)
    assert index.fact("stripe", "withdrawn").fact.status == "retracted"
    assert "af:stripe:withdrawn" not in _ids(index.services["stripe"].facts)


def test_document_is_the_yaml_plus_rendered_fixes(repo):
    fact = FactsIndex.load(repo).fact("stripe", "idempotency-key-reuse-different-params")
    assert fact.document["id"] == IDEMPOTENCY_ID
    assert fact.document["evidence"]["first_seen"] == "2026-10-22T09:14:00Z"
    assert fact.document["fixes_rendered"] == [
        "Set parameter Idempotency-Key to new UUID per distinct request"
    ]


def test_registry_version_is_the_newest_fact_date(repo):
    assert FactsIndex.load(repo).version == "2026-10-22"
    assert FactsIndex.load(repo, version="2026-11-01").version == "2026-11-01"


def test_empty_repo(tmp_path):
    index = FactsIndex.load(tmp_path)
    assert index.services == {} and index.version == "none"


def test_host_and_package_lookup(repo):
    index = FactsIndex.load(repo)
    assert [s.key for s in index.services_for_host("api.stripe.com")] == ["stripe"]
    assert index.services_for_host("stripe.com") == []
    assert [s.key for s in index.services_for_package("npm", "stripe")] == ["stripe"]
    assert index.services_for_package("npm", "left-pad") == []


def _signal(status, body=None):
    fields = ("status", "error.code", "error.type", "error.message")
    return extract_signal(status, body, fields)


def test_tier1_exact_hash(repo):
    index = FactsIndex.load(repo)
    stripe = index.services["stripe"]
    facts, hit = index.for_signal(
        stripe, ("POST", "/v1/payment_intents"), _signal(400, IDEMPOTENCY_BODY), None
    )
    assert (_ids(facts), hit) == ([IDEMPOTENCY_ID], True)


def test_tier1_vendor_code_when_the_message_differs(repo):
    index = FactsIndex.load(repo)
    body = '{"error": {"code": "resource_missing", "message": "No such customer: \'cus_999x\'"}}'
    facts, hit = index.for_signal(
        index.services["stripe"], ("GET", "/v1/customers/{id}"), _signal(404, body), None
    )
    assert (_ids(facts), hit) == (["af:stripe:customer-not-found"], True)


def test_tier1_vendor_code_without_status(repo):
    index = FactsIndex.load(repo)
    body = '{"error": {"code": "resource_missing", "message": "other words"}}'
    facts, hit = index.for_signal(
        index.services["stripe"], ("GET", "/v1/customers/{id}"), _signal(None, body), None
    )
    assert (_ids(facts), hit) == (["af:stripe:customer-not-found"], True)


def test_tier2_status_skips_contradicting_codes(repo):
    index = FactsIndex.load(repo)
    stripe = index.services["stripe"]
    template = ("POST", "/v1/payment_intents")
    facts, hit = index.for_signal(stripe, template, _signal(400, "something else"), None)
    assert (_ids(facts), hit) == ([IDEMPOTENCY_ID, "af:stripe:old-sdk-bad-request"], True)
    other_code = '{"error": {"type": "card_error", "message": "declined"}}'
    facts, _ = index.for_signal(stripe, template, _signal(400, other_code), None)
    assert _ids(facts) == ["af:stripe:old-sdk-bad-request"]  # its signal has no code


def test_tier2_respects_sdk_versions(repo):
    index = FactsIndex.load(repo)
    stripe = index.services["stripe"]
    template = ("POST", "/v1/payment_intents")
    new = Locator("pypi", "stripe", "12.1.0")
    facts, _ = index.for_signal(stripe, template, _signal(400, "x"), new)
    assert _ids(facts) == [IDEMPOTENCY_ID]


def test_tier3_service_level_kinds_when_nothing_matches(repo):
    index = FactsIndex.load(repo)
    facts, hit = index.for_signal(
        index.services["stripe"], ("POST", "/v1/payment_intents"), _signal(500, "boom"), None
    )
    assert (_ids(facts), hit) == (["af:stripe:payment-intents-429"], False)


def test_preflight_lists(repo):
    index = FactsIndex.load(repo)
    stripe = index.services["stripe"]
    assert _ids(index.for_template(stripe, ("GET", "/v1/customers/{id}"), None)) == [
        "af:stripe:customer-not-found",
        "af:stripe:payment-intents-429",
    ]
    assert len(index.for_service(stripe, None)) == 4
    assert _ids(index.for_package(stripe, Locator("pypi", "stripe", "11.0"))) == [
        IDEMPOTENCY_ID,  # versions ">=7,<13"
        "af:stripe:old-sdk-bad-request",  # versions "<12"
    ]
    assert _ids(index.for_package(stripe, Locator("pypi", "stripe", "12.1.0"))) == [
        IDEMPOTENCY_ID
    ]
    assert index.for_package(stripe, Locator("npm", "stripe", None)) == []


def test_service_helpers(repo):
    stripe = FactsIndex.load(repo).services["stripe"]
    assert stripe.rate_limit_headers == ("retry-after",)
    assert stripe.env_for_host("api.stripe.com") is None  # prod and sandbox share the host
