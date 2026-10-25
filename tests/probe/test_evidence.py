"""Outcome → fact evidence (spec 04 Execution, spec 01 status rules and dimension rule)."""

import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
from probe_builders import probe_doc

from apifacts.probe.evidence import apply_outcome, dump_text, load_fact
from apifacts.schema.models import Probe
from apifacts.schema.yamlio import load_yaml, plain

FIXTURE = Path(__file__).parents[1] / "fixtures" / "valid" / (
    "fact-idempotency-key-reuse-different-params.yaml"
)
NOW = datetime(2026, 10, 20, 10, 15, 30, tzinfo=UTC)
SANDBOX = Probe.model_validate(probe_doc())


def data(path):
    return plain(load_yaml(path))


def test_round_trip_is_byte_identical(tmp_path):
    copy = shutil.copy(FIXTURE, tmp_path / "f.yaml")
    assert dump_text(load_fact(Path(copy))) == FIXTURE.read_text(encoding="utf-8")


def test_pass_confirms(repo):
    path = repo.fact()
    assert apply_outcome(path, SANDBOX, "pass", "freebox", NOW) == "confirmed"
    ev = data(path)["evidence"]
    assert ev["last_confirmed"] == "2026-10-20T10:15:30Z"
    assert ev["confirmations"] == 2 and ev["stale_counter"] == 0
    assert ev["vantages"] == ["illouminus", "freebox"]


def test_pass_fills_missing_counters(repo):
    path = repo.fact(evidence={"confirmations": None, "vantages": None})
    text = path.read_text().replace("  confirmations: null\n", "").replace("  vantages: null\n", "")
    path.write_text(text)
    apply_outcome(path, SANDBOX, "pass", "illouminus", NOW)
    ev = data(path)["evidence"]
    assert (ev["confirmations"], ev["vantages"]) == (1, ["illouminus"])


def test_three_failures_make_a_verified_fact_stale(repo):
    path = repo.fact()
    assert [apply_outcome(path, SANDBOX, "fail", "illouminus", NOW) for _ in range(3)] == [
        "failed", "failed", "stale"
    ]
    doc = data(path)
    assert doc["status"] == "stale" and doc["evidence"]["stale_counter"] == 3
    assert doc["provenance"]["history"][-1] == {
        "date": "2026-10-20", "change": "stale", "by": "bot",
        "previous_status": "verified:server:sandbox",
    }
    assert apply_outcome(path, SANDBOX, "fail", "illouminus", NOW) == "failed"
    assert data(path)["evidence"]["stale_counter"] == 4
    assert len(data(path)["provenance"]["history"]) == 2


def test_pass_restores_a_stale_fact(repo):
    path = repo.fact()
    for _ in range(3):
        apply_outcome(path, SANDBOX, "fail", "illouminus", NOW)
    assert apply_outcome(path, SANDBOX, "pass", "illouminus", NOW) == "restored"
    doc = data(path)
    assert doc["status"] == "verified:server:sandbox"
    assert doc["evidence"]["stale_counter"] == 0
    assert doc["provenance"]["history"][-1] == {"date": "2026-10-20", "change": "restored",
                                                "by": "bot"}


def test_stale_without_history_restores_to_the_probe_env(repo):
    path = repo.fact(status="stale")
    assert apply_outcome(path, SANDBOX, "pass", "illouminus", NOW) == "restored"
    assert data(path)["status"] == "verified:server:sandbox"


@pytest.mark.parametrize("fact_overrides", [
    {"env": "prod"},
    {"dimensions": {"account_state": "restricted"}},
])
@pytest.mark.parametrize("outcome", ["pass", "fail"])
def test_other_dimension_never_touches_the_fact(repo, fact_overrides, outcome):
    path = repo.fact(**fact_overrides)
    before = path.read_bytes()
    for _ in range(3):
        assert apply_outcome(path, SANDBOX, outcome, "illouminus", NOW) == "other_dimension"
    assert path.read_bytes() == before


def test_probe_account_state_must_match(repo):
    path = repo.fact(dimensions={"account_state": "restricted"})
    restricted = Probe.model_validate(probe_doc(account_state="restricted"))
    assert apply_outcome(path, restricted, "pass", "illouminus", NOW) == "confirmed"


def test_official_fact_counts_failures_but_keeps_its_status(repo):
    path = repo.fact(status="official", evidence={"official_url": "https://acme.example/docs"})
    for _ in range(3):
        apply_outcome(path, SANDBOX, "fail", "illouminus", NOW)
    doc = data(path)
    assert doc["status"] == "official" and doc["evidence"]["stale_counter"] == 3


def test_retracted_fact_is_untouched(repo):
    path = repo.fact(status="retracted")
    before = path.read_bytes()
    assert apply_outcome(path, SANDBOX, "pass", "illouminus", NOW) == "untouched"
    assert path.read_bytes() == before


def test_invalid_fact_is_not_written(repo):
    path = repo.fact()
    path.write_text(path.read_text().replace("kind: availability", "kind: nonsense"))
    before = path.read_bytes()
    assert apply_outcome(path, SANDBOX, "pass", "illouminus", NOW) == "invalid"
    assert path.read_bytes() == before


def test_comments_survive_an_update(tmp_path):
    path = Path(shutil.copy(FIXTURE, tmp_path / "f.yaml"))
    prod = Probe.model_validate(probe_doc(service="stripe", id="af:stripe:probe:x", env="prod",
                                          steps=[{"do": "http", "method": "GET", "path": "/v1/x"}]))
    assert apply_outcome(path, prod, "pass", "illouminus", NOW) == "confirmed"
    text = path.read_text()
    assert "# stable; af:<service>:<slug>" in text
    assert "first_seen: 2026-10-22T09:14:00Z" in text
    assert "last_confirmed: 2026-10-20T10:15:30Z\n" in text  # plain, still a YAML timestamp
    assert "confirmations: 2\n" in text
    assert "status: verified:server:prod                               # see table" in text


def test_rewrite_keeps_the_file_mode(repo):
    path = repo.fact()
    path.chmod(0o644)
    apply_outcome(path, SANDBOX, "pass", "illouminus", NOW)
    assert path.stat().st_mode & 0o777 == 0o644
