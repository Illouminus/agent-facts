"""What the bot would publish: fact files changed in the checkout, minus any that `main` changed
in the meantime, with the facts read for the PR table and the auto-merge rule (spec 05 Bot).

A row is `substantive` when the fact is new, deleted, unreadable, or its substance changed
(`schema.substance`: anything but the evidence counters); a counter-only row waits for the daily
evidence refresh PR."""

import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError
from ruamel.yaml.error import YAMLError

from apifacts.schema.models import VERIFIED_STATUSES, Fact, Source, Status
from apifacts.schema.substance import substance
from apifacts.schema.yamlio import load_yaml, load_yaml_text, plain

FACTS_DIR = "facts"
BASE = "origin/main"


class GitError(RuntimeError):
    pass


def git(root: Path, *args: str, env: Mapping[str, str] | None = None) -> str:
    """Run git in `root`; its stdout, GitError with stderr on failure."""
    done = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, env=env, check=False
    )
    if done.returncode != 0:
        raise GitError(f"git {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout


@dataclass(frozen=True)
class Change:
    path: str  # repository-relative, posix
    deleted: bool = False


def changed_facts(root: Path) -> list[Change]:
    """Fact files modified, added (untracked too) or deleted under `facts/` versus HEAD."""
    out = git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", FACTS_DIR)
    entries = out.split("\0")
    changes: dict[str, Change] = {}
    i = 0
    while i < len(entries) and entries[i]:
        code, path = entries[i][:2], entries[i][3:]
        i += 1
        if code[0] in "RC":  # a rename lists its source next: that path is gone from HEAD's view
            source = entries[i]
            i += 1
            if code[0] == "R":
                changes[source] = Change(source, deleted=True)
        changes[path] = Change(path, deleted="D" in code)
    return [c for _, c in sorted(changes.items()) if c.path.endswith(".yaml")]


def _blob(root: Path, rev: str, path: str) -> str | None:
    try:
        return git(root, "rev-parse", "--verify", "--quiet", f"{rev}:{path}").strip()
    except GitError:
        return None


def already_on(root: Path, change: Change, base: str = BASE) -> bool:
    """`base` already holds exactly this change (a bot PR merged while the checkout was not yet
    synced): nothing to publish, and not a conflict either."""
    on_base = _blob(root, base, change.path)
    if change.deleted:
        return on_base is None
    return on_base is not None and git(root, "hash-object", "--", change.path).strip() == on_base


def drifted(root: Path, changes: Sequence[Change], base: str = BASE) -> list[str]:
    """Paths whose committed version differs between HEAD and `base`: `main` changed them after
    this checkout was synced, so publishing the local file would overwrite that change."""
    return [c.path for c in changes if _blob(root, "HEAD", c.path) != _blob(root, base, c.path)]


@dataclass(frozen=True)
class FactRow:
    path: str
    change: str  # new, changed, deleted
    id: str
    kind: str
    status: str
    evidence: str
    eligible: bool  # may merge without a human (spec 05)
    substantive: bool = True  # False: only evidence counters moved (daily refresh PR)
    quorum_draft: bool = False  # a new `reported` fact from the quorum: the weekly PR (D-093)


def _evidence(fact: Fact) -> str:
    ev = fact.evidence
    if fact.status in VERIFIED_STATUSES and ev.probe:
        return f"probe {ev.probe.rsplit(':', 1)[1]} ×{ev.confirmations or 0}"
    if fact.provenance.source is Source.observation_quorum:
        return f"quorum: {ev.observations or 0} networks" + (
            f", probe {ev.probe.rsplit(':', 1)[1]}" if ev.probe else ", needs a probe"
        )
    return ev.official_url or (f"probe {ev.probe.rsplit(':', 1)[1]}" if ev.probe else "manual")


def _eligible(fact: Fact) -> bool:
    """`verified:*` and authored by the bot. A `reported` fact — even from quorum — and a fact a
    human wrote need a human review `[tap]`: anonymous reporters must not publish on their own
    (sec card 2026-10-23, variant 1, D-089)."""
    return fact.provenance.author == "bot" and fact.status in VERIFIED_STATUSES


def _counters_only(root: Path, path: str, local: object) -> bool:
    """The committed version of `path` says the same as `local` but for evidence counters."""
    try:
        committed = load_yaml_text(git(root, "show", f"HEAD:{path}"))
    except (GitError, YAMLError):
        return False
    return isinstance(committed, dict) and substance(committed) == substance(local)


def fact_rows(root: Path, changes: Sequence[Change]) -> list[FactRow]:
    """One row per change; an unreadable or invalid file is a row with status `invalid` (never
    eligible), a deletion is never eligible either."""
    rows = []
    for change in changes:
        stem = Path(change.path).stem
        if change.deleted:
            rows.append(FactRow(change.path, "deleted", stem, "-", "deleted", "-", False))
            continue
        kind = "new" if _blob(root, "HEAD", change.path) is None else "changed"
        try:
            data = plain(load_yaml(root / change.path))
            fact = Fact.model_validate(data)
        except (OSError, YAMLError, ValidationError, ValueError):
            rows.append(FactRow(change.path, kind, stem, "-", "invalid", "-", False))
            continue
        counters = kind == "changed" and _counters_only(root, change.path, data)
        draft = (kind == "new" and fact.status is Status.reported
                 and fact.provenance.source is Source.observation_quorum)
        rows.append(FactRow(change.path, kind, fact.id, fact.kind.value, fact.status.value,
                            _evidence(fact), _eligible(fact), substantive=not counters,
                            quorum_draft=draft))
    return rows


def auto_mergeable(rows: Sequence[FactRow]) -> bool:
    return bool(rows) and all(r.eligible for r in rows)
