"""Runner + bot together (incident 2026-10-20..24: 62 bot PRs in three days). Real git with a bare
origin, the real runner against a local `httpserver`, a fake `gh`: 20 ticks open no PR, a status
change opens one at once, the daily evidence refresh opens one a day."""

import json
from datetime import UTC, date, datetime, timedelta

import pytest
import yaml
from bot_repo import Checkout, FakeGh, sh

from agentfacts.bot.pr import publish
from agentfacts.pages.build import build_pages, load_registry, sync
from agentfacts.probe.runner import TickOptions, refresh_evidence, run_tick
from agentfacts.schema.yamlio import load_yaml, plain

TODAY = date(2026, 10, 21)
T0 = datetime(2026, 10, 21, 1, 0, 0, tzinfo=UTC)
SANDBOX = "facts/stripe/idempotency-sandbox.yaml"
KNOWN = "facts/stripe/idempotency-key-reuse-different-params.yaml"
IDEMPOTENCY_ERROR = {"error": {"code": "idempotency_error", "message": (
    "Keys for idempotent requests can only be used with the same parameters they were first "
    "used with.")}}


class World:
    def __init__(self, tmp, httpserver):
        self.repo = Checkout(tmp)
        self.work = self.repo.work
        self.state = tmp / "state"
        self.keys = tmp / "keys"
        self.keys.mkdir()
        (self.keys / "stripe-test.key").write_text("sk_test_FAKEfake0123456789abcdefXYZ\n")
        doc = plain(load_yaml(self.work / KNOWN))
        doc["id"] = "af:stripe:idempotency-sandbox"
        doc["dimensions"]["env"] = "sandbox"
        doc["status"] = "verified:server:sandbox"
        self.repo.write(SANDBOX, yaml.safe_dump(doc, sort_keys=False))
        sync(self.work / "pages", build_pages(*load_registry(self.work)))
        sh(self.work, "add", "-A")
        sh(self.work, "commit", "--quiet", "-m", "sandbox fact")
        sh(self.work, "push", "--quiet", "origin", "main")
        sh(self.work, "fetch", "--quiet", "origin")
        self.httpserver = httpserver
        self.clock = T0
        self.gh = FakeGh()
        self.answer = IDEMPOTENCY_ERROR, 400
        httpserver.expect_request("/v1/payment_intents").respond_with_handler(self._handler)

    def _handler(self, request):
        from werkzeug import Response

        body, status = self.answer
        return Response(json.dumps(body), status=status, content_type="application/json")

    def tick(self, ok=True, vantage="illouminus"):
        self.answer = (IDEMPOTENCY_ERROR, 400) if ok else ({"id": "pi_1"}, 200)
        report = run_tick(self.work, self.state, TickOptions(vantage=vantage), keys_dir=self.keys,
                          base_urls={"stripe": self.httpserver.url_for("")},
                          sleep=lambda s: None, clock=lambda: self.clock, environ={})
        assert [line.outcome for line in report.lines] == ["pass" if ok else "fail"], report.lines
        self.clock += timedelta(minutes=15)

    def refresh(self):
        assert refresh_evidence(self.work, self.state, clock=lambda: self.clock, environ={}).ok

    def publish(self, today=TODAY):
        return publish(self.work, today=today, environ={}, gh=self.gh, state_dir=self.state)

    def facts_status(self):
        return sh(self.work, "status", "--porcelain", "--", "facts")

    def pr_titles(self):
        return [c[c.index("--title") + 1] for c in self.gh.calls if c[:2] == ["pr", "create"]]


@pytest.fixture
def world(tmp_path, httpserver):
    return World(tmp_path, httpserver)


def test_twenty_ticks_open_no_pr(world):
    for _ in range(20):
        world.tick()
        assert world.publish().action == "nothing"
    assert world.facts_status() == ""  # the YAML never changed
    assert world.pr_titles() == [] and world.gh.calls == []


def test_status_change_opens_one_pr_at_once(world):
    for _ in range(5):
        world.tick()
    for _ in range(3):
        world.tick(ok=False)
    report = world.publish()
    assert report.action == "opened"
    assert world.pr_titles() == ["facts: 1 fact file (2026-10-21)"]
    published = yaml.safe_load(world.repo.show(report.branch, SANDBOX))
    assert published["status"] == "stale" and published["evidence"]["confirmations"] == 6


def test_daily_refresh_opens_one_pr_a_day(world):
    for _ in range(20):
        world.tick()
    world.refresh()
    assert world.facts_status().strip() == f"M {SANDBOX}"
    report = world.publish()
    assert report.action == "opened"
    assert world.pr_titles() == ["facts: daily evidence refresh (2026-10-21)"]
    published = yaml.safe_load(world.repo.show(report.branch, SANDBOX))
    assert published["evidence"]["confirmations"] == 21
    # the same day: more ticks, another refresh → held for tomorrow, still one PR
    world.tick()
    world.refresh()
    again = world.publish()
    assert (again.action, again.detail) == ("holding", "today's evidence PR is already open")
    assert len(world.pr_titles()) == 1
    tomorrow = world.publish(today=TODAY + timedelta(days=1))
    assert tomorrow.action == "opened" and len(world.pr_titles()) == 2


def test_counter_change_without_a_refresh_waits(world):
    world.tick(vantage="freebox")  # first confirmation from a new vantage: written at once
    assert world.facts_status().strip() == f"M {SANDBOX}"
    report = world.publish()
    assert report.action == "holding" and world.gh.calls == []
    assert report.detail == "no evidence refresh yet (probe run --refresh-evidence)"


def test_refresh_already_published_waits_for_the_next_one(world):
    world.tick()
    world.refresh()
    assert world.publish().action == "opened"
    world.tick(vantage="freebox")
    report = world.publish(today=TODAY + timedelta(days=1))
    assert (report.action, report.detail) == ("holding",
                                              "waiting for the next daily evidence refresh")


def test_substance_change_carries_the_counters_along(world):
    world.tick(vantage="freebox")  # counters only
    world.repo.write("facts/stripe/second.yaml", world.repo.show("main", SANDBOX).replace(
        "af:stripe:idempotency-sandbox", "af:stripe:second"))
    report = world.publish()
    assert report.action == "opened"
    assert world.pr_titles() == ["facts: 2 fact files (2026-10-21)"]
    assert {SANDBOX, "facts/stripe/second.yaml"} <= set(world.repo.files_in(report.branch))
