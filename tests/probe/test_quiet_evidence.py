"""Quiet evidence (spec 04, incident 2026-10-20..24): with a ledger, a fact's YAML changes only on
a status change, a first confirmation from a new vantage, or the daily refresh."""

from datetime import UTC, datetime, timedelta

import pytest
from probe_builders import probe_doc

from agentfacts.probe.evidence import apply_outcome, refresh_from_ledger
from agentfacts.probe.ledger import EvidenceLedger, Pending
from agentfacts.probe.templating import rfc3339
from agentfacts.schema.models import Probe
from agentfacts.schema.yamlio import load_yaml, plain

NOW = datetime(2026, 10, 24, 10, 0, 0, tzinfo=UTC)
TICK = timedelta(minutes=15)
SANDBOX = Probe.model_validate(probe_doc())
FACT_ID = "af:acme:items-list-ok"


def data(path):
    return plain(load_yaml(path))


@pytest.fixture
def ledger(tmp_path):
    with EvidenceLedger(tmp_path / "var" / "evidence-pending.sqlite") as led:
        yield led


def run(path, ledger, outcomes, vantage="illouminus", start=NOW):
    return [apply_outcome(path, SANDBOX, o, vantage, start + i * TICK, ledger=ledger)
            for i, o in enumerate(outcomes)]


def test_twenty_passes_leave_the_yaml_alone(repo, ledger):
    path = repo.fact()
    before = path.read_bytes()
    assert run(path, ledger, ["pass"] * 20) == ["confirmed"] * 20
    assert path.read_bytes() == before
    assert ledger.get(FACT_ID) == Pending(20, rfc3339(NOW + 19 * TICK), 0)


def test_failures_below_the_threshold_stay_in_the_ledger(repo, ledger):
    path = repo.fact()
    before = path.read_bytes()
    assert run(path, ledger, ["fail", "fail"]) == ["failed", "failed"]
    assert path.read_bytes() == before
    assert ledger.get(FACT_ID).stale_counter == 2
    assert run(path, ledger, ["pass"]) == ["confirmed"]
    assert ledger.get(FACT_ID) == Pending(1, rfc3339(NOW), 0)


def test_status_change_writes_the_yaml_with_the_pending_counters(repo, ledger):
    path = repo.fact()
    run(path, ledger, ["pass"] * 5)
    assert run(path, ledger, ["fail"] * 3, start=NOW + 5 * TICK) == ["failed", "failed", "stale"]
    doc = data(path)
    assert doc["status"] == "stale"
    assert doc["evidence"]["confirmations"] == 6  # 1 in the YAML + 5 pending
    assert doc["evidence"]["last_confirmed"] == rfc3339(NOW + 4 * TICK)
    assert doc["evidence"]["stale_counter"] == 3
    assert doc["provenance"]["history"][-1]["change"] == "stale"
    assert ledger.get(FACT_ID) is None


def test_restore_writes_at_once(repo, ledger):
    path = repo.fact()
    run(path, ledger, ["fail"] * 3)
    assert run(path, ledger, ["pass"], start=NOW + 3 * TICK) == ["restored"]
    doc = data(path)
    assert doc["status"] == "verified:server:sandbox" and doc["evidence"]["stale_counter"] == 0
    assert ledger.get(FACT_ID) is None


def test_reported_fact_verified_by_its_probe_writes_at_once(repo, ledger):
    path = repo.fact(status="reported", provenance={"source": "observation_quorum"})
    assert run(path, ledger, ["pass"]) == ["verified"]
    assert data(path)["status"] == "verified:server:sandbox"
    assert ledger.get(FACT_ID) is None


def test_first_confirmation_from_a_new_vantage_writes_once(repo, ledger):
    path = repo.fact()
    run(path, ledger, ["pass"] * 2)
    assert run(path, ledger, ["pass"], vantage="freebox", start=NOW + 2 * TICK) == ["confirmed"]
    ev = data(path)["evidence"]
    assert ev["vantages"] == ["illouminus", "freebox"]
    assert ev["confirmations"] == 4 and ev["last_confirmed"] == rfc3339(NOW + 2 * TICK)
    assert ledger.get(FACT_ID) is None
    before = path.read_bytes()
    run(path, ledger, ["pass"], vantage="freebox", start=NOW + 3 * TICK)
    assert path.read_bytes() == before  # known vantage: back to the ledger


def test_refresh_flushes_and_clears(repo, ledger):
    path = repo.fact()
    run(path, ledger, ["pass"] * 3)
    assert refresh_from_ledger(path, ledger) == "refreshed"
    ev = data(path)["evidence"]
    assert (ev["confirmations"], ev["last_confirmed"], ev["stale_counter"]) == (
        4, rfc3339(NOW + 2 * TICK), 0)
    assert ledger.get(FACT_ID) is None
    before = path.read_bytes()
    assert refresh_from_ledger(path, ledger) == "untouched"  # nothing pending
    assert path.read_bytes() == before


def test_refresh_with_nothing_new_writes_nothing(repo, ledger):
    path = repo.fact(evidence={"stale_counter": 0})
    before = path.read_bytes()
    ledger.put(FACT_ID, Pending(0, "2026-10-01T09:00:00Z", 0))
    assert refresh_from_ledger(path, ledger) == "unchanged"
    assert path.read_bytes() == before and ledger.get(FACT_ID) is None


def test_refresh_drops_the_entry_of_a_retracted_fact(repo, ledger):
    path = repo.fact(status="retracted")
    before = path.read_bytes()
    ledger.put(FACT_ID, Pending(2, rfc3339(NOW), 0))
    assert refresh_from_ledger(path, ledger) == "untouched"
    assert path.read_bytes() == before and ledger.get(FACT_ID) is None


def test_without_a_ledger_every_outcome_is_written(repo):
    path = repo.fact()
    before = path.read_bytes()
    assert apply_outcome(path, SANDBOX, "pass", "illouminus", NOW) == "confirmed"
    assert path.read_bytes() != before
