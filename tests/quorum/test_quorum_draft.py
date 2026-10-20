"""Coverage and probe matching rules (spec 05), on in-memory models."""

from pathlib import Path

import pytest
from quorum_fixtures import quorum_rows

from agentfacts.probe.loader import LoadedFact, LoadedProbe
from agentfacts.quorum.draft import covering_fact, matching_probe
from agentfacts.quorum.group import group_observations
from agentfacts.schema.models import Fact, Probe, Service
from agentfacts.schema.yamlio import load_yaml, plain

VALID = Path(__file__).parents[1] / "fixtures" / "valid"
SERVICE = Service.model_validate(plain(load_yaml(VALID / "service-stripe.yaml")))


def group(**kw):
    (g,) = group_observations(quorum_rows(**kw))
    return g


def fact(slug="f", status="reported", signal=None, **target) -> LoadedFact:
    doc = {
        "id": f"af:stripe:{slug}", "service": "stripe", "kind": "error_meaning",
        "target": {"surface": "http", "method": "POST", "path_template": "/v1/payment_intents"}
        | target,
        "signal": signal or {"status": 400},
        "claim": "x.", "dimensions": {"env": "prod"},
        "fixes": [{"action": "none_known", "reason_kind": "investigating"}], "status": status,
        "evidence": {"first_seen": "2026-10-01T00:00:00Z"},
        "provenance": {"source": "manual", "author": "human:edouard", "created": "2026-10-01"},
    }
    return LoadedFact(Path(f"{slug}.yaml"), Fact.model_validate(doc))


def probe(asserts, env="sandbox", method="POST", path="/v1/payment_intents") -> LoadedProbe:
    doc = {"id": "af:stripe:probe:p", "service": "stripe", "env": env,
           "steps": [{"do": "http", "method": method, "path": path}], "assert": asserts}
    return LoadedProbe(Path("p.yaml"), Probe.model_validate(doc))


def test_status_only_group_is_covered_by_a_fact_with_that_status():
    g = group(message=None, status=400)
    assert covering_fact(g, [fact()]).fact.id == "af:stripe:f"
    assert covering_fact(group(message=None, status=429), [fact()]) is None


def test_string_group_needs_the_same_string():
    other = fact(signal={"status": 400, "normalized": "something else"})
    assert covering_fact(group(), [other]) is None
    same = fact(signal={"status": 400, "error_string": "Keys for idempotent requests can only be "
                        "used with the same parameters"})
    assert covering_fact(group(), [same]) is not None


def test_other_endpoint_never_covers():
    assert covering_fact(group(message=None), [fact(method="GET", path_template="/v1/x")]) is None


def test_live_fact_wins_over_a_retracted_one():
    found = covering_fact(group(message=None), [fact("a", "retracted"), fact("b")])
    assert found.fact.id == "af:stripe:b"


@pytest.mark.parametrize(
    "asserts, matches",
    [
        ([{"step": 1, "status": 400}], True),
        ([{"step": 1, "status": 402}], False),
        ([{"step": 1, "json_path": "$.error.message", "contains": "Same Parameters"}], True),
        ([{"step": 1, "body_contains": "only be used"}], True),
        ([{"step": 1, "json_path": "$.x", "equals": "400"}], False),  # "###": too short to prove
        ([{"step": 1, "header": "Request-Id", "present": True}], False),
    ],
)
def test_probe_matches_on_status_or_string(asserts, matches):
    assert (matching_probe(group(), [probe(asserts)], SERVICE, None) is not None) is matches


def test_probe_must_hit_the_template_with_the_method_and_env():
    ok = [{"step": 1, "status": 400}]
    assert matching_probe(group(), [probe(ok, method="GET", path="/v1/customers/x")],
                          SERVICE, None) is None
    assert matching_probe(group(), [probe(ok)], SERVICE, "prod") is None
    assert matching_probe(group(), [probe(ok)], SERVICE, "sandbox") is not None


def test_assertion_on_another_step_does_not_count():
    doc = {"id": "af:stripe:probe:two", "service": "stripe", "env": "sandbox",
           "steps": [{"do": "http", "method": "POST", "path": "/v1/payment_intents"},
                     {"do": "http", "method": "GET", "path": "/v1/customers/c"}],
           "assert": [{"step": 2, "status": 400}]}
    loaded = LoadedProbe(Path("two.yaml"), Probe.model_validate(doc))
    assert matching_probe(group(), [loaded], SERVICE, None) is None
