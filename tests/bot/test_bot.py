"""`bot publish` (spec 05 Bot): one branch, one PR, only facts/ and pages/, auto-merge rule,
drift guard, one open PR at a time, dry run, kill switch. `gh` is a fake; git is real."""

import json
from dataclasses import replace
from datetime import date

import pytest
import yaml
from bot_repo import Checkout, FakeGh, sh
from typer.testing import CliRunner

from apifacts.bot.collect import Change, GitError, changed_facts, fact_rows
from apifacts.bot.pr import BOT_STATE, branch_name, publish, quorum_gate, render_body
from apifacts.cli import app

TODAY = date(2026, 10, 21)
DRAFT = "facts/stripe/400-keys-for-idempotent-requests-can-only.yaml"
KNOWN = "facts/stripe/idempotency-key-reuse-different-params.yaml"


def draft(slug="400-keys-for-idempotent-requests-can-only", **over) -> str:
    doc = {
        "id": f"af:stripe:{slug}", "service": "stripe", "kind": "error_meaning",
        "target": {"surface": "http", "method": "POST", "path_template": "/v1/payment_intents"},
        "signal": {"status": 400, "normalized": "keys for idempotent requests"},
        "claim": 'POST /v1/payment_intents returns HTTP 400 with "keys for idempotent requests".',
        "dimensions": {"env": "sandbox"},
        "fixes": [{"action": "none_known", "reason_kind": "investigating"}],
        "status": "reported",
        "evidence": {"first_seen": "2026-10-20T10:00:00Z", "observations": 3},
        "provenance": {"source": "observation_quorum", "author": "bot", "created": "2026-10-21",
                       "history": [{"date": "2026-10-21", "change": "created", "by": "bot"}]},
    }
    for key, value in over.items():
        doc[key] = {**doc[key], **value} if isinstance(value, dict) else value
    return yaml.safe_dump(doc, sort_keys=False)


@pytest.fixture
def repo(tmp_path) -> Checkout:
    """The weekly quorum gate (D-093) stands open: drafts were gathered the week before."""
    checkout = Checkout(tmp_path)
    pending(checkout, "2026-10-12")
    return checkout


def pending(repo, week: str | None) -> None:
    state = repo.work / "var" / BOT_STATE
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({"quorum_pending": week}))


def bot_state(repo) -> dict:
    return json.loads((repo.work / "var" / BOT_STATE).read_text())


def run(repo, gh=None, **kw):
    return publish(repo.work, today=kw.pop("today", TODAY), environ=kw.pop("environ", {}), gh=gh,
                   **kw)


# ── collect ─────────────────────────────────────────────────────────────────────────────────────


def test_collects_new_changed_and_deleted_fact_files_only(repo):
    repo.write(DRAFT, draft())
    known = repo.work / KNOWN
    known.write_text(known.read_text().replace("confirmations: 1", "confirmations: 2"))
    repo.write("apifacts/code.py", "x = 2\n")
    repo.write("facts/stripe/notes.txt", "not yaml\n")
    assert changed_facts(repo.work) == [Change(DRAFT), Change(KNOWN)]
    known.unlink()
    assert changed_facts(repo.work) == [Change(DRAFT), Change(KNOWN, deleted=True)]


def test_rows_and_eligibility(repo):
    repo.write(DRAFT, draft())
    repo.write("facts/stripe/human.yaml",
               draft("human", provenance={"source": "manual", "author": "human:edouard"}))
    repo.write("facts/stripe/broken.yaml", "id: nope\n")
    rows = {r.id: r for r in fact_rows(repo.work, changed_facts(repo.work))}
    quorum = rows["af:stripe:400-keys-for-idempotent-requests-can-only"]
    # variant 1 of the sec card 2026-10-23 (D-089): `reported` never merges without a human
    assert (quorum.change, quorum.status, quorum.evidence, quorum.eligible) == (
        "new", "reported", "quorum: 3 networks, needs a probe", False)
    assert rows["af:stripe:human"].eligible is False
    assert rows["broken"].status == "invalid" and not rows["broken"].eligible


