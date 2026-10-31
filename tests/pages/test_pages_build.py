"""Spec 06 Done-when: deterministic pages, H1 = error string (else normalized string, else claim),
an index per service, a root index, and a fact page carrying fixes, badge,
first-seen/last-confirmed and CC BY 4.0."""

import os
from pathlib import Path

import pytest

from apifacts.fixes.templates import render_fix
from apifacts.pages import PagesError
from apifacts.pages.build import build_pages, load_registry, published, registry_version, sync
from apifacts.pages.templates import (
    FOOTER,
    HEAD_TITLE_MAX,
    head_description,
    head_title,
    substantive,
)
from apifacts.schema.models import Status

GOLDEN = Path(__file__).parent / "golden"
IDEMPOTENCY = (
    "keys for idempotent requests can only be used with the same parameters"
    " they were first used with"
)
IDEMPOTENCY_ID = "af:stripe:idempotency-key-reuse-different-params"
IDEMPOTENCY_RAW = (
    "Keys for idempotent requests can only be used with the same parameters"
    " they were first used with."
)


@pytest.fixture
def registry(fixture_root):
    return load_registry(fixture_root)


@pytest.fixture
def pages(registry):
    return build_pages(*registry)


def _tree(directory: Path) -> dict[str, str]:
    return {
        p.relative_to(directory).as_posix(): p.read_bytes().decode("utf-8")
        for p in sorted(directory.rglob("*.md"))
    }


def _fact(registry, fact_id):
    return next(f for f in registry[1] if f.id == fact_id)


def test_golden_tree(pages):
    """Regenerate with `UPDATE_GOLDEN=1 uv run pytest tests/pages -q`, then read the diff."""
    if os.environ.get("UPDATE_GOLDEN"):
        sync(GOLDEN, pages)
    assert _tree(GOLDEN) == pages


def test_build_twice_is_byte_identical(fixture_root, tmp_path):
    first, second = tmp_path / "one", tmp_path / "two"
    sync(first, build_pages(*load_registry(fixture_root)))
    sync(second, build_pages(*load_registry(fixture_root)))
    assert _tree(first) == _tree(second)
    assert {p.relative_to(first) for p in first.rglob("*")} == {
        p.relative_to(second) for p in second.rglob("*")
    }


def test_input_order_does_not_change_output(registry, pages):
    services, facts = registry
    assert build_pages(services[::-1], facts[::-1]) == pages


def test_layout(pages):
    assert "index.md" in pages
    assert {"stripe/index.md", "example/index.md"} <= set(pages)
    assert "stripe/idempotency-key-reuse-different-params.md" in pages
    assert "example/sdk-v2-legacy-endpoint.md" in pages
    assert sum(path.startswith("errors/") for path in pages) == 2
    assert all(text.endswith(FOOTER + "\n") for text in pages.values())


def test_verified_fact_page_content(registry, pages):
    fact = _fact(registry, "af:stripe:idempotency-key-reuse-different-params")
    page = pages["stripe/idempotency-key-reuse-different-params.md"]
    lines = page.splitlines()
    assert lines[0] == f"# `{IDEMPOTENCY_RAW}`"
    assert lines[2] == (
        "**Stripe · POST /v1/payment_intents · SDK `stripe` (pypi) `>=7,<13` · "
        "HTTP 400 `idempotency_error`**"
    )
    assert lines[4] == (
        "Status: ✅ verified:server:prod · first seen 2026-10-22 · last confirmed 2026-10-22 · "
        "1 confirmation from 1 vantage"
    )
    assert "> Reusing an Idempotency-Key with a different request body returns HTTP 400" in page
    assert f"## What to do\n\n1. {render_fix(fact.fixes[0])}.\n" in page
    assert (
        "env: prod · plan: any · region: any · account_state: any · also seen: [sandbox/test_mode]"
        "(idempotency-key-reuse-different-params-sandbox.md) (verified 2026-10-29)"
    ) in page
    assert (
        "Probe `af:stripe:probe:idempotency-key-reuse` "
        "(declarative, [source](../../probes/stripe/idempotency-key-reuse.yaml)) · "
        "official doc: <https://docs.stripe.com/api/idempotent_requests>"
    ) in page
    assert "Observations: none from reporters yet." in page
    signature = f"Match signature (what `check()` matches): `{IDEMPOTENCY}`"
    assert f"## Machine access\n\n{signature}\n" in page
    assert "curl -s https://apifacts.dev/v0/check" in page
    assert '"target":{"method":"POST","url":"https://api.stripe.com/v1/payment_intents"}' in page
    assert f'"error":{{"status":400,"body_excerpt":"{IDEMPOTENCY}"}}' in page
    assert (
        "YAML: [facts/stripe/idempotency-key-reuse-different-params.yaml]"
        "(../../facts/stripe/idempotency-key-reuse-different-params.yaml)"
    ) in page
    assert "Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)" in page


