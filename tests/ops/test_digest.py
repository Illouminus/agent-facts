"""ops/digest.py: weekly digest from facts/, results.jsonl and observations.sqlite (spec 08).

Fixtures only: no network except a local fake of the Telegram gateway, no VPS.
"""

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import digest
import pytest
import yaml
from ops_builders import (
    OFFICIAL,
    REPO,
    REPORTED,
    RETRACTED,
    STALE,
    make_db,
    run_record,
    write_results,
)

MONDAY = datetime(2026, 10, 26, 6, 0, tzinfo=UTC)  # 08:00 Paris
TUESDAY = datetime(2026, 10, 20, 13, 0, tzinfo=UTC)
WEEK43 = digest.salt_window(MONDAY)  # 2026-10-19 → 2026-10-26


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text)


# ── window ─────────────────────────────────────────────────────────────────────────────────────


def test_window_on_monday_is_the_last_complete_salt_period():
    w = digest.salt_window(MONDAY)
    assert (w.start, w.end) == (utc("2026-10-19T00:00Z"), utc("2026-10-26T00:00Z"))
    assert w.complete
    assert w.week == 43
    assert w.days == tuple(f"2026-10-{d}" for d in range(19, 26))


def test_window_midweek_is_the_previous_period():
    w = digest.salt_window(TUESDAY)
    assert (w.start, w.end) == (utc("2026-10-12T00:00Z"), utc("2026-10-19T00:00Z"))
    assert w.week == 42


def test_current_window_runs_from_this_monday_to_now():
    w = digest.salt_window(TUESDAY, current=True)
    assert (w.start, w.end, w.complete) == (utc("2026-10-19T00:00Z"), TUESDAY, False)
    assert w.days == ("2026-10-19", "2026-10-20")


def test_window_at_monday_midnight_ends_there():
    w = digest.salt_window(utc("2026-10-26T00:00Z"))
    assert w.end == utc("2026-10-26T00:00Z")


def test_naive_now_is_refused():
    with pytest.raises(ValueError):
        digest.salt_window(datetime(2026, 10, 26, 6, 0))


# ── facts ──────────────────────────────────────────────────────────────────────────────────────


def facts_of(registry):
    from apifacts.pages.build import load_registry

    return load_registry(registry.root)[1]


def test_fact_metrics_by_status_added_and_needs_probe(registry):
    registry.fact("new-verified", provenance__created="2026-10-20",
                  evidence__last_confirmed="2026-10-21T10:00:00Z")
    registry.fact("old-verified", provenance__created="2026-10-01",
                  evidence__last_confirmed="2026-10-02T10:00:00Z")
    registry.fact("reported-no-probe", base=REPORTED, provenance__created="2026-10-25")
    registry.fact("stale", base=STALE, provenance__created="2026-10-10",
                  evidence__first_seen="2026-10-09T07:00:00Z",
                  evidence__last_confirmed="2026-10-10T07:00:00Z")
    registry.fact("retracted", base=RETRACTED, provenance__created="2026-10-26")  # after window
    registry.fact("official", base=OFFICIAL, provenance__created="2026-10-19")
    m = digest.fact_metrics(facts_of(registry), WEEK43)
    assert m.total == 6
    assert m.counts == {"verified": 2, "official": 1, "reported": 1, "stale": 1, "retracted": 1}
    assert m.added == 3
    assert m.confirmed == 1
    assert m.by_service == {"example": 1, "stripe": 5}
    assert m.needs_probe == ("af:stripe:reported-no-probe",)


def test_reported_fact_with_a_probe_does_not_need_one(registry):
    registry.fact("reported-probed", base=REPORTED, evidence__probe="af:stripe:probe:p1")
    assert digest.fact_metrics(facts_of(registry), WEEK43).needs_probe == ()


# ── probes ─────────────────────────────────────────────────────────────────────────────────────