def test_branch_name_counts_the_days_branches():
    assert branch_name(TODAY, []) == "bot/facts-2026-10-21-1"
    existing = ["refs/heads/bot/facts-2026-10-21-1", "bot/facts-2026-10-21-3",
                "bot/facts-2026-10-20-7", "bot/facts-2026-10-21-x"]
    assert branch_name(TODAY, existing) == "bot/facts-2026-10-21-4"


def test_body_table(repo):
    repo.write(DRAFT, draft())
    rows = fact_rows(repo.work, changed_facts(repo.work))
    body = render_body(rows, True, "illouminus", skipped=["facts/stripe/x.yaml"])
    assert body.splitlines()[2] == ("Quorum drafts gathered over the salt period: 1. They go out "
                                    "as one PR a week, one review for all of them (D-093).")
    assert body.splitlines()[4:7] == [
        "| id | kind | status | evidence | change |",
        "|----|------|--------|----------|--------|",
        "| `af:stripe:400-keys-for-idempotent-requests-can-only` | error_meaning | reported | "
        "quorum: 3 networks, needs a probe | new |",
    ]
    assert "Auto-merge: on." in body and "`facts/stripe/x.yaml`" in body
    held = render_body([replace(rows[0], eligible=False)], False, "illouminus")
    assert "Needs a human review `[tap]` for: `af:stripe:400-keys" in held


# ── publish ─────────────────────────────────────────────────────────────────────────────────────


def test_nothing_to_publish(repo):
    gh = FakeGh()
    assert run(repo, gh).action == "nothing"
    assert gh.calls == []


def verified(repo, slug="verified-new") -> str:
    """A new verified fact written by the bot (a copy of the seeded one under another id)."""
    rel = f"facts/stripe/{slug}.yaml"
    repo.write(rel, repo.show("main", KNOWN).replace(
        "af:stripe:idempotency-key-reuse-different-params", f"af:stripe:{slug}"))
    return rel


def test_publish_opens_one_pr_with_facts_and_pages_only(repo):
    rel = verified(repo)
    repo.write("apifacts/code.py", "x = 2\n")  # a code change in the checkout never ships
    gh = FakeGh()
    report = run(repo, gh)
    assert report.action == "opened" and report.auto
    assert report.branch == "bot/facts-2026-10-21-1"
    assert report.url == "https://github.com/Illouminus/apifacts/pull/99"
    assert repo.remote_branches() == ["bot/facts-2026-10-21-1", "main"]
    files = repo.files_in("bot/facts-2026-10-21-1")
    assert rel in files and all(f.startswith(("facts/", "pages/")) for f in files)
    assert "pages/stripe/verified-new.md" in files
    log = sh(repo.origin, "log", "-1", "--format=%an <%ae>%n%B", "bot/facts-2026-10-21-1")
    assert log.startswith("agent-facts-bot <bot@apifacts.dev>\nfacts: 1 fact file from")
    assert "Signed-off-by: agent-facts-bot@illouminus <bot@apifacts.dev>" in log
    assert "Co-Authored-By" not in log
    assert gh.verbs() == ["pr list", "label create", "pr create", "pr merge"]
    create = gh.calls[2]
    assert [create[i + 1] for i, a in enumerate(create) if a == "--label"] == ["facts"]
    assert create[create.index("--head") + 1] == "bot/facts-2026-10-21-1"
    assert gh.calls[3] == ["pr", "merge", report.url, "--auto", "--squash"]
    # the checkout itself is untouched: same branch, the fact still there, no worktree left
    assert sh(repo.work, "rev-parse", "--abbrev-ref", "HEAD").strip() == "main"
    assert (repo.work / rel).is_file()
    assert len(sh(repo.work, "worktree", "list").splitlines()) == 1


def test_reported_quorum_fact_needs_review_and_never_auto_merges(repo):
    """Variant 1 of the sec card 2026-10-23 (D-089): an anonymous quorum must not publish a
    fact on its own; the PR waits for a human with the label needs-review."""
    repo.write(DRAFT, draft())
    verified(repo)
    gh = FakeGh()
    report = run(repo, gh)
    assert report.action == "opened" and not report.auto
    assert "pr merge" not in gh.verbs()
    create = next(c for c in gh.calls if c[:2] == ["pr", "create"])
    assert [create[i + 1] for i, a in enumerate(create) if a == "--label"] == [
        "facts", "needs-review"]
    assert ["label", "create", "needs-review"] == next(
        c for c in gh.calls if c[:3] == ["label", "create", "needs-review"])[:3]
    assert "Needs a human review `[tap]` for: `af:stripe:400-keys" in report.body


