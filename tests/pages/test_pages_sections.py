"""Spec 06 article sections: Example (from the probe), In your code (SDK mapping + fixes as code),
Related errors. Everything is derived from data; nothing is shown that the data does not hold."""

from pathlib import Path

import pytest
import yaml
from pydantic import TypeAdapter

from apifacts.pages import sdk
from apifacts.pages.build import build_pages, load_probes, load_registry, related
from apifacts.pages.example import example
from apifacts.schema import models as m

REPO = Path(__file__).parents[2]
FIX = TypeAdapter(m.Fix)


@pytest.fixture
def registry(fixture_root):
    services, facts = load_registry(fixture_root)
    return services, facts, load_probes(fixture_root)


def _fact(facts, fact_id):
    return next(f for f in facts if f.id == fact_id)


def _stripe(services):
    return next(s for s in services if s.key == "stripe")


def _with(fact, **update):
    return fact.model_copy(update=update)


def _signal(fact, **update):
    return fact.model_copy(update={"signal": fact.signal.model_copy(update=update)})


# ── Example ──────────────────────────────────────────────────────────────────────────────────


def test_example_replays_the_probe_steps_and_only_asserted_fields(registry):
    services, facts, probes = registry
    fact = _fact(facts, "af:stripe:idempotency-key-reuse-different-params")
    found = example(fact, _stripe(services), probes[1])
    assert found is not None and found.probe_id == "af:stripe:probe:idempotency-key-reuse"
    assert [n for n, _, _ in found.steps] == [1, 2]
    request = found.steps[1][1]
    assert request.splitlines()[0] == "POST https://api.stripe.com/v1/payment_intents"
    assert "Authorization: Bearer <key>" in request  # where the key goes, never a value
    assert "Idempotency-Key: <run_uuid>" in request  # templating shown as a placeholder
    assert request.endswith("\n\namount=200&currency=usd")
    assert found.steps[1][2] == 400
    response = found.response
    assert response.startswith("HTTP 400\n")
    assert '"code": "idempotency_error"' in response
    # `contains: same parameters` is shown as the recorded error string that holds it
    assert f'"message": "{fact.signal.error_string}"' in response
    assert "type" not in response  # not asserted, so not shown


def test_example_without_the_recorded_string_marks_the_excerpt(registry):
    services, facts, probes = registry
    fact = _signal(_fact(facts, "af:stripe:idempotency-key-reuse-different-params"),
                   error_string=None)
    assert '"message": "…same parameters…"' in example(fact, _stripe(services), probes[1]).response


def test_no_probe_no_example(registry, fixture_root):
    services, facts, _ = registry
    fact = _fact(facts, "af:stripe:idempotency-key-reuse-different-params")
    assert example(fact, _stripe(services), None) is None
    page = build_pages(services, facts)["stripe/idempotency-key-reuse-different-params.md"]
    assert "## Example" not in page


def test_example_section_on_the_page(fixture_root):
    from apifacts.pages.build import registry_pages

    page = registry_pages(fixture_root)["stripe/deleted-customer-returns-200.md"]
    assert "## Example" in page
    assert "GET https://api.stripe.com/v1/customers/cus_deleted_fixture" in page
    assert '"deleted": true' in page


def test_example_redacts_key_shapes(registry):
    services, facts, probes = registry
    step = probes[1].steps[0].model_copy(
        update={"headers": {"X-Debug": "sk_test_abcdefghijklmnop"}}
    )
    probe = probes[1].model_copy(update={"steps": (step, probes[1].steps[1])})
    fact = _fact(facts, "af:stripe:idempotency-key-reuse-different-params")
    text = example(fact, _stripe(services), probe).steps[0][1]
    assert "sk_test_" not in text and "[redacted]" in text


# ── In your code: SDK mapping ────────────────────────────────────────────────────────────────


def _raised(fact, package):
    return next(r for r in sdk.raised(fact) if r.package == package)


def test_stripe_mapping_follows_the_sdk_order(registry):
    _, facts, _ = registry
    fact = _fact(facts, "af:stripe:idempotency-key-reuse-different-params")
    py = _raised(fact, "stripe")
    assert py.raises == "stripe.IdempotencyError"
    assert py.checks == (("e.http_status", 400), ("e.error.type", "idempotency_error"))
    other = _signal(fact, error_code="amount_too_small")
    assert _raised(other, "stripe").raises == "stripe.InvalidRequestError"
    assert _raised(_signal(fact, status=402, error_code="card_declined"), "stripe").raises == (
        "stripe.CardError"
    )
    assert _raised(_signal(fact, status=429), "stripe").raises == "stripe.RateLimitError"
    assert _raised(_signal(fact, status=500), "stripe").raises == "stripe.APIError"


