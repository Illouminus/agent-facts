#!/usr/bin/env python3
"""Megabrain state journal for agent-facts (spec 08 "Megabrain state").

After a successful deploy `ops/deploy.sh` calls

    python ops/state_journal.py --sha <40 hex> --subject <commit subject> --root <checkout>

which puts one entry at the top of `## Журнал` in `<state>/projects/agent-facts.md`:

    ### 2026-10-21 — деплой a1b2c3d на illouminus

    - main a1b2c3d «<subject>»: фактов 53 (verified 39, official 14, reported 0, stale 0,
      retracted 0), /healthz ok.   [one line in the file]

and commits only that file with `bin/state-commit --as agent-facts --expect-sha <path>=<blob>`
(the state repo has many writers; `git add -A` there is forbidden). The same sha twice writes and
commits nothing. `ops/digest.py` reuses `insert_entry` and `commit` for its weekly entry.

Exit codes: 0 written (or already there), 1 state file missing / malformed / commit refused,
2 usage.
"""

import argparse
import hashlib
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from agentfacts.pages.build import load_registry
from agentfacts.schema.models import VERIFIED_STATUSES, Fact

ACTOR = "agent-facts"
PROJECT_FILE = "projects/agent-facts.md"
JOURNAL_HEADING = "## Журнал"
DEFAULT_STATE = Path.home() / "claude-hub" / "state"
PARIS = ZoneInfo("Europe/Paris")


class JournalError(Exception):
    pass


def insert_entry(text: str, title: str, bullets: Sequence[str]) -> str:
    """`### <title>` + bullets right under `## Журнал` (newest first, one blank line around)."""
    lines = text.splitlines()
    try:
        at = next(i for i, line in enumerate(lines) if line.strip() == JOURNAL_HEADING)
    except StopIteration:
        raise JournalError(f"no '{JOURNAL_HEADING}' heading") from None
    rest = lines[at + 1 :]
    while rest and not rest[0].strip():
        rest.pop(0)
    block = ["", f"### {title}", "", *bullets]
    if rest:
        block.append("")
    return "\n".join([*lines[: at + 1], *block, *rest]) + "\n"


def git_blob_sha(data: bytes) -> str:
    """What `git hash-object` prints for `data` (state-commit --expect-sha compares it)."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def commit(state_dir: Path, message: str, paths: Iterable[str]) -> int:
    """`bin/state-commit --as agent-facts --expect-sha <p>=<blob>… <message> <paths>`."""
    paths = list(paths)
    argv = [str(state_dir / "bin" / "state-commit"), "--as", ACTOR]
    for rel in paths:
        argv += ["--expect-sha", f"{rel}={git_blob_sha((state_dir / rel).read_bytes())}"]
    argv += [message, *paths]
    try:
        return subprocess.run(argv, cwd=state_dir, check=False).returncode
    except OSError as exc:
        print(f"state-commit not runnable: {exc}", file=sys.stderr)
        return 127


def status_counts(facts: Iterable[Fact]) -> dict[str, int]:
    """verified (any verified:*), official, reported, stale, retracted — in that order."""
    by_status = Counter(fact.status.value for fact in facts)
    verified = sum(n for status, n in by_status.items() if status in VERIFIED_STATUSES)
    counts = {"verified": verified}
    for status in ("official", "reported", "stale", "retracted"):
        counts[status] = by_status.get(status, 0)
    return counts


def deploy_entry(
    sha: str, subject: str, facts: Sequence[Fact], today: date
) -> tuple[str, list[str]]:
    counts = status_counts(facts)
    split = ", ".join(f"{name} {n}" for name, n in counts.items())
    short = sha[:7]
    title = f"{today.isoformat()} — деплой {short} на illouminus"
    bullet = f"- main {short} «{subject}»: фактов {len(facts)} ({split}), /healthz ok."
    return title, [bullet]


def _args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--sha", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--today", type=date.fromisoformat, default=None)
    parser.add_argument("--no-commit", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    sha = args.sha.lower()
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        print(f"--sha must be 40 hex characters, got {args.sha!r}", file=sys.stderr)
        return 2
    path = args.state_dir / PROJECT_FILE
    if not path.is_file():
        print(f"{path}: no such file", file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8")
    if f"деплой {sha[:7]} на illouminus" in text:
        print(f"journal: deploy {sha[:7]} already recorded")
        return 0
    _, facts = load_registry(args.root)
    today = args.today or datetime.now(PARIS).date()  # Edouard's date, not the host's
    title, bullets = deploy_entry(sha, args.subject, facts, today)
    try:
        updated = insert_entry(text, title, bullets)
    except JournalError as exc:
        print(f"{path}: {exc}", file=sys.stderr)
        return 1
    path.write_text(updated, encoding="utf-8")
    if args.no_commit:
        print(f"journal: written, not committed ({title})")
        return 0
    rc = commit(args.state_dir, f"agent-facts: деплой {sha[:7]}", [PROJECT_FILE])
    if rc != 0:
        print(f"journal: state-commit exited {rc}", file=sys.stderr)
        return 1
    print(f"journal: {title}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
