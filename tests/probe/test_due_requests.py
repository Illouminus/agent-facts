"""Quorum → runner hand-off (spec 05 Probe scheduling): a probe can be requested "due now"; it runs
ahead of older probes in the next tick, the per-template budget still applies, and a run clears
the request. A passing run upgrades a `reported` fact to `verified:server:<env>`."""

from datetime import UTC, datetime, timedelta

from probe_builders import probe_doc

from agentfacts.probe.budget import BudgetState
from agentfacts.probe.evidence import apply_outcome
from agentfacts.probe.runner import TickOptions, run_tick
from agentfacts.schema.models import Probe
from agentfacts.schema.yamlio import load_yaml, plain

T0 = datetime(2026, 10, 20, 10, 0, 0, tzinfo=UTC)
ITEMS = [("acme", "GET", "/v1/items")]


def tick(repo, httpserver, at, **options):
    return run_tick(repo.root, repo.state, TickOptions(**options), keys_dir=repo.keys,
                    base_urls={"acme": httpserver.url_for("")}, sleep=lambda s: None,
                    clock=lambda: at, environ={})


def ran(report):
    return [line.probe_id.split(":")[-1] for line in report.lines if line.outcome == "pass"]


def test_request_is_stored_per_vantage_and_cleared_by_a_run(tmp_path):
    with BudgetState(tmp_path / "s.sqlite") as state:
        assert not state.requested("p1", "illouminus")
        state.request_due("p1", "illouminus", 1.0)
        state.request_due("p1", "illouminus", 2.0)  # idempotent
        assert state.requested("p1", "illouminus") and not state.requested("p1", "freebox")
        state.record("p1", ITEMS, "illouminus", 3.0, "pass")
        assert not state.requested("p1", "illouminus")


def test_read_only_state_ignores_requests(tmp_path):
    with BudgetState(tmp_path / "s.sqlite", read_only=True) as state:
        state.request_due("p1", "illouminus", 1.0)
        assert not state.requested("p1", "illouminus")
    assert not (tmp_path / "s.sqlite").exists()


def test_requested_probe_runs_before_older_ones(repo, httpserver):
    repo.service()
    repo.key()
    repo.probe("a-old")
    repo.probe("b-asked", steps=[{"do": "http", "method": "GET", "path": "/v1/items/x"}])
    httpserver.expect_request("/v1/items").respond_with_json({})
    httpserver.expect_request("/v1/items/x").respond_with_json({})
    with BudgetState(repo.state / "probe-state.sqlite") as state:
        state.request_due("af:acme:probe:b-asked", "illouminus", T0.timestamp())
    assert ran(tick(repo, httpserver, T0, max_probes=1)) == ["b-asked"]
    with BudgetState(repo.state / "probe-state.sqlite") as state:
        assert not state.requested("af:acme:probe:b-asked", "illouminus")


def test_request_does_not_bypass_the_budget(repo, httpserver):
    repo.service()
    repo.key()
    repo.probe("a-only")
    httpserver.expect_request("/v1/items").respond_with_json({})
    assert ran(tick(repo, httpserver, T0)) == ["a-only"]
    with BudgetState(repo.state / "probe-state.sqlite") as state:
        state.request_due("af:acme:probe:a-only", "illouminus", T0.timestamp())
    assert ran(tick(repo, httpserver, T0 + timedelta(seconds=10))) == []
    assert ran(tick(repo, httpserver, T0 + timedelta(seconds=300))) == ["a-only"]


def test_pass_upgrades_reported_to_verified(repo):
    path = repo.fact(env="sandbox", status="reported",
                     provenance={"source": "observation_quorum"})
    probe = Probe.model_validate(probe_doc())
    assert apply_outcome(path, probe, "pass", "illouminus", T0) == "verified"
    doc = plain(load_yaml(path))
    assert doc["status"] == "verified:server:sandbox"
    assert doc["evidence"]["confirmations"] == 2
    assert doc["provenance"]["history"][-1] == {
        "date": "2026-10-20", "change": "verified", "by": "bot", "previous_status": "reported"}


def test_fail_keeps_a_reported_fact_reported(repo):
    path = repo.fact(env="sandbox", status="reported")
    probe = Probe.model_validate(probe_doc())
    for _ in range(3):
        apply_outcome(path, probe, "fail", "illouminus", T0)
    assert plain(load_yaml(path))["status"] == "reported"


def test_probe_on_another_endpoint_never_promotes(repo):
    path = repo.fact(env="sandbox", status="reported",
                     target={"surface": "http", "method": "GET", "path_template": "/v1/items/{id}"})
    probe = Probe.model_validate(probe_doc())  # GET /v1/items
    assert apply_outcome(path, probe, "pass", "illouminus", T0) == "confirmed"
    assert plain(load_yaml(path))["status"] == "reported"