def test_no_table_for_success_or_unmapped_services(registry):
    _, facts, _ = registry
    fact = _fact(facts, "af:stripe:idempotency-key-reuse-different-params")
    assert sdk.raised(_signal(fact, status=200)) == []
    assert sdk.raised(_with(fact, service="pypi")) == []


def test_unknown_message_falls_back_to_the_catch_class(registry):
    _, facts, _ = registry
    base = _with(_fact(facts, "af:stripe:idempotency-key-reuse-different-params"),
                 service="github")
    found = _signal(base, status=404, error_code=None, error_string="Not Found")
    assert _raised(found, "PyGithub").raises == "github.UnknownObjectException"
    unknown = _signal(base, status=404, error_code=None, error_string=None)
    assert _raised(unknown, "PyGithub").raises == "github.GithubException"
    assert _raised(unknown, "@octokit/request").checks == (("err.status", 404),)


def test_null_rule_and_path_condition(registry):
    _, facts, _ = registry
    base = _with(_fact(facts, "af:stripe:idempotency-key-reuse-different-params"),
                 service="telegram")
    target = base.target.model_copy(update={"path_template": "/{bot_token}/{method}"})
    generic = _signal(_with(base, target=target), status=404, error_code=None)
    assert _raised(generic, "python-telegram-bot").raises == "telegram.error.TelegramError"
    named = _with(generic, target=target.model_copy(update={"path_template": "/{bot_token}/getMe"}))
    assert _raised(named, "python-telegram-bot").raises == "telegram.error.InvalidToken"


def test_returns_instead_of_raising(registry):
    _, facts, _ = registry
    fact = _signal(_with(_fact(facts, "af:stripe:idempotency-key-reuse-different-params"),
                         service="resend"), status=401, error_code="missing_api_key")
    py = _raised(fact, "resend")  # the pypi entry comes first
    assert py.raises == "resend.exceptions.MissingApiKeyError"
    js = [r for r in sdk.raised(fact) if r.ecosystem == "npm"][0]
    assert js.raises is None and js.returns == "{ data: null, error }"
    assert js.checks == (("error.statusCode", 401), ("error.name", "missing_api_key"))


def test_mapping_file_is_well_formed():
    mapping = sdk.load_mapping()
    services = {p.stem for p in (REPO / "services").glob("*.yaml")}
    assert set(mapping) <= services
    conditions = {"status", "error_code", "path_template", *sdk._MESSAGE_TESTS}
    for service, entries in mapping.items():
        for entry in entries:
            assert entry["sdk"]["ecosystem"] in sdk.LANGUAGES, service
            assert entry["verified"].strip(), service
            assert entry.get("catch") or entry.get("returns"), service
            for rule in entry["rules"]:
                assert set(rule["when"]) <= conditions, (service, rule)
                assert set(rule) <= {"when", "raises", "read"}, (service, rule)


def test_mapping_file_is_plain_yaml():
    assert yaml.safe_load(sdk.SDK_ERRORS.read_text(encoding="utf-8"))


# ── In your code: fixes as code ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("fix", "expected"),
    [
        ({"action": "set_header", "name": "X-GitHub-Api-Version",
          "value_source": "literal:2022-11-28"},
         'headers["X-GitHub-Api-Version"] = "2022-11-28"'),
        ({"action": "set_header", "name": "x-api-key", "value_source": "account_setting:api_key"},
         'headers["x-api-key"] = YOUR_API_KEY'),
        ({"action": "set_param", "name": "limit", "value_source": "literal:100",
          "location": "query"},
         'params["limit"] = "100"'),
        ({"action": "remove_param", "name": "expand", "location": "query"},
         'params.pop("expand", None)'),
        ({"action": "use_endpoint", "method": "GET", "path_template": "/v1/models/{model}"},
         'response = client.request("GET", f"/v1/models/{model}")'),
        ({"action": "encode_as", "field": "timeMin", "encoding": "rfc3339"},
         'params["timeMin"] = moment.astimezone(UTC).isoformat()'),
        ({"action": "pin_sdk_version", "package": "stripe", "ecosystem": "pypi",
          "constraint": ">=7,<13"},
         "pip install 'stripe>=7,<13'"),
    ],
)
def test_fix_snippets(registry, fix, expected):
    _, facts, _ = registry
    fact = facts[0]
    language, code = sdk.fix_snippet(FIX.validate_python(fix), fact)
    assert expected in code


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("/v1/models/{model}", 'f"/v1/models/{model}"'),
        ("/v1/models", '"/v1/models"'),
        ("/v1/{x.__class__}", '"/v1/{x.__class__}"'),
        ("/v1/{__import__('os').system('id')}", "\"/v1/{__import__('os').system('id')}\""),
        ("/v1/{model}/{a[0]}", '"/v1/{model}/{a[0]}"'),
        ("/v1/{model}}", '"/v1/{model}}"'),
        ("/v1/{{model}}", '"/v1/{{model}}"'),
        ("/v1/{}", '"/v1/{}"'),
    ],
)
def test_use_endpoint_never_emits_an_f_string_with_code(template, expected):
    from apifacts.pages.sdk import _path_expr

    assert _path_expr(template) == expected
    fix = m.UseEndpoint.model_construct(action="use_endpoint", method="GET", path_template=template)
    _, code = sdk.fix_snippet(fix, None)
    assert code == f'response = client.request("GET", {expected})'