def test_human_fact_disables_auto_merge(repo):
    repo.write("facts/stripe/human.yaml",
               draft("human", provenance={"source": "manual", "author": "human:edouard"}))
    gh = FakeGh()
    report = run(repo, gh)
    assert report.action == "opened" and not report.auto
    assert "pr merge" not in gh.verbs()


def test_second_branch_of_the_day_gets_the_next_number(repo):
    repo.write(DRAFT, draft())
    run(repo, FakeGh())
    verified(repo, "second")
    assert run(repo, FakeGh()).branch == "bot/facts-2026-10-21-2"


def test_open_bot_pr_means_wait(repo):
    repo.write(DRAFT, draft())
    gh = FakeGh(open_prs=[{"number": 98, "headRefName": "bot/facts-2026-10-21-1",
                           "url": "https://github.com/x/y/pull/98"}])
    report = run(repo, gh)
    assert (report.action, report.detail) == ("waiting", "open bot PR https://github.com/x/y/pull/98")
    assert gh.verbs() == ["pr list"]
    assert repo.remote_branches() == ["main"]


def test_file_changed_on_main_is_not_overwritten(repo, tmp_path):
    known = repo.work / KNOWN
    known.write_text(known.read_text().replace("confirmations: 1", "confirmations: 2"))
    repo.write(DRAFT, draft())
    human = repo.show("main", KNOWN).replace("vantages: [illouminus]", "vantages: [freebox]")
    repo.push_to_main_from_elsewhere(KNOWN, human, tmp_path)
    report = run(repo, FakeGh())
    assert report.action == "opened" and report.skipped == [KNOWN]
    assert KNOWN not in repo.files_in(report.branch)
    assert "Not included (changed on `main`" in report.body


def test_invalid_fact_refuses_the_publish(repo):
    repo.write("facts/stripe/broken.yaml", "id: af:stripe:broken\nservice: stripe\n")
    gh = FakeGh()
    report = run(repo, gh)
    assert report.action == "refused" and "broken.yaml" in report.detail
    assert repo.remote_branches() == ["main"]
    assert "pr create" not in gh.verbs()


def test_dry_run_pushes_and_calls_nothing(repo):
    repo.write(DRAFT, draft())
    gh = FakeGh()
    report = run(repo, gh, dry_run=True)
    assert (report.action, report.branch, report.auto) == ("would-open", "bot/facts-2026-10-21-1",
                                                           False)
    assert "| `af:stripe:400-keys" in report.body
    assert gh.calls == [] and repo.remote_branches() == ["main"]


@pytest.mark.parametrize("kill", ["file", "env"])
def test_kill_switch_stops_the_bot(repo, kill):
    repo.write(DRAFT, draft())
    environ = {"APIFACTS_KILL": "1"} if kill == "env" else {}
    if kill == "file":
        repo.write("ops/KILL", "")
    gh = FakeGh()
    report = run(repo, gh, environ=environ)
    assert report.action == "killed" and gh.calls == []
    assert repo.remote_branches() == ["main"]


def test_cli_dry_run(repo):
    repo.write(DRAFT, draft())
    args = ["bot", "publish", "--root", str(repo.work), "--dry-run"]
    r = CliRunner().invoke(app, args, env={"APIFACTS_KILL": "0"})
    assert r.exit_code == 0, r.output
    row = "new      af:stripe:400-keys-for-idempotent-requests-can-only  reported  [review]"
    assert row in r.output
    assert "would open bot/facts-" in r.output and "Auto-merge: off." in r.output
    assert "dry run: would open bot/facts-" in r.output


def test_cli_kill_switch(repo):
    repo.write(DRAFT, draft())
    r = CliRunner().invoke(app, ["bot", "publish", "--root", str(repo.work)],
                           env={"APIFACTS_KILL": "1"})
    assert r.exit_code == 0 and "killed (APIFACTS_KILL=1)" in r.output