def services_of(registry):
    from apifacts.pages.build import load_registry

    return load_registry(registry.root)[0]


def test_probe_metrics_count_only_runs_inside_the_window(registry, tmp_path):
    path = write_results(tmp_path / "results.jsonl", [
        run_record("2026-10-18T23:59:59Z"),  # before
        run_record("2026-10-19T00:00:00Z", "pass"),
        run_record("2026-10-20T00:00:00Z", "fail", probe_id="af:stripe:probe:p2"),
        run_record("2026-10-21T00:00:00Z", "error"),
        run_record("2026-10-22T00:00:00Z", "skipped:no_key", detail="no key stripe-test"),
        run_record("2026-10-23T00:00:00Z", "skipped:no_key", detail="no key stripe-test"),
        run_record("2026-10-26T00:00:00Z"),  # after (end is exclusive)
    ])
    m = digest.probe_metrics(path, services_of(registry), WEEK43)
    assert m.available
    assert m.outcomes == {"pass": 1, "fail": 1, "error": 1, "skipped:no_key": 2}
    assert m.runs == 3
    assert m.probes == 2
    assert m.vantages == {"illouminus": 3}
    assert m.missing_keys == ("stripe-test",)
    assert m.last_run == "2026-10-21T00:00:00Z"


def test_budget_violation_is_two_runs_on_one_template_closer_than_the_budget(registry, tmp_path):
    # stripe probe_budget.per_template_seconds = 300
    path = write_results(tmp_path / "results.jsonl", [
        run_record("2026-10-20T10:00:00Z", probe_id="af:stripe:probe:a"),
        run_record("2026-10-20T10:04:59Z", probe_id="af:stripe:probe:b"),  # 299 s: violation
        run_record("2026-10-20T10:10:00Z", probe_id="af:stripe:probe:a"),  # 301 s: fine
        run_record("2026-10-20T10:10:30Z", probe_id="af:stripe:probe:c",
                   template="/v1/payment_intents", method="POST"),  # other template: fine
        run_record("2026-10-20T10:11:00Z", probe_id="af:stripe:probe:a", vantage="freebox"),
        run_record("2026-10-20T10:11:30Z", "skipped:no_key", detail="no key stripe-test"),
    ])
    m = digest.probe_metrics(path, services_of(registry), WEEK43)
    assert m.budget_violations == 1
    assert m.violation_keys == ("stripe GET /v1/customers/{id} @illouminus",)
    assert m.budget_bypassed == 0


def test_run_all_is_not_a_budget_violation(registry, tmp_path):
    # 20.10.2026: the first `probe run --all` (30 probes, seconds apart on shared templates) printed
    # «нарушений бюджета 20»; --all skips the budget by design, a --due tick never pairs like that.
    path = write_results(tmp_path / "results.jsonl", [
        run_record("2026-10-20T13:57:57Z", probe_id="af:stripe:probe:a", selection="all"),
        run_record("2026-10-20T13:57:58Z", probe_id="af:stripe:probe:b", selection="all"),
        run_record("2026-10-20T13:57:59Z", probe_id="af:stripe:probe:c", selection=None),  # legacy
        run_record("2026-10-20T14:01:00Z", probe_id="af:stripe:probe:a"),  # due after --all: real
        run_record("2026-10-20T14:15:00Z", probe_id="af:stripe:probe:b"),  # due, 14 min: fine
    ])
    m = digest.probe_metrics(path, services_of(registry), WEEK43)
    assert (m.budget_violations, m.budget_bypassed) == (1, 2)
    assert m.violation_keys == ("stripe GET /v1/customers/{id} @illouminus",)


def test_bad_lines_are_counted_not_fatal(registry, tmp_path):
    path = tmp_path / "results.jsonl"
    path.write_text('{"broken\n' + json.dumps(run_record("2026-10-20T00:00:00Z")) + "\n",
                    encoding="utf-8")
    m = digest.probe_metrics(path, services_of(registry), WEEK43)
    assert (m.runs, m.bad_lines) == (1, 1)


