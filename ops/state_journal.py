#!/usr/bin/env python3
"""Megabrain state journal for agent-facts (spec 08 "Megabrain state").

After a successful deploy `ops/deploy.sh` calls

    python ops/state_journal.py --sha <40 hex> --prev <deployed before> --subject <subject> \
        --root <checkout>

which puts one entry at the top of `## Журнал` in `<state>/projects/agent-facts.md` — only when
the registry says something new between `--prev` and `--sha` (a fact added, removed, or changed in
anything but its evidence counters; `agentfacts.schema.substance`). A code-only or counter-only
deploy writes nothing (incident 2026-10-20..24: ~40 lines «деплой X» for counter refreshes):

    ### 2026-10-24 — деплой a1b2c3d на illouminus

    - main a1b2c3d «<subject>»: фактов 55 (+2; verified 41 (+2), official 14, reported 0,
      stale 0, retracted 0); новые: af:x:a, af:x:b; /healthz ok.   [one line in the file]

Without `--prev` (by hand) the entry is written with the counts only.

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
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from agentfacts.pages.build import load_registry
from agentfacts.schema.models import VERIFIED_STATUSES, Fact
from agentfacts.schema.substance import substance
from agentfacts.schema.yamlio import load_yaml_text, plain

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


def remove_entry(text: str, marker: str) -> str:
    """Drop the `### ` entry whose block contains `marker` (up to the next `##`/`###` heading)."""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("### "):
            start = i
        elif line.startswith("## "):
            start = None
        if marker in line and start is not None:
            later = range(i + 1, len(lines))
            end = next((j for j in later if lines[j].startswith(("## ", "### "))), len(lines))
            return "\n".join(lines[:start] + lines[end:]) + "\n"
    return text


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


def bucket(status: str) -> str:
    """verified:* → verified; every other status is its own bucket."""
    return "verified" if status in VERIFIED_STATUSES else status


def status_counts(facts: Iterable[Fact]) -> dict[str, int]:
    """verified (any verified:*), official, reported, stale, retracted — in that order."""
    by_bucket = Counter(bucket(fact.status.value) for fact in facts)
    return {name: by_bucket.get(name, 0)
            for name in ("verified", "official", "reported", "stale", "retracted")}


@dataclass
class Delta:
    """What the registry says differently at `sha` than at `prev` (counters excluded)."""

    new: list[tuple[str, str]] = field(default_factory=list)  # (id, status)
    removed: list[tuple[str, str]] = field(default_factory=list)
    status: list[tuple[str, str, str]] = field(default_factory=list)  # (id, old, new)
    changed: list[str] = field(default_factory=list)  # same status, other substance

    def __bool__(self) -> bool:
        return bool(self.new or self.removed or self.status or self.changed)

    def buckets(self) -> Counter:
        moves: Counter = Counter()
        for _, status in self.new:
            moves[bucket(status)] += 1
        for _, status in self.removed:
            moves[bucket(status)] -= 1
        for _, old, new in self.status:
            moves[bucket(old)] -= 1
            moves[bucket(new)] += 1
        return moves


def _git(root: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                          check=False)
    if done.returncode != 0:
        raise JournalError(f"git {' '.join(args[:2])}: {done.stderr.strip()}")
    return done.stdout


def _fact_at(root: Path, rev: str, path: str) -> dict:
    data = plain(load_yaml_text(_git(root, "show", f"{rev}:{path}")))
    return data if isinstance(data, dict) else {}


def registry_delta(root: Path, prev: str, sha: str) -> Delta:
    """Fact files added, removed or changed in substance between two commits (git, not the
    working tree: the runner's uncommitted counters never count)."""
    out = _git(root, "diff", "--name-status", "--no-renames", "-z", prev, sha, "--", "facts")
    fields = out.split("\0")
    delta = Delta()
    for code, path in zip(fields[0::2], fields[1::2], strict=False):
        if not path.endswith(".yaml"):
            continue
        before = {} if code == "A" else _fact_at(root, prev, path)
        after = {} if code == "D" else _fact_at(root, sha, path)
        fact_id = str(after.get("id") or before.get("id") or Path(path).stem)
        if code == "A":
            delta.new.append((fact_id, str(after.get("status"))))
        elif code == "D":
            delta.removed.append((fact_id, str(before.get("status"))))
        elif before.get("status") != after.get("status"):
            delta.status.append((fact_id, str(before.get("status")), str(after.get("status"))))
        elif substance(before) != substance(after):
            delta.changed.append(fact_id)
    return delta


def _signed(n: int) -> str:
    return "±0" if n == 0 else f"{n:+d}"


def _ids(items: Sequence[str], limit: int = 10) -> str:
    shown = ", ".join(items[:limit])
    return shown + (f" и ещё {len(items) - limit}" if len(items) > limit else "")


def deploy_entry(
    sha: str, subject: str, facts: Sequence[Fact], today: date, delta: Delta | None = None
) -> tuple[str, list[str]]:
    counts = status_counts(facts)
    moves = delta.buckets() if delta else Counter()
    split = ", ".join(
        f"{name} {n}" + (f" ({_signed(moves[name])})" if moves[name] else "")
        for name, n in counts.items()
    )
    short = sha[:7]
    title = f"{today.isoformat()} — деплой {short} на illouminus"
    if delta is None:
        bullet = f"- main {short} «{subject}»: фактов {len(facts)} ({split}), /healthz ok."
        return title, [bullet]
    total = _signed(len(delta.new) - len(delta.removed))
    parts = [f"фактов {len(facts)} ({total}; {split})"]
    if delta.new:
        parts.append("новые: " + _ids([i for i, _ in delta.new]))
    if delta.status:
        parts.append("статус: " + _ids([f"{i} {old} → {new}" for i, old, new in delta.status]))
    if delta.changed:
        parts.append("изменены: " + _ids(delta.changed))
    if delta.removed:
        parts.append("удалены: " + _ids([i for i, _ in delta.removed]))
    return title, [f"- main {short} «{subject}»: " + "; ".join(parts) + "; /healthz ok."]


def _args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--sha", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--prev", default=None, help="sha deployed before; enables the delta")
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
    delta = None
    if args.prev:
        try:
            delta = registry_delta(args.root, args.prev, sha)
        except JournalError as exc:
            print(f"journal: {exc}", file=sys.stderr)
            return 1
        if not delta:
            print(f"journal: registry unchanged since {args.prev[:7]} (code or evidence counters "
                  "only); nothing written")
            return 0
    _, facts = load_registry(args.root)
    today = args.today or datetime.now(PARIS).date()  # Edouard's date, not the host's
    title, bullets = deploy_entry(sha, args.subject, facts, today, delta)
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
