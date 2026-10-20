"""`agentfacts probe run|list` (spec 04, 09 § W2). Dry runs only: the CLI has no URL test seam."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from agentfacts.cli import app

FIXTURE = Path(__file__).parents[1] / "fixtures" / "probe-repo"
runner = CliRunner()


@pytest.fixture(autouse=True)
def _no_kill_env(monkeypatch):
    monkeypatch.delenv("AGENTFACTS_KILL", raising=False)


def invoke(*args):
    return runner.invoke(app, ["probe", *args])


def test_probe_is_registered():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0 and "probe" in result.stdout


def test_dry_run_all_on_the_fixture(tmp_path):
    state = tmp_path / "state"
    result = invoke("run", "--all", "--dry-run", "--root", str(FIXTURE), "--state-dir", str(state))
    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines() == [
        "would-run af:example:probe:item-missing — 1 request",
        "would-run af:example:probe:status-ok — 1 request",
        "skipped:no_key af:examplepay:probe:charge-roundtrip — no key examplepay-fixture",
    ]
    assert "dry run: 2 would run, 1 skipped:no_key, 0 not due, 0 deferred" in result.stderr
    assert not state.exists()


def test_default_mode_is_due_and_respects_max(tmp_path):
    result = invoke("run", "--dry-run", "--max", "1", "--root", str(FIXTURE),
                    "--state-dir", str(tmp_path))
    assert result.exit_code == 0, result.output
    assert [line.split()[0] for line in result.stdout.splitlines()] == [
        "would-run", "deferred", "skipped:no_key"]


def test_list_shows_every_probe(tmp_path):
    result = invoke("list", "--root", str(FIXTURE), "--state-dir", str(tmp_path))
    assert result.exit_code == 0, result.output
    lines = result.stdout.splitlines()
    assert len(lines) == 3
    by_id = {line.split()[0]: line for line in lines}
    assert "key:none" in by_id["af:example:probe:status-ok"]
    assert "key:missing" in by_id["af:examplepay:probe:charge-roundtrip"]
    assert all("last:never" in line and line.endswith("due") for line in lines)
    assert not any(tmp_path.iterdir())


@pytest.mark.parametrize("args", [
    ["run", "--vantage", "Bad Name"],
    ["run", "--max", "-1"],
    ["run", "--max-requests", "-1"],
    ["list", "--vantage", "UPPER"],
])
def test_usage_errors_exit_2(args, tmp_path):
    result = invoke(*args, "--root", str(FIXTURE), "--state-dir", str(tmp_path))
    assert result.exit_code == 2, result.output


def test_kill_switch_exits_0_without_requests(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTFACTS_KILL", "1")
    result = invoke("run", "--all", "--root", str(FIXTURE), "--state-dir", str(tmp_path))
    assert result.exit_code == 0
    assert "kill switch on (AGENTFACTS_KILL=1): no requests" in result.stderr
    assert result.stdout == "" and not any(tmp_path.iterdir())


def test_invalid_probe_files_exit_1(tmp_path):
    root = tmp_path / "repo"
    (root / "probes" / "example").mkdir(parents=True)
    (root / "probes" / "example" / "broken.yaml").write_text("id: af:example:probe:broken\n"
                                                             "steps: []\n")
    result = invoke("run", "--dry-run", "--root", str(root), "--state-dir", str(tmp_path / "s"))
    assert result.exit_code == 1
    assert "broken.yaml:" in result.stderr


def test_fixture_is_valid():
    result = runner.invoke(app, ["validate", "--root", str(FIXTURE)])
    assert result.exit_code == 0, result.output


def test_kill_switch_does_not_hide_invalid_files(tmp_path, monkeypatch):
    import agentfacts.probe.cli as cli_module
    from agentfacts.probe.runner import TickReport
    from agentfacts.schema.validate import Problem

    report = TickReport(killed="ops/KILL", results_path=tmp_path / "r.jsonl",
                        problems=[Problem(Path("probes/x/y.yaml"), 1, "schema_required", "bad")])
    monkeypatch.setattr(cli_module, "run_tick", lambda *a, **k: report)
    result = invoke("run", "--root", str(tmp_path))
    assert result.exit_code == 1
    assert "y.yaml:1: schema_required bad" in result.stderr
    assert "kill switch on (ops/KILL)" in result.stderr


def test_busy_tick_exits_0(tmp_path, monkeypatch):
    import agentfacts.probe.cli as cli_module
    from agentfacts.probe.runner import TickReport

    monkeypatch.setattr(cli_module, "run_tick", lambda *a, **k: TickReport(busy=True))
    result = invoke("run", "--root", str(tmp_path))
    assert result.exit_code == 0 and "another tick is running" in result.stderr