def test_missing_results_file_reads_as_unavailable(registry, tmp_path):
    m = digest.probe_metrics(tmp_path / "nope.jsonl", services_of(registry), WEEK43)
    assert not m.available
    assert m.runs == 0


# ── check() ────────────────────────────────────────────────────────────────────────────────────


def test_check_metrics_from_counters_and_rows(tmp_path):
    db = make_db(tmp_path / "observations.sqlite", [
        {"received_at": "2026-10-19T08:00:00Z", "reporter_net": "n1"},
        {"received_at": "2026-10-20T08:00:00Z", "reporter_net": "n1"},
        {"received_at": "2026-10-21T08:00:00Z", "reporter_net": "n2",
         "reporter_ua_class": "sdk"},
        {"received_at": "2026-10-26T08:00:00Z", "reporter_net": "n3"},  # after
    ], [
        ("2026-10-19", "stored", 2), ("2026-10-21", "stored", 1),
        ("2026-10-20", "unregistered_target", 5),
        ("2026-10-20", "unregistered_target:api.notion.com", 3),
        ("2026-10-20", "unregistered_target:other", 2),
        ("2026-10-22", "unregistered_target", 1),
        ("2026-10-22", "unregistered_target:api.hubspot.com", 1),
        ("2026-10-23", "dropped_prompt", 1),
        ("2026-10-18", "stored", 9),  # before
    ])
    m = digest.check_metrics(db, WEEK43)
    assert m.available
    assert (m.stored, m.unregistered, m.networks) == (3, 6, 2)
    assert m.top_unregistered == (("api.notion.com", 3), ("api.hubspot.com", 1))
    assert m.dropped == {"dropped_prompt": 1}
    assert m.counted == 10
    assert m.ua_classes == {"pytest-plugin": 2, "sdk": 1}


def test_missing_db_reads_as_unavailable(tmp_path):
    m = digest.check_metrics(tmp_path / "none.sqlite", WEEK43)
    assert not m.available
    assert m.counted == 0
    assert not (tmp_path / "none.sqlite").exists()  # read-only: never created


# ── publications ───────────────────────────────────────────────────────────────────────────────


def test_repository_policy_is_approved_and_loads():
    # approved by Edouard on 2026-10-20 (D-086); the publish button still does not exist
    policy = digest.load_policy(REPO / "ops" / "publish-policy.yaml")
    assert policy.approved is True
    assert "stripe" in policy.vendors


def write_policy(path: Path, **changes) -> Path:
    doc = yaml.safe_load((REPO / "ops" / "publish-policy.yaml").read_text(encoding="utf-8"))
    doc.update(changes)
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    return path


def test_policy_approval_must_be_literally_true(tmp_path):
    assert not digest.load_policy(write_policy(tmp_path / "p.yaml", approved="yes")).approved
    assert digest.load_policy(write_policy(tmp_path / "p.yaml", approved=True)).approved


def test_policy_with_unknown_key_is_refused(tmp_path):
    with pytest.raises(digest.PolicyError):
        digest.load_policy(write_policy(tmp_path / "p.yaml", publish_everything=True))


def test_candidates_are_stable_verified_facts_of_listed_vendors(registry, tmp_path):
    registry.fact("solid", evidence__confirmations=5)
    registry.fact("young", evidence__confirmations=1)
    registry.fact("auth", kind="auth_quirk", evidence__confirmations=5)
    registry.fact("stale", base=STALE)
    registry.fact("reported", base=REPORTED)
    registry.fact("done", evidence__confirmations=5)
    policy = digest.load_policy(REPO / "ops" / "publish-policy.yaml")
    published = {"af:stripe:done"}
    assert digest.publication_candidates(policy, facts_of(registry), published) == (
        "af:stripe:solid",
    )


