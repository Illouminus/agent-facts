"""`apifacts bot publish`: the changed fact files → one branch `bot/facts-<date>-<n>`, one PR
labelled `facts`, auto-merge when every fact may go in without a human (spec 05 Bot).

The commit is built in a temporary worktree of `origin/main`, never in the checkout: the runner's
working tree, its branch and every code path stay untouched; only `facts/` and the `pages/`
regenerated from them can enter the commit (checked before the push). One open bot PR at a time:
while it waits, changes stay in the checkout and go out with the next run after the merge.

GitHub access is the bot's own token only (`bot/token.py`, D-089): gh with GH_TOKEN, remote git
through an env-only credential helper; a missing token is a refusal, never the personal login.

When to open (incident 2026-10-20..24, 62 PRs in three days): a new, deleted or substantively
changed fact goes out at once (with any counter-only changes riding along); counter-only changes
go out as one "daily evidence refresh" PR, on the first run after `probe run --refresh-evidence`
left its marker, at most one a day (`<state-dir>/bot-state.json` remembers it). New `reported`
drafts from the quorum need a human tap each, so they gather into one PR a salt period (D-093): the
first run that sees them notes the period, the first run of a later period takes them all.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from apifacts.api.store import salt_period
from apifacts.bot.collect import (
    BASE,
    Change,
    FactRow,
    GitError,
    already_on,
    auto_mergeable,
    changed_facts,
    drifted,
    fact_rows,
    git,
)
from apifacts.bot.token import BotAuth
from apifacts.probe.runner import (
    DEFAULT_VANTAGE,
    REFRESH_MARKER,
    check_vantage,
    kill_reason,
    write_json_atomic,
)

BOT_NAME = "agent-facts-bot"
DEFAULT_BOT_EMAIL = "bot@apifacts.dev"
LABEL = "facts"
REVIEW_LABEL = "needs-review"  # a PR without auto-merge: some fact needs a human tap (D-089)
BRANCH_PREFIX = "bot/facts-"
PUBLISHED_DIRS = ("facts/", "pages/")
BOT_STATE = "bot-state.json"
DAILY_TITLE = "facts: daily evidence refresh ({day})"
QUORUM_HOLD = "quorum drafts wait for the weekly PR"

Gh = Callable[[Sequence[str]], str]


GH_FALLBACKS = ("~/.local/bin/gh", "/usr/local/bin/gh", "/snap/bin/gh", "/opt/homebrew/bin/gh")


def find_gh(
    environ: Mapping[str, str] | None = None, fallbacks: Sequence[str] = GH_FALLBACKS
) -> str:
    """Path to the `gh` binary: `APIFACTS_GH`, then PATH, then the usual per-user and system
    locations. systemd user units run with a minimal PATH that lacks ~/.local/bin, where gh lives
    on illouminus (quorum service failed with FileNotFoundError on 2026-10-20)."""
    env = os.environ if environ is None else environ
    if explicit := env.get("APIFACTS_GH"):
        return explicit
    if found := shutil.which("gh", path=env.get("PATH")):
        return found
    home = env.get("HOME") or str(Path.home())
    for candidate in fallbacks:
        path = Path(candidate.replace("~", home, 1))
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    raise GitError("gh not found: set APIFACTS_GH or add gh to PATH")


def gh_cli(root: Path, auth: BotAuth) -> Gh:
    """The real `gh`, run in the checkout (its `origin` names the repository), with the bot's
    token in GH_TOKEN (never the host's keyring login) and redacted errors."""
    exe = find_gh()
    env = auth.gh_env(os.environ)

    def run(args: Sequence[str]) -> str:
        done = subprocess.run([exe, *args], cwd=root, capture_output=True, text=True, env=env,
                              check=False)
        if done.returncode != 0:
            raise GitError(auth.redact(f"gh {' '.join(args[:2])}: {done.stderr.strip()}"))
        return done.stdout

    return run


def branch_name(day: date, existing: Iterable[str]) -> str:
    """`bot/facts-<day>-<n>`, n one above the highest already used that day."""
    pattern = re.compile(rf"^(?:refs/heads/)?{re.escape(BRANCH_PREFIX)}{day.isoformat()}-(\d+)$")
    used = [int(m[1]) for name in existing if (m := pattern.match(name.strip()))]
    return f"{BRANCH_PREFIX}{day.isoformat()}-{max(used, default=0) + 1}"


def _remote_branches(root: Path, day: date, auth: BotAuth) -> list[str]:
    out = auth.git(root, "ls-remote", "--heads", "origin", f"refs/heads/{BRANCH_PREFIX}{day}-*")
    return [line.split("\t", 1)[1] for line in out.splitlines() if "\t" in line]


def render_body(
    rows: Sequence[FactRow],
    auto: bool,
    vantage: str,
    skipped: Sequence[str] = (),
    daily: bool = False,
) -> str:
    """The PR description: one table row per fact, then what decides the merge."""
    lines = [f"Fact files changed by the quorum and the probe runner on `{vantage}`.", ""]
    if drafts := sum(r.quorum_draft for r in rows):
        lines += [f"Quorum drafts gathered over the salt period: {drafts}. They go out as one PR "
                  "a week, one review for all of them (D-093).", ""]
    if daily:
        lines += ["Daily evidence refresh: only the counters moved (confirmations, last_confirmed, "
                  "stale_counter, vantages, observations). New facts and status changes open "
                  "their own PR at once.", ""]
    lines += [
        "| id | kind | status | evidence | change |",
        "|----|------|--------|----------|--------|",
    ]
    lines += [f"| `{r.id}` | {r.kind} | {r.status} | {r.evidence} | {r.change} |" for r in rows]
    lines.append("")
    if auto:
        lines.append("Auto-merge: on. Every fact is `verified:*` and written by the bot; it "
                     "merges when CI is green.")
    else:
        held = ", ".join(f"`{r.id}`" for r in rows if not r.eligible)
        lines.append(f"Auto-merge: off. Needs a human review `[tap]` for: {held}. Only "
                     "`verified:*` facts written by the bot merge on their own (D-089).")
    if skipped:
        lines += ["", "Not included (changed on `main` since this checkout was synced): "
                  + ", ".join(f"`{p}`" for p in skipped) + "."]
    lines += ["", "Pages regenerated with `apifacts pages build`. No code path is touched."]
    return "\n".join(lines) + "\n"


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def evidence_gate(state_dir: Path, today: date) -> tuple[str | None, str | None]:
    """(why counter-only changes must wait, or None; the refresh marker's stamp)."""
    refreshed = _read_json(state_dir / REFRESH_MARKER).get("refreshed")
    if not isinstance(refreshed, str):
        return "no evidence refresh yet (probe run --refresh-evidence)", None
    state = _read_json(state_dir / BOT_STATE)
    if state.get("evidence_day") == today.isoformat():
        return "today's evidence PR was already opened", refreshed
    if refreshed <= str(state.get("evidence_refresh") or ""):
        return "waiting for the next daily evidence refresh", refreshed
    return None, refreshed


def quorum_gate(state_dir: Path, today: date) -> str | None:
    """Why quorum drafts must wait for the weekly PR, or None when it may open now (D-093)."""
    week = salt_period(today).isoformat()
    pending = _read_json(state_dir / BOT_STATE).get("quorum_pending")
    if isinstance(pending, str) and pending < week:
        return None
    since = pending if isinstance(pending, str) else week
    return f"{QUORUM_HOLD} (gathering since the salt period of {since})"


def _remember_quorum(state_dir: Path, **fields: str | None) -> None:
    write_json_atomic(state_dir / BOT_STATE, {**_read_json(state_dir / BOT_STATE), **fields})


def _forget_quorum(state_dir: Path, held: bool, dry_run: bool) -> None:
    """Drop a pending week no draft is held for: a draft that went out another way (a probe
    confirmed it, it reached main) must not open the next week's gate at once (D-093)."""
    if not held and not dry_run and isinstance(
            _read_json(state_dir / BOT_STATE).get("quorum_pending"), str):
        _remember_quorum(state_dir, quorum_pending=None)


def _remember_evidence_pr(state_dir: Path, today: date, refreshed: str | None) -> None:
    write_json_atomic(state_dir / BOT_STATE, {**_read_json(state_dir / BOT_STATE),
                                              "evidence_refresh": refreshed,
                                              "evidence_day": today.isoformat()})


@dataclass
class PublishReport:
    action: str  # nothing, killed, holding, waiting, would-open, opened, refused
    branch: str | None = None
    url: str | None = None
    rows: list[FactRow] = field(default_factory=list)
    auto: bool = False
    skipped: list[str] = field(default_factory=list)
    body: str = ""
    detail: str = ""
    daily: bool = False  # counter-only changes: the daily evidence refresh PR


def _commit_message(
    rows: Sequence[FactRow], vantage: str, email: str, day: date, daily: bool
) -> str:
    listed = "\n".join(f"- {r.id} ({r.status}, {r.change})" for r in rows)
    files = f"{len(rows)} fact file{'s' if len(rows) != 1 else ''}"
    headline = DAILY_TITLE.format(day=day) if daily else f"facts: {files} from {vantage} ({day})"
    return f"{headline}\n\n{listed}\n\nSigned-off-by: {BOT_NAME}@{vantage} <{email}>\n"


def _bot_env(email: str) -> dict[str, str]:
    return {**os.environ, "GIT_AUTHOR_NAME": BOT_NAME, "GIT_AUTHOR_EMAIL": email,
            "GIT_COMMITTER_NAME": BOT_NAME, "GIT_COMMITTER_EMAIL": email}


def _open_bot_pr(gh: Gh) -> str | None:
    out = gh(
        ["pr", "list", "--state", "open", "--label", LABEL, "--json", "number,headRefName,url"]
    )
    for pr in json.loads(out or "[]"):
        if str(pr.get("headRefName", "")).startswith(BRANCH_PREFIX):
            return str(pr.get("url") or pr.get("number"))
    return None


def _build_tree(tree: Path, root: Path, changes: Sequence[Change]) -> list[str]:
    """Copy the changes into the worktree, regenerate pages, validate; problems as strings."""
    from apifacts.pages import PagesError
    from apifacts.pages.build import build_pages, load_registry, sync
    from apifacts.schema.validate import default_paths, validate_paths

    for change in changes:
        target = tree / change.path
        if change.deleted:
            target.unlink(missing_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / change.path, target)
    report = validate_paths(default_paths(tree), root=tree)
    if not report.ok:
        return [str(p).replace(str(tree) + "/", "") for p in report.problems]
    try:
        sync(tree / "pages", build_pages(*load_registry(tree)))
    except PagesError as exc:
        return [f"pages: {exc}"]
    return []


def publish(
    root: Path,
    *,
    today: date,
    vantage: str = DEFAULT_VANTAGE,
    dry_run: bool = False,
    environ: Mapping[str, str] | None = None,
    gh: Gh | None = None,
    state_dir: Path | None = None,
    auth: BotAuth | None = None,
) -> PublishReport:
    check_vantage(vantage)
    environ = os.environ if environ is None else environ
    state_dir = root / "var" if state_dir is None else state_dir
    if reason := kill_reason(root, environ):
        return PublishReport("killed", detail=reason)
    changes = changed_facts(root)
    by_path = {row.path: row for row in fact_rows(root, changes)}  # against HEAD: fetch-proof
    _forget_quorum(state_dir, any(row.quorum_draft for row in by_path.values()), dry_run)
    if not changes:
        return PublishReport("nothing")
    hold, refreshed = evidence_gate(state_dir, today)
    if hold and not any(row.substantive for row in by_path.values()):
        return PublishReport("holding", detail=hold)  # no fetch, no gh: nothing goes out
    if auth is None:  # MissingToken (a GitError) before any remote call; a dry run goes anonymous
        auth = BotAuth.anonymous() if dry_run else BotAuth.load()
    if not dry_run:
        auth.git(root, "fetch", "--quiet", "origin", "main")
    changes = [c for c in changes if not already_on(root, c)]
    if not changes:
        return PublishReport("nothing", detail="every change is already on main")
    # after the fetch: drafts the weekly PR already merged are not gathered again
    drafts = {c.path for c in changes if by_path[c.path].quorum_draft}
    if drafts and (wait := quorum_gate(state_dir, today)):  # they stay in the checkout
        if not dry_run and not isinstance(_read_json(state_dir / BOT_STATE).get("quorum_pending"),
                                          str):
            _remember_quorum(state_dir, quorum_pending=salt_period(today).isoformat())
        changes = [c for c in changes if c.path not in drafts]
        if not changes:
            return PublishReport("holding", detail=wait)
    skipped = drifted(root, changes)
    changes = [c for c in changes if c.path not in skipped]
    if not changes:
        return PublishReport("refused", skipped=skipped, detail="every change conflicts with main")
    rows = [by_path[c.path] for c in changes]
    daily = not any(row.substantive for row in rows)
    if daily and hold:  # the substantive changes were on main, conflicted or wait for the week
        return PublishReport("holding", skipped=skipped, detail=hold)
    auto = auto_mergeable(rows)
    body = render_body(rows, auto, vantage, skipped, daily=daily)
    report = PublishReport("would-open", rows=rows, auto=auto, skipped=skipped, body=body,
                           daily=daily)
    report.branch = branch_name(today, _remote_branches(root, today, auth))
    if dry_run:
        return report
    gh = gh or gh_cli(root, auth)
    if (waiting := _open_bot_pr(gh)) is not None:
        report.action, report.detail = "waiting", f"open bot PR {waiting}"
        return report

    email = environ.get("APIFACTS_BOT_EMAIL") or DEFAULT_BOT_EMAIL
    scratch = Path(tempfile.mkdtemp(prefix="apifacts-bot-"))
    tree = scratch / "tree"
    git(root, "worktree", "add", "--quiet", "--detach", str(tree), BASE)
    try:
        if problems := _build_tree(tree, root, changes):
            report.action, report.detail = "refused", "; ".join(problems[:5])
            return report
        git(tree, "add", "--all", "--", "facts", "pages")
        staged = git(tree, "diff", "--cached", "--name-only").split()
        if not staged:
            report.action = "nothing"
            return report
        if outside := [p for p in staged if not p.startswith(PUBLISHED_DIRS)]:
            report.action, report.detail = "refused", f"outside facts/ and pages/: {outside}"
            return report
        git(tree, "commit", "--quiet", "--no-verify", "-m",
            _commit_message(rows, vantage, email, today, daily), env=_bot_env(email))
        auth.git(tree, "push", "--quiet", "origin", f"HEAD:refs/heads/{report.branch}")
    finally:
        git(root, "worktree", "remove", "--force", str(tree))
        shutil.rmtree(scratch, ignore_errors=True)

    title = (DAILY_TITLE.format(day=today) if daily else
             f"facts: {len(rows)} fact file{'s' if len(rows) != 1 else ''} ({today})")
    labels = ["--label", LABEL] + ([] if auto else ["--label", REVIEW_LABEL])
    try:
        gh(["label", "create", LABEL, "--force", "--color", "0E8A16",
            "--description", "Fact files published by agent-facts-bot"])
        if not auto:
            gh(["label", "create", REVIEW_LABEL, "--force", "--color", "D93F0B",
                "--description", "A fact in this PR needs a human review before merge"])
        report.url = gh(["pr", "create", "--base", "main", "--head", report.branch, "--title",
                         title, "--body", body, *labels]).strip()
    except GitError:  # no PR: drop the branch, or the next run would push a duplicate
        auth.git(root, "push", "--quiet", "origin", "--delete", report.branch)
        raise
    if any(row.quorum_draft for row in rows):  # the same: the drafts are on their way
        try:
            _remember_quorum(state_dir, quorum_pending=None)
        except OSError as exc:
            report.detail = f"bot state not saved: {exc}"
    if daily:  # before the merge call: a failing `gh pr merge` must not reopen it next hour
        try:
            _remember_evidence_pr(state_dir, today, refreshed)
        except OSError as exc:  # the PR is open; the open-PR check holds the next runs
            report.detail = f"bot state not saved: {exc}"
    if auto:
        gh(["pr", "merge", report.url, "--auto", "--squash"])
    report.action = "opened"
    return report
