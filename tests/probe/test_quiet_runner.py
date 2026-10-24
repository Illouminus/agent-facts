"""Quiet ticks, `--refresh-evidence` and the rate-limited 403 (spec 04, incident 2026-10-20..24).
Local `httpserver` only."""

import json
from datetime import UTC, datetime, timedelta

from typer.testing import CliRunner
from werkzeug import Response

from agentfacts.cli import app
from agentfacts.probe.ledger import LEDGER_FILE, EvidenceLedger, Pending
from agentfacts.probe.runner import REFRESH_MARKER, TickOptions, refresh_evidence, run_tick
from agentfacts.probe.templating import rfc3339
from agentfacts.schema.yamlio import load_yaml, plain

T0 = datetime(2026, 10, 24, 1, 0, 0, tzinfo=UTC)
FACT_ID = "af:acme:items-list-ok"


class Clock:
    def __init__(self, at=T0):
        self.at = at

    def __call__(self):
        return self.at

    def advance(self, seconds):
        self.at += timedelta(seconds=seconds)


def tick(repo, httpserver, clock, **options):
    return run_tick(repo.root, repo.state, TickOptions(**options), keys_dir=repo.keys,
                    base_urls={"acme": httpserver.url_for("")}, sleep=lambda s: None,
                    clock=clock, environ={})


def pending(repo):
    with EvidenceLedger(repo.state / LEDGER_FILE, read_only=True) as ledger:
        return ledger.get(FACT_ID)


def fact_file(repo):
    return repo.root / "facts" / "acme" / "items-list-ok.yaml"


def setup(repo, httpserver, status=200):
    repo.service()
    repo.key()
    repo.probe()
    repo.fact()
    httpserver.expect_request("/v1/items").respond_with_json({"data": []}, status=status)


def test_twenty_ticks_leave_the_fact_file_alone(repo, httpserver):
    setup(repo, httpserver)
    before = fact_file(repo).read_bytes()
    clock = Clock()
    for _ in range(20):
        report = tick(repo, httpserver, clock)
        assert [line.outcome for line in report.lines] == ["pass"]
        clock.advance(900)
    assert fact_file(repo).read_bytes() == before
    assert len(repo.results()) == 20
    assert all(r["facts"] == [{"id": FACT_ID, "change": "confirmed"}] for r in repo.results())
    assert pending(repo) == Pending(20, rfc3339(T0 + timedelta(seconds=19 * 900)), 0)


def test_a_status_change_still_reaches_the_file(repo, httpserver):
    setup(repo, httpserver, status=404)
    clock = Clock()
    for _ in range(3):
        tick(repo, httpserver, clock)
        clock.advance(900)
    assert plain(load_yaml(fact_file(repo)))["status"] == "stale"
    assert pending(repo) is None


def test_refresh_evidence_flushes_the_ledger_and_leaves_a_marker(repo, httpserver):
    setup(repo, httpserver)
    clock = Clock()
    for _ in range(3):
        tick(repo, httpserver, clock)
        clock.advance(900)
    report = refresh_evidence(repo.root, repo.state, clock=clock, environ={})
    assert report.ok and report.changes["refreshed"] == 1
    ev = plain(load_yaml(fact_file(repo)))["evidence"]
    assert ev["confirmations"] == 4
    assert ev["last_confirmed"] == rfc3339(T0 + timedelta(seconds=1800))
    assert pending(repo) is None
    marker = json.loads((repo.state / REFRESH_MARKER).read_text())
    assert marker == {"refreshed": rfc3339(clock()), "written": 1}
    before = fact_file(repo).read_bytes()
    clock.advance(60)
    again = refresh_evidence(repo.root, repo.state, clock=clock, environ={})
    assert again.changes["refreshed"] == 0 and fact_file(repo).read_bytes() == before
    assert json.loads((repo.state / REFRESH_MARKER).read_text())["written"] == 0


def test_refresh_dry_run_writes_nothing(repo, httpserver):
    setup(repo, httpserver)
    tick(repo, httpserver, Clock())
    before = fact_file(repo).read_bytes()
    report = refresh_evidence(repo.root, repo.state, dry_run=True, clock=Clock(), environ={})
    assert report.changes["would-refresh"] == 1 and report.marker is None
    assert fact_file(repo).read_bytes() == before and pending(repo) is not None
    assert not (repo.state / REFRESH_MARKER).exists()