def test_published_ledger_ids(tmp_path):
    ledger = tmp_path / "publications.jsonl"
    ledger.write_text('{"fact": "af:stripe:a"}\nnot json\n{"fact": "af:stripe:b"}\n',
                      encoding="utf-8")
    assert digest.published_ids(ledger) == {"af:stripe:a", "af:stripe:b"}
    assert digest.published_ids(tmp_path / "none.jsonl") == set()


# ── rendering ──────────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def week(registry, tmp_path):
    registry.fact("verified-a", provenance__created="2026-10-20", evidence__confirmations=5)
    registry.fact("reported-b", base=REPORTED, provenance__created="2026-10-21")
    results = write_results(registry.root / "var" / "results.jsonl", [
        run_record("2026-10-20T10:00:00Z"),
        run_record("2026-10-22T00:00:00Z", "skipped:no_key", detail="no key stripe-test"),
    ])
    make_db(registry.root / "var" / "observations.sqlite",
            [{"received_at": "2026-10-20T08:00:00Z", "reporter_net": "n1"}],
            [("2026-10-20", "stored", 1), ("2026-10-20", "unregistered_target", 2),
             ("2026-10-20", "unregistered_target:api.notion.com", 2)])
    return digest.build(registry.root, MONDAY, results=results,
                        db=registry.root / "var" / "observations.sqlite",
                        policy_path=REPO / "ops" / "publish-policy.yaml")


def test_report_is_markdown_with_every_section(week):
    text = digest.render_report(week)
    assert text.startswith("# agent-facts — неделя 43 (19.10–25.10.2026)\n")
    for section in ("## Факты", "## check()", "## Пробы", "## Нужна проба", "## Публикации"):
        assert section in text
    assert "af:stripe:reported-b" in text
    assert "api.notion.com 2" in text
    assert "stripe-test" in text
    assert "политика утверждена, кандидатов 1 (кнопка ещё не подключена)" in text


def test_report_is_deterministic(registry, week):
    again = digest.build(registry.root, MONDAY, results=registry.root / "var" / "results.jsonl",
                         db=registry.root / "var" / "observations.sqlite",
                         policy_path=REPO / "ops" / "publish-policy.yaml")
    assert digest.render_report(again) == digest.render_report(week)


def test_ping_names_run_all_pairs_apart_from_violations(week):
    p = replace(week.probes, budget_violations=0, budget_bypassed=20)
    line = digest._probes_line(replace(week, probes=p))
    assert "нарушений бюджета 0 (+20 вне бюджета по --all)" in line


def test_ping_is_5_to_8_lines_with_the_report_link(week):
    text = digest.render_ping(week, "https://ops.baillot.dev/reports")
    lines = text.splitlines()
    assert 5 <= len(lines) <= 8
    assert lines[0] == "agent-facts · неделя 43"
    assert lines[-1] == "https://ops.baillot.dev/reports/agent-facts-2026-10-26"
    assert "факты: 2 (+2) · verified 1 · official 0 · reported 1 · stale 0 · retracted 0" in lines
    assert "check(): 3 обращений · сетей 1 · незарегистрированных целей 2 (top: api.notion.com)" \
        in lines
    assert "пробы: 1 прогонов (1 pass) · нарушений бюджета 0 · ключей нет: stripe-test" in lines
    assert "нужна проба: 1 reported без пробы" in lines
    assert "публикации: политика утверждена, кандидатов 1 (кнопка ещё не подключена)" in lines
    assert "✅" not in text  # the publish button is not wired yet (Telegram gateway card)


def test_current_window_is_labelled_incomplete(registry):
    d = digest.build(registry.root, TUESDAY, current=True)
    assert digest.render_ping(d, "u").splitlines()[0] == "agent-facts · неделя 43 (неполная)"
    assert "неполная" in digest.render_report(d).splitlines()[0]


# ── card ───────────────────────────────────────────────────────────────────────────────────────


