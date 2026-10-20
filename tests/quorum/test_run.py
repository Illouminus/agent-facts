"""`quorum run` end to end on a tmp registry: drafts above quorum only, valid by `validate`,
refresh instead of duplicates, probe requests, dry run and kill switch. Then the runner confirms a
draft: reported → verified:server:sandbox (spec 05 Done when)."""

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
from conftest import quorum_rows, row

from agentfacts.probe.budget import BudgetState
from agentfacts.probe.runner import TickOptions, run_tick
from agentfacts.quorum.run import run_quorum
from agentfacts.schema.validate import default_paths, validate_paths
from agentfacts.schema.yamlio import load_yaml, plain

VALID = Path(__file__).parents[1] / "fixtures" / "valid"
NOW = datetime(2026, 10, 21, 10, 0, tzinfo=UTC)
PROBE = "af:stripe:probe:idempotency-key-reuse"
SHORT = "keys for idempotent requests can only be used with the same parameters"
SLUG = "400-keys-for-idempotent-requests-can-only"
KNOWN = ("Keys for idempotent requests can only be used with the same parameters they were "
         "first used with.")


@pytest.fixture
def root(tmp_path) -> Path:
    root = tmp_path / "repo"
    for src, dst in [
        ("service-stripe.yaml", "services/stripe.yaml"),
        ("probe-idempotency-key-reuse.yaml", "probes/stripe/idempotency-key-reuse.yaml"),
        ("fact-idempotency-key-reuse-different-params.yaml",
         "facts/stripe/idempotency-key-reuse-different-params.yaml"),
    ]:
        (root / dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(VALID / src, root / dst)
    return root


def run(root, db, **kw):
    kw.setdefault("now", NOW)
    return run_quorum(root, db, root / "var", **kw)


def doc(path: Path) -> dict:
    return plain(load_yaml(path))


def requested(root, probe=PROBE) -> bool:
    with BudgetState(root / "var" / "probe-state.sqlite", read_only=True) as state:
        return state.requested(probe, "illouminus")


def test_group_above_quorum_becomes_one_valid_draft(root, db, observe):
    observe(*quorum_rows())
    report = run(root, db)
    assert [(line.action, line.fact_id) for line in report.lines] == [
        ("draft", f"af:stripe:{SLUG}")]
    path = root / "facts" / "stripe" / f"{SLUG}.yaml"
    assert report.lines[0].path == path
    assert validate_paths(default_paths(root), root=root).ok
    assert doc(path) == {
        "id": f"af:stripe:{SLUG}",
        "service": "stripe",
        "kind": "error_meaning",
        "target": {"surface": "http", "method": "POST", "path_template": "/v1/payment_intents"},
        "signal": {"status": 400, "normalized": SHORT},
        "claim": f'POST /v1/payment_intents returns HTTP 400 with "{SHORT}".',
        "dimensions": {"env": "sandbox"},  # the probe's env: reporters did not say
        "fixes": [{"action": "none_known", "reason_kind": "investigating"}],
        "status": "reported",
        "evidence": {"probe": PROBE, "first_seen": "2026-10-20T10:00:00Z", "observations": 3},
        "provenance": {
            "source": "observation_quorum", "author": "bot", "created": "2026-10-21",
            "history": [{"date": "2026-10-21", "change": "created", "by": "bot"}],
        },
    }
    assert "2026-10-20T10:00:00Z" in path.read_text()  # plain timestamps, like hand-written facts
    assert requested(root)


def test_below_quorum_writes_nothing(root, db, observe):
    observe(row(1, ua="sdk"), row(2, ua="pytest-plugin"))  # two networks
    before = sorted(p.name for p in (root / "facts" / "stripe").iterdir())
    report = run(root, db)
    assert [line.action for line in report.lines] == ["below"]
    assert sorted(p.name for p in (root / "facts" / "stripe").iterdir()) == before
    assert not requested(root)


def test_second_run_refreshes_instead_of_duplicating(root, db, observe):
    observe(*quorum_rows())
    run(root, db)
    observe(row(4, ua="mcp"))
    later = datetime(2026, 10, 22, 9, 0, tzinfo=UTC)
    report = run(root, db, now=later)
    assert [line.action for line in report.lines] == ["refresh"]
    files = sorted(p.stem for p in (root / "facts" / "stripe").iterdir())
    assert files == [SLUG, "idempotency-key-reuse-different-params"]
    evidence = doc(root / "facts" / "stripe" / f"{SLUG}.yaml")["evidence"]
    assert evidence["observations"] == 4 and evidence["last_confirmed"] == "2026-10-22T09:00:00Z"
    again = run(root, db, now=later)  # same day, same count: nothing to write
    assert [line.action for line in again.lines] == ["covered"]


def test_known_fact_only_gets_its_observation_count(root, db, observe):
    path = root / "facts" / "stripe" / "idempotency-key-reuse-different-params.yaml"
    observe(*quorum_rows(message=KNOWN))
    before = doc(path)
    report = run(root, db)
    assert [(line.action, line.fact_id) for line in report.lines] == [
        ("refresh", "af:stripe:idempotency-key-reuse-different-params")]
    before["evidence"]["observations"] = 3
    assert doc(path) == before  # verified fact: no last_confirmed from the quorum
    assert "# stable; af:<service>:<slug>" in path.read_text()  # comments survive


def test_slug_is_deduplicated(root, db, observe):
    (root / "facts" / "stripe" / f"{SLUG}.yaml").write_text("not a fact\n")
    observe(*quorum_rows())
    report = run(root, db)
    assert report.lines[0].fact_id == f"af:stripe:{SLUG}-2"


def test_reporters_env_decides_and_a_probe_of_another_env_is_not_used(root, db, observe):
    observe(*quorum_rows(env="prod"))
    report = run(root, db)
    (line,) = report.lines
    assert (line.action, line.probe_id, line.detail) == ("draft", None, "needs a probe")
    fact = doc(line.path)
    assert fact["dimensions"] == {"env": "prod"} and "probe" not in fact["evidence"]
    assert not requested(root)


def test_status_only_group_is_a_rate_limit_draft(root, db, observe):
    observe(*quorum_rows(message=None, status=429))
    (line,) = run(root, db).lines
    fact = doc(line.path)
    assert line.fact_id == "af:stripe:429"
    assert (fact["kind"], fact["signal"]) == ("rate_limit", {"status": 429})
    assert fact["claim"] == "POST /v1/payment_intents returns HTTP 429, a rate-limit response."
    assert fact["dimensions"] == {"env": "prod"}  # no probe asserts 429: default env


def test_unregistered_template_is_skipped(root, db, observe):
    observe(*quorum_rows(template="/v1/charges"))
    (line,) = run(root, db).lines
    assert line.action == "skipped"
    assert not (root / "facts" / "stripe" / f"{SLUG}.yaml").exists()


def test_dry_run_writes_nothing(root, db, observe):
    observe(*quorum_rows())
    report = run(root, db, dry_run=True)
    assert [line.action for line in report.lines] == ["draft"]
    assert not report.lines[0].path.exists()
    assert not (root / "var").exists()


@pytest.mark.parametrize("kill", ["file", "env"])
def test_kill_switch_stops_the_quorum(root, db, observe, kill):
    observe(*quorum_rows())
    environ = {"AGENTFACTS_KILL": "1"} if kill == "env" else {}
    if kill == "file":
        (root / "ops").mkdir()
        (root / "ops" / "KILL").write_text("")
    report = run(root, db, environ=environ)
    assert report.killed and report.lines == []
    assert not (root / "facts" / "stripe" / f"{SLUG}.yaml").exists()


def test_probe_run_confirms_the_draft(root, db, observe, httpserver):
    """The hand-off works: the quorum's draft cites the probe, the next tick runs it first, a
    pass makes the draft verified:server:sandbox."""
    observe(*quorum_rows())
    run(root, db)
    keys = root / "keys"
    keys.mkdir()
    (keys / "stripe-test.key").write_text("sk_test_FAKEfake0123456789abcdefXYZ\n")
    body = {"error": {"code": "idempotency_error", "message": KNOWN}}
    httpserver.expect_request("/v1/payment_intents").respond_with_json(body, status=400)
    report = run_tick(root, root / "var", TickOptions(), keys_dir=keys,
                      base_urls={"stripe": httpserver.url_for("")}, sleep=lambda s: None,
                      clock=lambda: NOW, environ={})
    assert [(line.probe_id, line.outcome) for line in report.lines] == [(PROBE, "pass")]
    fact = doc(root / "facts" / "stripe" / f"{SLUG}.yaml")
    assert fact["status"] == "verified:server:sandbox"
    assert fact["provenance"]["history"][-1]["change"] == "verified"
    assert not requested(root)
    assert validate_paths(default_paths(root), root=root).ok
    results = [json.loads(x) for x in (root / "var" / "results.jsonl").read_text().splitlines()]
    assert {"id": f"af:stripe:{SLUG}", "change": "verified"} in results[0]["facts"]