def test_refresh_respects_the_kill_switch(repo, httpserver):
    setup(repo, httpserver)
    tick(repo, httpserver, Clock())
    report = refresh_evidence(repo.root, repo.state, clock=Clock(),
                              environ={"AGENTFACTS_KILL": "1"})
    assert report.killed == "AGENTFACTS_KILL=1" and pending(repo) is not None


def test_refresh_drops_entries_of_facts_that_are_gone(repo, httpserver):
    setup(repo, httpserver)
    tick(repo, httpserver, Clock())
    fact_file(repo).unlink()
    report = refresh_evidence(repo.root, repo.state, clock=Clock(), environ={})
    assert report.changes["dropped"] == 1 and pending(repo) is None


def test_rate_limited_403_is_an_error_not_evidence(repo, httpserver):
    """GitHub answers a spent primary limit with 403 + X-RateLimit-Remaining: 0 (8 false
    failures of the search probes 21–23.10: the IP's 10/min search limit spent by others)."""
    repo.service()
    repo.key()
    repo.probe(**{"assert": [{"step": 1, "status": 422}]})
    repo.fact()
    httpserver.expect_request("/v1/items").respond_with_response(Response(
        '{"message": "API rate limit exceeded"}', status=403,
        headers={"X-RateLimit-Remaining": "0", "Content-Type": "application/json"}))
    before = fact_file(repo).read_bytes()
    report = tick(repo, httpserver, Clock())
    [line] = report.lines
    assert line.outcome == "error"
    assert line.detail == "step 1: rate limited (403, x-ratelimit-remaining: 0)"
    assert repo.results()[0]["facts"] == []
    assert fact_file(repo).read_bytes() == before and pending(repo) is None


def test_asserted_403_stays_evidence(repo, httpserver):
    repo.service()
    repo.key()
    repo.probe(**{"assert": [{"step": 1, "status": 403}]})
    repo.fact()
    httpserver.expect_request("/v1/items").respond_with_response(Response(
        "{}", status=403, headers={"X-RateLimit-Remaining": "0"}))
    assert [line.outcome for line in tick(repo, httpserver, Clock()).lines] == ["pass"]


def test_cli_refresh_evidence(repo, httpserver):
    setup(repo, httpserver)
    tick(repo, httpserver, Clock())
    args = ["probe", "run", "--refresh-evidence", "--root", str(repo.root),
            "--state-dir", str(repo.state)]
    dry = CliRunner().invoke(app, [*args, "--dry-run"], env={"AGENTFACTS_KILL": "0"})
    assert dry.exit_code == 0, dry.output
    assert "dry run: 1 fact with pending evidence" in dry.stderr
    result = CliRunner().invoke(app, args, env={"AGENTFACTS_KILL": "0"})
    assert result.exit_code == 0, result.output
    assert "evidence refresh: 1 written, 0 unchanged, 0 dropped" in result.stderr
    assert pending(repo) is None


def test_refresh_waits_for_a_running_tick_instead_of_skipping_the_day(repo, httpserver):
    import fcntl
    import threading

    setup(repo, httpserver)
    tick(repo, httpserver, Clock())
    lock = (repo.state / "probe.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX)  # the 03:00 tick is still running
    threading.Timer(0.3, lambda: fcntl.flock(lock, fcntl.LOCK_UN)).start()
    report = refresh_evidence(repo.root, repo.state, clock=Clock(), environ={}, lock_wait_s=5)
    lock.close()
    assert not report.busy and report.changes["refreshed"] == 1


def test_refresh_gives_up_after_the_wait(repo, httpserver):
    import fcntl

    setup(repo, httpserver)
    tick(repo, httpserver, Clock())
    with (repo.state / "probe.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        report = refresh_evidence(repo.root, repo.state, clock=Clock(), environ={},
                                  lock_wait_s=0.2)
    assert report.busy and pending(repo) is not None


def test_cli_refresh_refuses_all(repo):
    result = CliRunner().invoke(app, ["probe", "run", "--refresh-evidence", "--all", "--root",
                                      str(repo.root)], env={"AGENTFACTS_KILL": "0"})
    assert result.exit_code == 2 and "runs no probe" in result.stderr