def test_needs_probe_card_follows_the_state_contract(week):
    card_id, text = digest.needs_probe_card(week)
    assert card_id == "2026-10-26-agent-facts-needs-a-probe"
    head, body = text.split("\n---\n", 1)
    fm = yaml.safe_load(head.removeprefix("---\n"))
    assert fm["id"] == card_id
    assert (fm["project"], fm["status"], fm["owner"], fm["machine"]) == (
        "agent-facts", "backlog", "agent", "vps")
    for section in ("## Что", "## Почему", "## Что сделать", "## Готово когда", "## Детали"):
        assert f"\n{section}\n" in body
    assert "- af:stripe:reported-b" in body
    for line in body.splitlines():
        assert not line.startswith(("status:", "owner:", "machine:", "priority:", "pr:"))


def test_no_card_without_reported_facts(registry):
    registry.fact("verified-a")
    assert digest.needs_probe_card(digest.build(registry.root, MONDAY)) is None


def test_open_card_is_found(state):
    (state.root / "tasks" / "2026-10-19-agent-facts-needs-a-probe.md").write_text(
        "---\nid: 2026-10-19-agent-facts-needs-a-probe\nstatus: backlog\n---\n", encoding="utf-8")
    (state.root / "tasks" / "2026-10-12-agent-facts-needs-a-probe.md").write_text(
        "---\nid: 2026-10-12-agent-facts-needs-a-probe\nstatus: done\n---\n", encoding="utf-8")
    assert digest.open_needs_probe_card(state.root) == "2026-10-19-agent-facts-needs-a-probe"


# ── main ───────────────────────────────────────────────────────────────────────────────────────


def run_main(registry, state, *extra: str) -> int:
    return digest.main([
        "--root", str(registry.root), "--state-dir", str(state.root),
        "--now", "2026-10-26T06:00:00Z", "--policy", str(REPO / "ops" / "publish-policy.yaml"),
        *extra,
    ])


def test_dry_run_prints_and_writes_nothing(registry, state, capsys):
    registry.fact("reported-b", base=REPORTED)
    before = state.journal.read_text(encoding="utf-8")
    assert run_main(registry, state, "--dry-run") == 0
    out = capsys.readouterr().out
    assert "# agent-facts — неделя 43" in out
    assert "agent-facts · неделя 43" in out
    assert list((state.root / "reviews").iterdir()) == []
    assert list((state.root / "tasks").iterdir()) == []
    assert state.journal.read_text(encoding="utf-8") == before
    assert state.calls() == []


def test_full_run_writes_report_card_journal_and_commits_once(registry, state, capsys):
    registry.fact("reported-b", base=REPORTED)
    assert run_main(registry, state, "--no-send") == 0
    report = state.root / "reviews" / "agent-facts-2026-10-26.md"
    card = state.root / "tasks" / "2026-10-26-agent-facts-needs-a-probe.md"
    assert report.read_text(encoding="utf-8").startswith("# agent-facts — неделя 43")
    assert card.exists()
    journal = state.journal.read_text(encoding="utf-8")
    assert "### 2026-10-26 — дайджест, неделя 43" in journal
    assert "reports/agent-facts-2026-10-26" in journal
    (call,) = state.calls()
    assert call[:2] == ["--as", "agent-facts"]
    assert call[-4:] == ["agent-facts: дайджест, неделя 43", "reviews/agent-facts-2026-10-26.md",
                         "tasks/2026-10-26-agent-facts-needs-a-probe.md",
                         "projects/agent-facts.md"]


def test_second_run_same_day_commits_nothing_new(registry, state):
    registry.fact("verified-a")
    assert run_main(registry, state, "--no-send") == 0
    assert run_main(registry, state, "--no-send") == 0
    assert len(state.calls()) == 1
    assert state.journal.read_text(encoding="utf-8").count("дайджест, неделя 43") == 1


