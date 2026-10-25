"""Cross-document rules of `apifacts validate`: registry references, ids, URLs, templates."""

from pathlib import Path

import pytest

from apifacts.schema.registry import match_template, on_vendor_domain
from apifacts.schema.validate import validate_paths

VALID = Path(__file__).parents[1] / "fixtures" / "valid"
SERVICE = (VALID / "service-stripe.yaml").read_text(encoding="utf-8")
FACT = (VALID / "fact-idempotency-key-reuse-different-params.yaml").read_text(encoding="utf-8")
PROBE = (VALID / "probe-idempotency-key-reuse.yaml").read_text(encoding="utf-8")
FIX_LINE = (
    "  - {action: set_param, name: Idempotency-Key, value_source: new_uuid_per_distinct_request}"
)


def _codes(tmp_path: Path, files: dict[str, str]) -> set[str]:
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text, encoding="utf-8")
    report = validate_paths([tmp_path / name for name in files], root=tmp_path / "no-root")
    return {p.code for p in report.problems}


def _swap(text: str, old: str, new: str) -> str:
    assert old in text, old
    return text.replace(old, new)


def test_baseline_is_clean(tmp_path):
    assert _codes(tmp_path, {"s.yaml": SERVICE, "f.yaml": FACT, "p.yaml": PROBE}) == set()


def test_fact_of_unregistered_service(tmp_path):
    assert _codes(tmp_path, {"f.yaml": FACT, "p.yaml": PROBE}) == {"unknown_service"}


def test_fact_referencing_missing_probe(tmp_path):
    assert _codes(tmp_path, {"s.yaml": SERVICE, "f.yaml": FACT}) == {"unknown_probe"}


def test_duplicate_ids(tmp_path):
    files = {"s.yaml": SERVICE, "f.yaml": FACT, "f2.yaml": FACT, "p.yaml": PROBE}
    assert _codes(tmp_path, files) == {"duplicate_id"}


def test_fact_id_must_carry_its_service(tmp_path):
    fact = _swap(FACT, "id: af:stripe:", "id: af:paypal:")
    assert _codes(tmp_path, {"s.yaml": SERVICE, "f.yaml": fact, "p.yaml": PROBE}) == {"id_mismatch"}


def test_fact_location_must_match_its_id(tmp_path):
    files = {"s.yaml": SERVICE, "facts/stripe/other-slug.yaml": FACT, "p.yaml": PROBE}
    assert _codes(tmp_path, files) == {"id_mismatch"}


def test_fact_in_its_canonical_location(tmp_path):
    files = {
        "services/stripe.yaml": SERVICE,
        "facts/stripe/idempotency-key-reuse-different-params.yaml": FACT,
        "probes/stripe/idempotency-key-reuse.yaml": PROBE,
    }
    assert _codes(tmp_path, files) == set()


def test_use_endpoint_must_be_registered(tmp_path):
    fact = _swap(
        FACT, FIX_LINE, "  - {action: use_endpoint, method: GET, path_template: /v1/refunds}"
    )
    assert _codes(tmp_path, {"s.yaml": SERVICE, "f.yaml": fact, "p.yaml": PROBE}) == {
        "unregistered_template"
    }


def test_use_endpoint_registered_template_passes(tmp_path):
    fact = _swap(
        FACT,
        FIX_LINE,
        '  - {action: use_endpoint, method: GET, path_template: "/v1/customers/{id}"}',
    )
    assert _codes(tmp_path, {"s.yaml": SERVICE, "f.yaml": fact, "p.yaml": PROBE}) == set()


SERVICE_WITH_DOCS = _swap(
    SERVICE, "hosts: [api.stripe.com]", "hosts: [api.stripe.com]\ndoc_hosts: [docs.stripe.com]"
)


@pytest.mark.parametrize(
    ("service", "url", "codes"),
    [
        (SERVICE_WITH_DOCS, "https://docs.stripe.com/payments", set()),
        (SERVICE, "https://docs.stripe.com/payments", {"foreign_url"}),
        (SERVICE, "https://api.stripe.com/docs", set()),
        (SERVICE_WITH_DOCS, "https://stripe.com/docs", {"foreign_url"}),
        (SERVICE_WITH_DOCS, "https://docs.stripe.com.evil.example/x", {"foreign_url"}),
        (SERVICE_WITH_DOCS, "https://evil.example/docs.stripe.com", {"foreign_url"}),
    ],
)
def test_vendor_doc_url_must_be_on_a_registered_host(tmp_path, service, url, codes):
    fix = f"  - {{action: enable_in_dashboard, setting_key: payments, vendor_doc_url: '{url}'}}"
    fact = _swap(FACT, FIX_LINE, fix)
    assert _codes(tmp_path, {"s.yaml": service, "f.yaml": fact, "p.yaml": PROBE}) == codes


