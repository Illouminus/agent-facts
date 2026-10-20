"""Spec 01 examples pass the JSON Schemas and parse into the pydantic mirrors; enums agree."""

from pathlib import Path

import pytest

from agentfacts.schema import SCHEMA_NAMES, load_schema, validator_for
from agentfacts.schema.models import (
    Env,
    Fact,
    Kind,
    Observation,
    Probe,
    Service,
    Source,
    Status,
    Surface,
)
from agentfacts.schema.yamlio import load_yaml, plain

VALID = Path(__file__).parents[1] / "fixtures" / "valid"

CASES = [
    ("service-stripe.yaml", "service", Service),
    ("fact-idempotency-key-reuse-different-params.yaml", "fact", Fact),
    ("probe-idempotency-key-reuse.yaml", "probe", Probe),
]

OBSERVATION = {
    "id": 1,
    "received_at": "2026-10-22T09:14:00Z",
    "service": "stripe",
    "method": "POST",
    "path_template": "/v1/payment_intents",
    "status": 400,
    "error_hash": "a" * 64,
    "normalized_error": "keys for idempotent requests can only be used with the same parameters",
    "reporter_net": "b" * 64,
    "reporter_ua_class": "pytest-plugin",
    "sdk_package": "stripe",
    "sdk_version": "12.1.0",
    "env_guess": "prod",
    "vantage_country": "FR",
}


@pytest.mark.parametrize(("name", "schema", "model"), CASES, ids=[c[1] for c in CASES])
def test_spec_example_is_valid(name, schema, model):
    doc = plain(load_yaml(VALID / name))
    assert [e.message for e in validator_for(schema).iter_errors(doc)] == []
    model.model_validate(doc)


def test_fact_example_round_trips_through_the_model():
    doc = plain(load_yaml(VALID / CASES[1][0]))
    fact = Fact.model_validate(doc)
    assert fact.fixes[0].action == "set_param"
    assert fact.status is Status.verified_server_prod
    assert (
        list(validator_for("fact").iter_errors(fact.model_dump(mode="json", exclude_none=True)))
        == []
    )


def test_observation_row_is_valid():
    assert list(validator_for("observation").iter_errors(OBSERVATION)) == []
    Observation.model_validate(OBSERVATION)


def test_observation_rejects_bodies_and_raw_ips():
    row = OBSERVATION | {"body": "{...}", "ip": "203.0.113.7"}
    assert list(validator_for("observation").iter_errors(row))


@pytest.mark.parametrize(
    ("enum", "schema", "path"),
    [
        (Kind, "fact", ("properties", "kind", "enum")),
        (Status, "fact", ("properties", "status", "enum")),
        (Surface, "fact", ("$defs", "target", "properties", "surface", "enum")),
        (Env, "fact", ("$defs", "dimensions", "properties", "env", "enum")),
        (Source, "fact", ("$defs", "provenance", "properties", "source", "enum")),
        (Env, "probe", ("properties", "env", "enum")),
    ],
    ids=["kind", "status", "surface", "env", "source", "probe-env"],
)
def test_enum_parity(enum, schema, path):
    node = load_schema(schema)
    for key in path:
        node = node[key]
    assert [e.value for e in enum] == node


def _patterns(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "pattern":
                yield value
            else:
                yield from _patterns(value)
    elif isinstance(node, list):
        for value in node:
            yield from _patterns(value)


@pytest.mark.parametrize("schema", SCHEMA_NAMES)
def test_anchored_patterns_reject_trailing_newline(schema):
    # Python's re lets `$` match before a final "\n"; `(?!\n)$` closes that gap in every engine.
    for pattern in _patterns(load_schema(schema)):
        assert pattern.endswith(r"(?!\n)$"), pattern