def test_existing_open_card_is_not_duplicated(registry, state):
    registry.fact("reported-b", base=REPORTED)
    (state.root / "tasks" / "2026-10-19-agent-facts-needs-a-probe.md").write_text(
        "---\nid: 2026-10-19-agent-facts-needs-a-probe\nstatus: backlog\n---\n", encoding="utf-8")
    assert run_main(registry, state, "--no-send") == 0
    assert not (state.root / "tasks" / "2026-10-26-agent-facts-needs-a-probe.md").exists()
    report = (state.root / "reviews" / "agent-facts-2026-10-26.md").read_text(encoding="utf-8")
    assert "2026-10-19-agent-facts-needs-a-probe" in report


def test_failed_commit_fails_the_run(registry, state, monkeypatch):
    registry.fact("verified-a")
    monkeypatch.setenv("FAKE_STATE_COMMIT_RC", "75")
    assert run_main(registry, state, "--no-send") == 1


# ── Telegram gateway client ────────────────────────────────────────────────────────────────────


def sse(text: str, is_error: bool = False) -> str:
    result = {"content": [{"type": "text", "text": text}]}
    if is_error:
        result["isError"] = True
    data = json.dumps({"result": result, "jsonrpc": "2.0", "id": 1})
    return f"event: message\ndata: {data}\n\n"


@pytest.mark.parametrize(("reply", "is_error", "state_"), [
    ("Telegram message sent (id=42) [digest]", False, "sent"),
    ("Not sent to Telegram (diverted, это не ошибка) — digest шлёт только pm-weekly", False,
     "diverted"),
    ("Telegram delivery failed: boom", True, "failed"),
])
def test_gateway_reply_is_classified(httpserver, reply, is_error, state_):
    httpserver.expect_request(
        "/mcp", method="POST", headers={"X-Routine": "agent-facts-digest"},
    ).respond_with_data(sse(reply, is_error), content_type="text/event-stream")
    result = digest.send_telegram("hello", httpserver.url_for("/mcp"), "agent-facts-digest")
    assert result.state == state_
    assert reply in result.detail
    (request, _), = httpserver.log
    body = json.loads(request.data)
    assert body["method"] == "tools/call"
    assert body["params"]["name"] == "send_telegram"
    assert body["params"]["arguments"] == {"text": "hello", "class": "digest", "markdown": False}


def test_gateway_json_reply_and_unreachable_gateway(httpserver):
    payload = {"jsonrpc": "2.0", "id": 1,
               "result": {"content": [{"type": "text", "text": "Telegram message sent (id=1)"}]}}
    httpserver.expect_request("/mcp").respond_with_json(payload)
    assert digest.send_telegram("x", httpserver.url_for("/mcp"), "r").state == "sent"
    down = digest.send_telegram("x", "http://127.0.0.1:9/mcp", "r", timeout=2)
    assert down.state == "failed"


def test_main_sends_once_and_reports_a_diverted_ping_without_failing(registry, state, httpserver,
                                                                     capsys):
    registry.fact("verified-a")
    httpserver.expect_request("/mcp").respond_with_data(
        sse("Not sent to Telegram (diverted, это не ошибка) — x"), content_type="text/event-stream")
    assert run_main(registry, state, "--gateway", httpserver.url_for("/mcp")) == 0
    assert len(httpserver.log) == 1
    assert "diverted" in capsys.readouterr().err


def test_rerun_with_new_numbers_replaces_its_journal_entry(registry, state):
    registry.fact("verified-a")
    assert run_main(registry, state, "--no-send") == 0
    registry.fact("verified-b")
    assert run_main(registry, state, "--no-send") == 0
    journal = state.journal.read_text(encoding="utf-8")
    assert journal.count("дайджест, неделя 43") == 1
    assert "- факты 2 (+2)" in journal
    assert "### 2026-10-20 — старая запись" in journal
    assert len(state.calls()) == 2
