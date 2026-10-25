"""Golden sentence per fix action (spec 02): schema, model and renderer agree on every example."""

import pytest
from pydantic import TypeAdapter

from apifacts.fixes.templates import render_fix
from apifacts.schema import load_schema, validator_for
from apifacts.schema.models import FIX_ACTIONS, Fix

GOLDEN = [
    (
        {"action": "retry_after_header", "unit": "s", "max_attempts": 3},
        "Wait the number of seconds in Retry-After, then retry (≤ 3 attempts)",
    ),
    (
        {
            "action": "retry_after_header",
            "header": "X-RateLimit-Reset",
            "unit": "ms",
            "max_attempts": 2,
        },
        "Wait the number of milliseconds in X-RateLimit-Reset, then retry (≤ 2 attempts)",
    ),
    (
        {
            "action": "backoff_exponential",
            "base_ms": 500,
            "factor": 2,
            "max_ms": 30000,
            "max_attempts": 5,
            "jitter": True,
        },
        "Retry with exponential backoff from 500 ms × 2, cap 30000 ms, ≤ 5 attempts, with jitter",
    ),
    (
        {
            "action": "set_header",
            "name": "Idempotency-Key",
            "value_source": "new_uuid_per_distinct_request",
        },
        "Send header Idempotency-Key = new UUID per distinct request",
    ),
    (
        {"action": "set_header", "name": "Stripe-Version", "value_source": "literal:2024-06-20"},
        "Send header Stripe-Version = 2024-06-20",
    ),
    (
        {
            "action": "set_param",
            "name": "limit",
            "value_source": "literal:100",
            "location": "query",
        },
        "Set query parameter limit to 100",
    ),
    (
        {
            "action": "set_param",
            "name": "Idempotency-Key",
            "value_source": "new_uuid_per_distinct_request",
        },
        "Set parameter Idempotency-Key to new UUID per distinct request",
    ),
    (
        {
            "action": "set_param",
            "name": "team_id",
            "value_source": "account_setting:workspace_id",
            "location": "body",
        },
        "Set body parameter team_id to the account setting workspace_id",
    ),
    (
        {"action": "remove_param", "name": "expand", "location": "body"},
        "Omit body parameter expand",
    ),
    (
        {"action": "use_endpoint", "method": "GET", "path_template": "/v1/customers/{id}"},
        "Call GET /v1/customers/{id} instead",
    ),
    (
        {
            "action": "paginate_with",
            "cursor_field": "next_cursor",
            "param_name": "cursor",
            "page_size_max": 200,
        },
        "Paginate by next_cursor via cursor, ≤ 200 per page",
    ),
    (
        {
            "action": "pin_sdk_version",
            "package": "stripe",
            "ecosystem": "pypi",
            "constraint": ">=7,<13",
        },
        "Pin stripe (pypi) to >=7,<13",
    ),
    (
        {
            "action": "upgrade_sdk",
            "package": "@slack/web-api",
            "ecosystem": "npm",
            "min_version": "7.9.0",
        },
        "Upgrade @slack/web-api (npm) to ≥ 7.9.0",
    ),
    (
        {"action": "switch_env", "to": "sandbox", "reason_kind": "state_unreachable"},
        "Use the sandbox environment: state unreachable",
    ),
    (
        {"action": "request_scope", "scope": "chat:write"},
        "Request OAuth scope chat:write",
    ),
    (
        {"action": "wait_for_state", "account_state": "active", "typical_delay_s": 60},
        "Wait until account state active (typically 60 s)",
    ),
    (
        {
            "action": "enable_in_dashboard",
            "setting_key": "payment_methods.card",
            "vendor_doc_url": "https://docs.stripe.com/payments/payment-methods",
        },
        "A human must enable payment_methods.card in the vendor dashboard"
        " (see https://docs.stripe.com/payments/payment-methods)",
    ),
    (
        {"action": "reduce_payload", "field": "blocks", "max_items": 50},
        "Keep blocks ≤ 50 items",
    ),
    (
        {"action": "reduce_payload", "field": "text", "max_bytes": 4000},
        "Keep text ≤ 4000 bytes",
    ),
    (
        {"action": "encode_as", "field": "created", "encoding": "rfc3339"},
        "Encode created as an RFC 3339 timestamp",
    ),
    (
        {"action": "none_known", "reason_kind": "vendor_side"},
        "No client-side fix known (vendor side)",
    ),
]

FIX = TypeAdapter(Fix)


def test_golden_covers_every_action():
    assert {fix["action"] for fix, _ in GOLDEN} == set(FIX_ACTIONS)


def test_model_actions_equal_schema_enum():
    assert list(FIX_ACTIONS) == load_schema("fix")["properties"]["action"]["enum"]


@pytest.mark.parametrize(("fix", "sentence"), GOLDEN, ids=[f["action"] for f, _ in GOLDEN])
def test_golden_fix_is_valid_and_renders(fix, sentence):
    assert list(validator_for("fix").iter_errors(fix)) == []
    assert render_fix(FIX.validate_python(fix)) == sentence


def test_render_accepts_plain_dict():
    assert render_fix({"action": "none_known", "reason_kind": "by_design"}) == (
        "No client-side fix known (by design)"
    )
