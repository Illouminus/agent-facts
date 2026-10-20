"""ops/state_journal.py: one journal entry per deploy in megabrain projects/agent-facts.md."""

import hashlib

import state_journal
from ops_builders import REPORTED

SHA = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"


def deploy(registry, state, *extra: str) -> int:
    return state_journal.main([
        "--sha", SHA, "--subject", "W8: ops", "--root", str(registry.root),
        "--state-dir", str(state.root), "--today", "2026-10-21", *extra,
    ])


def test_insert_entry_goes_right_under_the_heading_newest_first():
    text = "---\nname: x\n---\n\n## Журнал\n\n### 2026-10-20 — старая\n\n- было\n"
    out = state_journal.insert_entry(text, "2026-10-21 — новая", ["- стало"])
    assert out == (
        "---\nname: x\n---\n\n## Журнал\n\n### 2026-10-21 — новая\n\n- стало\n\n"
        "### 2026-10-20 — старая\n\n- было\n"
    )


def test_insert_entry_into_an_empty_journal():
    out = state_journal.insert_entry("## Журнал\n", "2026-10-21 — первая", ["- раз"])
    assert out == "## Журнал\n\n### 2026-10-21 — первая\n\n- раз\n"


def test_insert_entry_without_heading_raises():
    try:
        state_journal.insert_entry("# нет журнала\n", "t", ["- x"])
    except state_journal.JournalError as exc:
        assert "## Журнал" in str(exc)
    else:
        raise AssertionError("expected JournalError")


def test_deploy_entry_counts_facts_by_status(registry, state):
    registry.fact("one")
    registry.fact("two", base=REPORTED)
    assert deploy(registry, state) == 0
    text = state.journal.read_text(encoding="utf-8")
    head = text.split("### 2026-10-20 — старая")[0]
    assert "### 2026-10-21 — деплой a1b2c3d на illouminus" in head
    assert "- main a1b2c3d «W8: ops»: фактов 2 (verified 1, official 0, reported 1, stale 0, " \
        "retracted 0), /healthz ok." in head


def test_deploy_commits_only_the_journal_as_agent_facts(registry, state):
    registry.fact("one")
    deploy(registry, state)
    data = state.journal.read_bytes()
    blob = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()
    assert state.calls() == [[
        "--as", "agent-facts", "--expect-sha", f"projects/agent-facts.md={blob}",
        "agent-facts: деплой a1b2c3d", "projects/agent-facts.md",
    ]]


def test_same_sha_twice_writes_and_commits_once(registry, state):
    registry.fact("one")
    assert deploy(registry, state) == 0
    once = state.journal.read_text(encoding="utf-8")
    assert deploy(registry, state) == 0
    assert state.journal.read_text(encoding="utf-8") == once
    assert len(state.calls()) == 1


def test_no_commit_flag_writes_only(registry, state):
    registry.fact("one")
    assert deploy(registry, state, "--no-commit") == 0
    assert "деплой a1b2c3d" in state.journal.read_text(encoding="utf-8")
    assert state.calls() == []


def test_missing_project_file_is_an_error_and_writes_nothing(registry, state):
    state.journal.unlink()
    assert deploy(registry, state) == 1
    assert not state.journal.exists()
    assert state.calls() == []


def test_failed_commit_is_reported(registry, state, monkeypatch):
    registry.fact("one")
    monkeypatch.setenv("FAKE_STATE_COMMIT_RC", "3")
    assert deploy(registry, state) == 1


def test_bad_sha_is_a_usage_error(registry, state):
    rc = state_journal.main(["--sha", "nope", "--subject", "x", "--root", str(registry.root),
                             "--state-dir", str(state.root)])
    assert rc == 2


def test_remove_entry_drops_only_the_marked_block():
    text = ("## Журнал\n\n### b — новая\n\n- отчёт (x/r-2)\n\n### a — старая\n\n- было\n")
    assert state_journal.remove_entry(text, "x/r-2)") == "## Журнал\n\n### a — старая\n\n- было\n"
    assert state_journal.remove_entry(text, "nothing") == text