def test_changes_already_merged_on_main_are_not_republished(repo, tmp_path):
    """The bot's PR merged; the runner's checkout is not synced yet: nothing to do, no refusal."""
    repo.write(DRAFT, draft())
    report = run(repo, FakeGh())
    sh(repo.origin, "update-ref", "refs/heads/main", f"refs/heads/{report.branch}")  # "merged"
    gh = FakeGh()
    again = run(repo, gh)
    assert (again.action, again.detail) == ("nothing", "every change is already on main")
    assert gh.calls == []


def test_failed_pr_create_drops_the_pushed_branch(repo):
    class Failing(FakeGh):
        def __call__(self, args):
            if list(args[:2]) == ["pr", "create"]:
                raise GitError("gh pr create: HTTP 502")
            return super().__call__(args)

    repo.write(DRAFT, draft())
    with pytest.raises(GitError):
        run(repo, Failing())
    assert repo.remote_branches() == ["main"]


def test_cli_holds_counter_only_changes_until_the_daily_refresh(repo, tmp_path):
    known = repo.work / KNOWN
    known.write_text(known.read_text().replace("confirmations: 1", "confirmations: 2"))
    args = ["bot", "publish", "--root", str(repo.work), "--state-dir", str(tmp_path / "state")]
    r = CliRunner().invoke(app, args, env={"APIFACTS_KILL": "0"})
    assert r.exit_code == 0, r.output
    assert "holding counter-only changes: no evidence refresh yet" in r.output
    assert repo.remote_branches() == ["main"]


# ── quorum drafts: one PR a salt week (D-093) ───────────────────────────────────────────────────


def test_quorum_gate_opens_only_in_a_later_salt_period(tmp_path):
    assert quorum_gate(tmp_path, TODAY).startswith("quorum drafts wait")  # nothing noted yet
    (tmp_path / BOT_STATE).write_text(json.dumps({"quorum_pending": "2026-10-19"}))
    assert "since the salt period of 2026-10-19" in quorum_gate(tmp_path, TODAY)
    assert quorum_gate(tmp_path, date(2026, 10, 26)) is None  # the next Monday


def test_quorum_drafts_gather_for_the_week_then_go_out_in_one_pr(repo):
    pending(repo, None)
    repo.write(DRAFT, draft())
    gh = FakeGh()
    report = run(repo, gh)
    assert (report.action, gh.calls) == ("holding", [])
    assert report.detail.startswith("quorum drafts wait for the weekly PR")
    assert bot_state(repo)["quorum_pending"] == "2026-10-19"
    repo.write("facts/stripe/second.yaml", draft("second"))  # Saturday, same salt week
    assert run(repo, FakeGh(), today=date(2026, 10, 24)).action == "holding"
    assert bot_state(repo)["quorum_pending"] == "2026-10-19"  # the first sighting stays

    gh = FakeGh()
    report = run(repo, gh, today=date(2026, 10, 26))  # Monday: one PR with both drafts
    assert report.action == "opened" and not report.auto
    assert {r.path for r in report.rows} == {DRAFT, "facts/stripe/second.yaml"}
    assert bot_state(repo)["quorum_pending"] is None
    assert "Quorum drafts gathered over the salt period: 2." in report.body


def test_held_drafts_do_not_hold_other_new_facts(repo):
    pending(repo, None)
    repo.write(DRAFT, draft())
    rel = verified(repo)
    report = run(repo, FakeGh())
    assert report.action == "opened" and report.auto
    assert [r.path for r in report.rows] == [rel]
    assert DRAFT not in repo.files_in(report.branch)
    assert (repo.work / DRAFT).is_file()  # still in the checkout for the weekly PR
    assert bot_state(repo)["quorum_pending"] == "2026-10-19"


def test_dry_run_notes_no_pending_week(repo):
    pending(repo, None)
    repo.write(DRAFT, draft())
    assert run(repo, FakeGh(), dry_run=True).action == "holding"
    assert bot_state(repo)["quorum_pending"] is None


def test_cli_names_the_quorum_hold(repo):
    pending(repo, None)
    repo.write(DRAFT, draft())
    args = ["bot", "publish", "--root", str(repo.work), "--dry-run"]
    r = CliRunner().invoke(app, args, env={"APIFACTS_KILL": "0"})
    assert r.exit_code == 0, r.output
    assert "holding: quorum drafts wait for the weekly PR" in r.output
