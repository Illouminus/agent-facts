"""Spec 05 rules: kind inference, claim per kind, slug and dedup."""

import pytest

from agentfacts.quorum.rules import MAX_CLAIM, claim_for, infer_kind, slug_base, unique_slug
from agentfacts.schema.models import Kind


@pytest.mark.parametrize(
    "status, normalized, headers, kind",
    [
        (429, None, (), Kind.rate_limit),
        (429, "too many requests", (), Kind.rate_limit),
        (400, "x", ("Retry-After",), Kind.rate_limit),
        (403, "x", ("X-RateLimit-Remaining",), Kind.rate_limit),  # the first rule wins
        (200, None, (), Kind.silent_behavior),
        (204, None, (), Kind.silent_behavior),
        (200, "x", (), Kind.error_meaning),  # a 2xx with a message is not silent (JSON-RPC)
        (401, "bad credentials", (), Kind.auth_quirk),
        (403, None, (), Kind.auth_quirk),
        (410, None, (), Kind.deprecation),
        (400, "x", ("Sunset",), Kind.deprecation),
        (404, "not found", (), Kind.error_meaning),
        (500, None, (), Kind.error_meaning),
        (None, "boom", (), Kind.error_meaning),
    ],
)
def test_infer_kind(status, normalized, headers, kind):
    assert infer_kind(status, normalized, headers) is kind


@pytest.mark.parametrize(
    "kind, status, normalized, claim",
    [
        (Kind.error_meaning, 400, "keys for idempotent requests",
         'POST /v1/x returns HTTP 400 with "keys for idempotent requests".'),
        (Kind.error_meaning, 500, None, "POST /v1/x returns HTTP 500."),
        (Kind.rate_limit, 429, None, "POST /v1/x returns HTTP 429, a rate-limit response."),
        (Kind.silent_behavior, 200, None, "POST /v1/x returns HTTP 200 with an empty body."),
        (Kind.auth_quirk, 403, "forbidden",
         'POST /v1/x refuses the request with HTTP 403 with "forbidden".'),
        (Kind.deprecation, 410, None, "POST /v1/x returns HTTP 410, a deprecation signal."),
        (Kind.error_meaning, None, "boom", 'POST /v1/x fails with "boom".'),
    ],
)
def test_claim_templates(kind, status, normalized, claim):
    assert claim_for(kind, "POST", "/v1/x", status, normalized) == claim


def test_long_string_is_cut_to_fit_the_claim():
    claim = claim_for(Kind.error_meaning, "POST", "/v1/x", 400, "word " * 200)
    assert len(claim) <= MAX_CLAIM
    assert claim.endswith('…".') and claim.startswith("POST /v1/x returns HTTP 400 with \"word")


@pytest.mark.parametrize(
    "status, normalized, slug",
    [
        (400, "keys for idempotent requests can only be used with the same parameters",
         "400-keys-for-idempotent-requests-can-only"),
        (404, "no such customer: '<id>'", "404-no-such-customer-id"),
        (400, "page ### of ### is out of range", "400-page-of-is-out"),
        (429, None, "429"),
        (None, "Boom", "boom"),
        (500, "### ###", "500"),
        (None, None, "signal"),
    ],
)
def test_slug_base(status, normalized, slug):
    assert slug_base(status, normalized) == slug


def test_slug_base_is_capped():
    base = slug_base(400, " ".join(["abcdefghijklmnopqrstuvwxyz"] * 6))
    assert len(base) <= 60 and not base.endswith("-")


def test_unique_slug_dedups_with_suffix():
    assert unique_slug("400-a", set()) == "400-a"
    assert unique_slug("400-a", {"400-a"}) == "400-a-2"
    assert unique_slug("400-a", {"400-a", "400-a-2"}) == "400-a-3"
    assert unique_slug("index", set()) == "index-2"