def test_scope_url_must_be_on_the_vendor_domain(tmp_path):
    fact = _swap(FACT, FIX_LINE, "  - {action: request_scope, scope: 'https://evil.example/auth'}")
    assert _codes(tmp_path, {"s.yaml": SERVICE, "f.yaml": fact, "p.yaml": PROBE}) == {"foreign_url"}


def test_account_state_must_be_listed_by_the_service(tmp_path):
    fact = _swap(FACT, "account_state: any ", "account_state: frozen ")
    assert _codes(tmp_path, {"s.yaml": SERVICE, "f.yaml": fact, "p.yaml": PROBE}) == {
        "unknown_account_state"
    }
    fact = _swap(FACT, "account_state: any ", "account_state: restricted ")
    assert _codes(tmp_path, {"s.yaml": SERVICE, "f.yaml": fact, "p.yaml": PROBE}) == set()


def test_wait_for_state_must_name_a_listed_state(tmp_path):
    fact = _swap(
        FACT, FIX_LINE, "  - {action: wait_for_state, account_state: frozen, typical_delay_s: 5}"
    )
    assert _codes(tmp_path, {"s.yaml": SERVICE, "f.yaml": fact, "p.yaml": PROBE}) == {
        "unknown_account_state"
    }


def test_probe_step_must_hit_a_registered_template(tmp_path):
    probe = PROBE.replace("path: /v1/payment_intents", "path: /v1/refunds")
    assert _codes(tmp_path, {"s.yaml": SERVICE, "p.yaml": probe}) == {"unregistered_template"}


def test_probe_step_may_instantiate_a_template(tmp_path):
    probe = (
        "id: af:stripe:probe:get-customer\nservice: stripe\nenv: sandbox\n"
        "steps:\n  - {do: http, method: GET, path: /v1/customers/cus_123}\n"
        "  - {do: http, method: GET, path: '/v1/customers/{{step[1].json.id}}'}\n"
        "assert:\n  - {step: 2, status: 404}\n"
    )
    assert _codes(tmp_path, {"s.yaml": SERVICE, "p.yaml": probe}) == set()


def test_assertion_must_reference_an_existing_step(tmp_path):
    probe = PROBE.replace("- {step: 2, status: 400}", "- {step: 3, status: 400}")
    assert _codes(tmp_path, {"s.yaml": SERVICE, "p.yaml": probe}) == {"unknown_step"}


def test_probe_env_must_be_offered_by_the_service(tmp_path):
    service = SERVICE.replace(", sandbox: https://api.stripe.com}", "}")
    assert _codes(tmp_path, {"s.yaml": service, "p.yaml": PROBE}) == {"env_not_offered"}


def test_service_file_name_must_match_key(tmp_path):
    assert _codes(tmp_path, {"services/paypal.yaml": SERVICE}) == {"id_mismatch"}


def test_yaml_syntax_error(tmp_path):
    assert _codes(tmp_path, {"f.yaml": "id: [unclosed\n"}) == {"yaml_error"}


def test_document_of_unknown_type(tmp_path):
    assert _codes(tmp_path, {"x.yaml": "hello: world\n"}) == {"unknown_document"}
    assert _codes(tmp_path, {"y.yaml": "- a\n- b\n"}) == {"not_a_mapping"}


def test_context_services_come_from_root(tmp_path):
    (tmp_path / "services").mkdir()
    (tmp_path / "services" / "stripe.yaml").write_text(SERVICE, encoding="utf-8")
    (tmp_path / "probes").mkdir()
    (tmp_path / "probes" / "p.yaml").write_text(PROBE, encoding="utf-8")
    (tmp_path / "f.yaml").write_text(FACT, encoding="utf-8")
    assert validate_paths([tmp_path / "f.yaml"], root=tmp_path).problems == []


def test_inputs_shadow_context_documents(tmp_path):
    (tmp_path / "services").mkdir()
    (tmp_path / "services" / "stripe.yaml").write_text(SERVICE, encoding="utf-8")
    report = validate_paths([VALID], root=tmp_path)
    assert report.problems == []


