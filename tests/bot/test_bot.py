"""`bot publish` (spec 05 Bot): one branch, one PR, only facts/ and pages/, auto-merge rule,
drift guard, one open PR at a time, dry run, kill switch. `gh` is a fake; git is real."""

from dataclasses import replace
from datetime import date

import pytest
import yaml
from bot_repo import Checkout, FakeGh, sh
from typer.testing import CliRunner

from agentfacts.bot.collect import Change, GitError, changed_facts, fact_rows
from agentfacts.bot.pr import branch_name, publish, render_body
from agentfacts.cli import app

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
    return Checkout(tmp_path)


def run(repo, gh=None, **kw):
    return publish(repo.work, today=TODAY, environ=kw.pop("environ", {}), gh=gh, **kw)


# ── collect ─────────────────────────────────────────────────────────────────────────────────────


def test_collects_new_changed_and_deleted_fact_files_only(repo):
    repo.write(DRAFT, draft())
    known = repo.work / KNOWN
    known.write_text(known.read_text().replace("confirmations: 1", "confirmations: 2"))
    repo.write("agentfacts/code.py", "x = 2\n")
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
    assert (quorum.change, quorum.status, quorum.evidence, quorum.eligible) == (
        "new", "reported", "quorum: 3 networks, needs a probe", True)
    assert rows["af:stripe:human"].eligible is False  # reported, but not from quorum
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
    assert body.splitlines()[2:5] == [
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


def test_publish_opens_one_pr_with_facts_and_pages_only(repo):
    repo.write(DRAFT, draft())
    repo.write("agentfacts/code.py", "x = 2\n")  # a code change in the checkout never ships
    gh = FakeGh()
    report = run(repo, gh)
    assert report.action == "opened" and report.auto
    assert report.branch == "bot/facts-2026-10-21-1"
    assert report.url == "https://github.com/Illouminus/agent-facts/pull/99"
    assert repo.remote_branches() == ["bot/facts-2026-10-21-1", "main"]
    files = repo.files_in("bot/facts-2026-10-21-1")
    assert DRAFT in files and all(f.startswith(("facts/", "pages/")) for f in files)
    assert "pages/stripe/400-keys-for-idempotent-requests-can-only.md" in files
    log = sh(repo.origin, "log", "-1", "--format=%an <%ae>%n%B", "bot/facts-2026-10-21-1")
    assert log.startswith("agent-facts-bot <bot@facts.baillot.dev>\nfacts: 1 fact file from")
    assert "Signed-off-by: agent-facts-bot@illouminus <bot@facts.baillot.dev>" in log
    assert "Co-Authored-By" not in log
    assert gh.verbs() == ["pr list", "label create", "pr create", "pr merge"]
    create = gh.calls[2]
    assert create[create.index("--label") + 1] == "facts"
    assert create[create.index("--head") + 1] == "bot/facts-2026-10-21-1"
    assert gh.calls[3] == ["pr", "merge", report.url, "--auto", "--squash"]
    # the checkout itself is untouched: same branch, the draft still there, no worktree left
    assert sh(repo.work, "rev-parse", "--abbrev-ref", "HEAD").strip() == "main"
    assert (repo.work / DRAFT).is_file()
    assert len(sh(repo.work, "worktree", "list").splitlines()) == 1


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
    repo.write("facts/stripe/second.yaml", draft("second"))
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
                                                           True)
    assert "| `af:stripe:400-keys" in report.body
    assert gh.calls == [] and repo.remote_branches() == ["main"]


@pytest.mark.parametrize("kill", ["file", "env"])
def test_kill_switch_stops_the_bot(repo, kill):
    repo.write(DRAFT, draft())
    environ = {"AGENTFACTS_KILL": "1"} if kill == "env" else {}
    if kill == "file":
        repo.write("ops/KILL", "")
    gh = FakeGh()
    report = run(repo, gh, environ=environ)
    assert report.action == "killed" and gh.calls == []
    assert repo.remote_branches() == ["main"]


def test_cli_dry_run(repo):
    repo.write(DRAFT, draft())
    args = ["bot", "publish", "--root", str(repo.work), "--dry-run"]
    r = CliRunner().invoke(app, args, env={"AGENTFACTS_KILL": "0"})
    assert r.exit_code == 0, r.output
    row = "new      af:stripe:400-keys-for-idempotent-requests-can-only  reported  [auto]"
    assert row in r.output
    assert "would open bot/facts-" in r.output and "Auto-merge: on." in r.output
    assert "dry run: would open bot/facts-" in r.output


def test_cli_kill_switch(repo):
    repo.write(DRAFT, draft())
    r = CliRunner().invoke(app, ["bot", "publish", "--root", str(repo.work)],
                           env={"AGENTFACTS_KILL": "1"})
    assert r.exit_code == 0 and "killed (AGENTFACTS_KILL=1)" in r.output


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
    r = CliRunner().invoke(app, args, env={"AGENTFACTS_KILL": "0"})
    assert r.exit_code == 0, r.output
    assert "holding counter-only changes: no evidence refresh yet" in r.output
    assert repo.remote_branches() == ["main"]