def test_error_string_leads_and_the_normalized_string_stays(registry, pages):
    """Agents search the vendor's message as they got it (case, digits); `check()` matches the
    normalized form, so a fact page shows both and each error stub keeps the normalized one."""
    from apifacts.pages.templates import slug_of

    for fact in registry[1]:
        page = pages.get(f"{fact.service}/{slug_of(fact)}.md")
        if page is None or not (fact.signal and fact.signal.error_string):
            continue
        assert page.startswith(f"# `{fact.signal.error_string}`\n"), fact.id
        if fact.status.value != "retracted":
            assert f"Match signature (what `check()` matches): `{fact.signal.normalized}`" in page
    assert pages["errors/ee9b5326e496.md"].startswith(f"# `{IDEMPOTENCY}`\n")


def test_reported_page_has_yellow_badge_and_no_probe_note(pages):
    page = pages["stripe/customer-retrieve-rate-limit.md"]
    assert "Status: 🟡 reported · first seen 2026-10-26 · last confirmed 2026-10-28 · " in page
    assert "not yet reproduced by a probe" in page
    assert "Observations: 5 distinct reporter networks." in page
    assert "No probe or official document yet." in page


def test_stale_page_is_kept_with_grey_badge_and_claim_title(pages):
    page = pages["stripe/deleted-customer-returns-200.md"]
    assert page.startswith(
        "# Retrieving a deleted customer returns HTTP 200 with deleted set to true"
        " instead of HTTP 404.\n"
    )
    assert "⚪ stale" in page
    assert "not reproduced by the last 3 probe runs; not refuted" in page
    assert "\n> " not in page  # the claim is the title; no quote repeating it


def test_retracted_page_is_one_line_with_the_reason(pages):
    page = pages["stripe/amount-too-small.md"]
    assert page == (
        "# `Amount must be at least $0.50 usd`\n\n"
        "Status: ⛔ retracted 2026-10-27 · reason: duplicate\n\n"
        f"---\n\n{FOOTER}\n"
    )


def test_official_sdk_page(pages):
    page = pages["example/sdk-v2-legacy-endpoint.md"]
    assert page.startswith("# example-sdk 2.x calls the v1 endpoints")
    assert "**Example API · SDK `example-sdk` (pypi) `>=2,<3`**" in page
    assert "Status: 🔵 official · first seen 2026-10-20" in page
    assert "official doc: <https://docs.example.com/sdk/migration-v3>" in page
    assert '-d \'{"target":{"url":"pypi:example-sdk"}}\'' in page


def test_expired_reported_fact_has_no_page_row_or_stub(pages):
    assert "stripe/payment-intent-lock-timeout.md" not in pages
    assert all("payment-intent-lock-timeout" not in text for text in pages.values())
    assert all("lock_timeout" not in text for text in pages.values())


def test_service_index_groups_by_kind_with_badges(pages):
    index = pages["stripe/index.md"]
    assert index.startswith("# Stripe\n\nHosts: `api.stripe.com` · 5 facts\n")
    kinds = [line for line in index.splitlines() if line.startswith("## ")]
    assert kinds == ["## Error meanings", "## Rate limits", "## Silent behavior"]
    assert (
        f"- ✅ verified:server:prod · [`{IDEMPOTENCY_RAW}`]"
        "(idempotency-key-reuse-different-params.md)"
        " · POST /v1/payment_intents · env prod"
    ) in index
    retracted = "- ⛔ retracted · [`Amount must be at least $0.50 usd`](amount-too-small.md)\n"
    assert retracted in index
    rows = [line for line in index.splitlines() if line.startswith("- ")]
    assert rows.index(retracted.strip()) == 2  # last of the error meanings
    assert "- ⚪ stale · [Retrieving a deleted customer" in index


def test_root_index_lists_services_counts_and_version(pages):
    index = pages["index.md"]
    assert "Registry version 2026-10-29 · 2 services · 6 facts." in index
    assert "| [Example API](example/index.md) | 1 | 0 | 1 | 0 | 0 | 0 |" in index
    assert "| [Stripe](stripe/index.md) | 5 | 2 | 0 | 1 | 1 | 1 |" in index
    assert index.index("example/index.md") < index.index("stripe/index.md")