@pytest.mark.parametrize(
    ("path", "template", "ok"),
    [
        ("/v1/customers/cus_1", "/v1/customers/{id}", True),
        ("/v1/customers", "/v1/customers/{id}", False),
        ("/v1/customers/cus_1/x", "/v1/customers/{id}", False),
        ("/v1/customers/", "/v1/customers/{id}", False),
        ("/v1/payment_intents", "/v1/payment_intents", True),
        ("/v1/payment_intent", "/v1/payment_intents", False),
        ("/v1/customers/..", "/v1/customers/{id}", False),
        ("/v1/customers/.", "/v1/customers/{id}", False),
        ("/v1/customers/%2E%2E", "/v1/customers/{id}", False),
        ("/v1/customers/a%2Fb", "/v1/customers/{id}", False),
        ("/v1/customers/a\\b", "/v1/customers/{id}", False),
    ],
)
def test_match_template(path, template, ok):
    assert match_template(path, template) is ok


def test_on_vendor_domain():
    hosts = ("api.stripe.com", "docs.stripe.com")
    assert on_vendor_domain("https://docs.stripe.com/x", hosts)
    assert on_vendor_domain("https://eu.api.stripe.com/x", hosts)
    assert not on_vendor_domain("https://stripe.com/x", hosts)  # no parent-domain guessing
    assert not on_vendor_domain("https://notapi.stripe.com/x", hosts)
    assert not on_vendor_domain("https://docs.stripe.com@evil.example/x", hosts)
    assert not on_vendor_domain("https://api.co.uk/x", ("x.api.co.uk",))


PROD_GET = (
    "id: af:stripe:probe:get-customer\nservice: stripe\nenv: prod\n"
    "steps:\n  - {do: http, method: GET, path: /v1/customers/cus_123%s}\n"
    "assert:\n  - {step: 1, status: 404}\n"
)
SERVICE_PROD_KEY = SERVICE.replace("  env: sandbox ", "  env: prod    ")


@pytest.mark.parametrize(
    "extra",
    [
        ", form: {name: x}",
        ", json: {name: x}",
        ", headers: {X-HTTP-Method-Override: DELETE}",
        ", headers: {x-method-override: POST}",
        ", query: {_method: DELETE}",
    ],
)
def test_prod_probe_cannot_smuggle_a_write(tmp_path, extra):
    files = {"s.yaml": SERVICE_PROD_KEY, "p.yaml": PROD_GET % extra}
    assert _codes(tmp_path, files) == {"prod_probe_not_readonly"}


@pytest.mark.parametrize("header", ["Authorization", "cookie", "Host"])
def test_probe_cannot_supply_credentials_or_host(tmp_path, header):
    probe = PROBE.replace(
        "headers: {Idempotency-Key", f"headers: {{{header}: x, Idempotency-Key", 1
    )
    assert _codes(tmp_path, {"s.yaml": SERVICE, "p.yaml": probe}) == {"forbidden_header"}


def test_probe_env_must_match_the_key_env(tmp_path):
    # The stripe key reaches sandbox; a probe labelled prod that uses it is mislabelled, and a
    # sandbox-labelled probe must not run with a prod key (it could write to production).
    assert _codes(tmp_path, {"s.yaml": SERVICE, "p.yaml": PROD_GET % ""}) == {"auth_env_mismatch"}
    assert _codes(tmp_path, {"s.yaml": SERVICE_PROD_KEY, "p.yaml": PROBE}) == {"auth_env_mismatch"}


def test_keyless_step_may_cross_env(tmp_path):
    probe = (PROD_GET % "").replace("cus_123}", "cus_123, auth: none}")
    assert _codes(tmp_path, {"s.yaml": SERVICE, "p.yaml": probe}) == set()


def test_malformed_service_is_reported_not_a_crash(tmp_path):
    service = "key: stripe\nname: Stripe\nhosts: api.stripe.com\nsurfaces: [http]\nauth: bearer\n"
    codes = _codes(tmp_path, {"s.yaml": service, "f.yaml": FACT, "p.yaml": PROBE})
    assert "schema_type" in codes  # hosts / surfaces / auth have the wrong shape; no traceback


def test_fact_directly_under_facts_is_misplaced(tmp_path):
    files = {"s.yaml": SERVICE, "facts/idempotency.yaml": FACT, "p.yaml": PROBE}
    assert _codes(tmp_path, files) == {"id_mismatch"}


def test_directory_named_like_yaml_is_skipped(tmp_path):
    (tmp_path / "old.yaml").mkdir()
    assert validate_paths([tmp_path], root=tmp_path / "no-root").problems == []


def test_unreadable_file_is_a_read_error(tmp_path):
    path = tmp_path / "f.yaml"
    path.write_text(FACT, encoding="utf-8")
    path.chmod(0)
    try:
        assert {p.code for p in validate_paths([path], root=tmp_path).problems} == {"read_error"}
    finally:
        path.chmod(0o644)
