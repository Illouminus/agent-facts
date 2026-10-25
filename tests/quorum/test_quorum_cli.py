"""`apifacts quorum run` on the command line."""

import shutil
from pathlib import Path

import pytest
from quorum_fixtures import quorum_rows
from typer.testing import CliRunner

from apifacts.cli import app

VALID = Path(__file__).parents[1] / "fixtures" / "valid"
runner = CliRunner()


@pytest.fixture
def root(tmp_path) -> Path:
    root = tmp_path / "repo"
    (root / "services").mkdir(parents=True)
    shutil.copy(VALID / "service-stripe.yaml", root / "services" / "stripe.yaml")
    return root


def invoke(*args, env=None):
    return runner.invoke(app, ["quorum", "run", *args], env=env or {"APIFACTS_KILL": "0"})


def test_dry_run_prints_the_draft_and_writes_nothing(root, db, observe, monkeypatch):
    rows = quorum_rows(at=_this_week())
    observe(*rows)
    r = invoke("--root", str(root), "--db", str(db), "--dry-run")
    assert r.exit_code == 0, r.output
    assert "draft    af:stripe:400-keys-for-idempotent-requests-can-only" in r.output
    assert "needs a probe" in r.output
    assert "dry run: 1 groups in" in r.output and "1 draft" in r.output
    assert not (root / "facts").exists() and not (root / "var").exists()


def test_real_run_writes_the_draft(root, db, observe):
    observe(*quorum_rows(at=_this_week()))
    r = invoke("--root", str(root), "--db", str(db))
    assert r.exit_code == 0, r.output
    assert (root / "facts" / "stripe" / "400-keys-for-idempotent-requests-can-only.yaml").is_file()


def test_db_from_the_environment_and_empty_period(root, tmp_path):
    r = invoke("--root", str(root), env={"APIFACTS_DB": str(tmp_path / "none.sqlite")})
    assert r.exit_code == 0 and "0 groups in" in r.output


def test_kill_switch(root, db, observe):
    observe(*quorum_rows(at=_this_week()))
    r = invoke("--root", str(root), "--db", str(db), env={"APIFACTS_KILL": "1"})
    assert r.exit_code == 0 and "killed (APIFACTS_KILL=1)" in r.output
    assert not (root / "facts").exists()


@pytest.mark.parametrize("value", ["yesterday", "2999-01-01"])
def test_bad_since_period_is_a_usage_error(root, value):
    assert invoke("--root", str(root), "--since-period", value).exit_code == 2


def test_past_period(root, db, observe):
    observe(*quorum_rows(at="2026-10-14T12:00:00Z"))
    r = invoke("--root", str(root), "--db", str(db), "--since-period", "2026-10-15", "--dry-run")
    assert r.exit_code == 0
    assert "2026-10-12 00:00 → 2026-10-19 00:00 UTC" in r.output and "1 draft" in r.output


def _this_week() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