def test_error_stub_points_to_every_fact_with_the_string(pages):
    stubs = {p: t for p, t in pages.items() if p.startswith("errors/")}
    stub = next(t for t in stubs.values() if IDEMPOTENCY in t)
    assert stub.startswith(f"# `{IDEMPOTENCY}`\n")
    prod = "](../stripe/idempotency-key-reuse-different-params.md) · ✅ verified:server:prod"
    assert prod in stub
    assert "](../stripe/idempotency-key-reuse-different-params-sandbox.md)" in stub


def test_registry_version_is_the_latest_date_in_the_data(registry):
    assert registry_version(registry[1]) == "2026-10-29"
    assert registry_version(()) is None


def test_registry_version_override_also_moves_reported_expiry(registry):
    pages = build_pages(*registry, version="2026-12-31")
    assert "Registry version 2026-12-31" in pages["index.md"]
    assert "stripe/customer-retrieve-rate-limit.md" not in pages  # last refresh 2026-10-28


def test_reported_expires_after_30_days(registry):
    fact = _fact(registry, "af:stripe:customer-retrieve-rate-limit")  # last refresh 2026-10-28
    assert published([fact], "2026-11-27") == (fact,)
    assert published([fact], "2026-11-28") == ()


def test_dates_are_utc(registry):
    fact = _fact(registry, "af:stripe:customer-retrieve-rate-limit")
    evidence = fact.evidence.model_copy(update={"first_seen": "2026-10-26T23:30:00.123-05:00"})
    late = fact.model_copy(update={"evidence": evidence})
    services = registry[0]
    page = build_pages(services, [late])["stripe/customer-retrieve-rate-limit.md"]
    assert "first seen 2026-10-27" in page


def test_empty_registry_has_only_the_root_index():
    pages = build_pages((), ())
    assert list(pages) == ["index.md"]
    assert "No services registered yet." in pages["index.md"]
    assert "Registry version none yet" in pages["index.md"]


def test_slug_index_collides_with_the_service_index(registry):
    services, facts = registry
    bad = facts[0].model_copy(update={"id": f"af:{facts[0].service}:index"})
    with pytest.raises(PagesError, match="index"):
        build_pages(services, [bad])


def test_service_key_errors_collides_with_the_stubs(registry):
    services, _ = registry
    with pytest.raises(PagesError, match="errors"):
        build_pages([services[0].model_copy(update={"key": "errors"})], [])


# ── substance (sitemap lastmod) and the HTML head ──────────────────────────────────────────────


def _refreshed(fact):
    """What the nightly evidence refresh does to a fact: counters and dates only (a reported
    fact's last_confirmed is its quorum refresh, which decides whether it keeps a page)."""
    ev = fact.evidence
    bumped = {
        "confirmations": (ev.confirmations or 0) + 5,
        "vantages": (*(ev.vantages or ()), "extra-vantage"),
    }
    if fact.status is not Status.reported:
        bumped["last_confirmed"] = "2026-10-29T03:00:00Z"
    if ev.stale_counter is not None:
        bumped["stale_counter"] = ev.stale_counter + 1
    if ev.observations is not None and ev.observations >= 3:
        bumped["observations"] = ev.observations + 4
    return fact.model_copy(update={"evidence": ev.model_copy(update=bumped)})


def test_a_refresh_does_not_change_any_page_substance(registry):
    services, facts = registry
    before = build_pages(services, facts, version="2026-10-29")
    after = build_pages(services, [_refreshed(f) for f in facts], version="2026-10-30")
    assert before.keys() == after.keys()
    assert any(before[p] != after[p] for p in before)
    for path in before:
        assert substantive(before[path]) == substantive(after[path]), path


def test_a_status_change_is_substance(registry):
    services, facts = registry
    stale = [
        f.model_copy(update={"status": Status.stale}) if f.id == IDEMPOTENCY_ID else f
        for f in facts
    ]
    path = "stripe/idempotency-key-reuse-different-params.md"
    before, after = build_pages(services, facts)[path], build_pages(services, stale)[path]
    assert substantive(before) != substantive(after)


def test_head_title_and_description(registry):
    services, _ = registry
    stripe = next(s for s in services if s.key == "stripe")
    fact = _fact(registry, IDEMPOTENCY_ID)
    assert head_title(fact, stripe) == f"Stripe 400 idempotency_error: {IDEMPOTENCY_RAW} · apifacts"
    assert head_description(fact).startswith("Reusing an Idempotency-Key with a different")
    signal = fact.signal.model_copy(update={"error_string": "word " * 60})
    title = head_title(fact.model_copy(update={"signal": signal}), stripe)
    assert len(title) <= HEAD_TITLE_MAX
    assert title.startswith("Stripe 400 idempotency_error: word word")
    assert title.endswith("word… · apifacts")