def test_retry_snippets_use_the_fix_parameters(registry):
    _, facts, _ = registry
    fact = _signal(_fact(facts, "af:stripe:idempotency-key-reuse-different-params"), status=429)
    backoff = FIX.validate_python({"action": "backoff_exponential", "base_ms": 1000, "factor": 2,
                                   "max_ms": 32000, "max_attempts": 5, "jitter": True})
    _, code = sdk.fix_snippet(backoff, fact)
    assert "delay_ms = 1000" in code and "range(5)" in code
    assert "response.status_code != 429" in code and "min(delay_ms * 2, 32000)" in code
    assert "random.uniform" in code
    retry = FIX.validate_python({"action": "retry_after_header", "unit": "ms", "max_attempts": 3})
    _, code = sdk.fix_snippet(retry, fact)
    assert 'float(response.headers["Retry-After"]) / 1000' in code and "range(3)" in code


@pytest.mark.parametrize(
    "fix",
    [
        {"action": "none_known", "reason_kind": "by_design"},
        {"action": "request_scope", "scope": "repo"},
        {"action": "paginate_with", "cursor_field": "id", "param_name": "starting_after",
         "page_size_max": 100},
    ],
)
def test_no_snippet_where_code_would_need_judgement(registry, fix):
    _, facts, _ = registry
    assert sdk.fix_snippet(FIX.validate_python(fix), facts[0]) is None


# ── Related errors ───────────────────────────────────────────────────────────────────────────


def test_related_errors_rank_and_exclusions(registry):
    services, facts, _ = registry
    fact = _fact(facts, "af:stripe:idempotency-key-reuse-different-params")
    same_both = _signal(_with(fact, id="af:stripe:zz-same-both"), error_code="amount_too_small")
    same_status = _with(
        _with(fact, id="af:stripe:aa-same-status"),
        target=fact.target.model_copy(update={"method": "GET", "path_template": "/v1/customers"}),
    )
    success = _signal(_with(fact, id="af:stripe:bb-success"), status=200)
    retracted = _with(fact, id="af:stripe:cc-retracted", status=m.Status.retracted)
    other_service = _with(fact, id="af:example:dd-other", service="example")
    pool = [fact, same_both, same_status, success, retracted, other_service]
    assert [f.id for f in related(fact, pool)] == [same_both.id, same_status.id]
    assert related(fact, pool, exclude=[same_both]) == (same_status,)
    many = [_with(same_status, id=f"af:stripe:n{i}") for i in range(9)]
    assert len(related(fact, many)) == 6


def test_example_picks_the_step_on_the_facts_endpoint(registry):
    from apifacts.pages.example import chosen_step

    _, facts, probes = registry
    fact = _fact(facts, "af:stripe:idempotency-key-reuse-different-params")
    probe = probes[1]
    other = probe.steps[1].model_copy(update={"path": "/v1/customers"})
    later = probe.model_copy(
        update={
            "steps": (*probe.steps, other),
            "assertions": (*probe.assertions, m.AssertStatus(step=3, status=400)),
        }
    )
    assert chosen_step(fact, later) == 2  # step 3 also answers 400, on another endpoint


def test_example_shows_where_the_key_goes(registry):
    from apifacts.pages.example import request_text

    services, _, probes = registry
    stripe = _stripe(services)
    step = probes[1].steps[0]
    assert "Authorization: Bearer <key>" in request_text(step, stripe, "sandbox")
    invalid = step.model_copy(update={"auth": "invalid"})
    assert "Authorization: Bearer apifacts-invalid-key" in request_text(invalid, stripe, "sandbox")
    keyless = stripe.model_copy(
        update={"auth": stripe.auth.model_copy(update={"key_name": None, "env": None})}
    )
    assert "Authorization" not in request_text(step, keyless, "sandbox")  # sends nothing
    none = step.model_copy(update={"auth": "none"})
    assert "Authorization" not in request_text(none, stripe, "sandbox")


def test_long_json_arrays_are_shown_compacted():
    from apifacts.pages.example import _compact

    assert _compact({"params": [list(range(101))]}) == {"params": [[0, 1, 2, "… 98 more"]]}
    assert _compact([1, 2, 3, 4]) == [1, 2, 3, 4]
