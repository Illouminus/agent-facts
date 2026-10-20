"""`agentfacts quorum run`: one pass over the current salt period (spec 05, hourly timer).

For each group: below quorum → nothing; already a fact → refresh its evidence; new → a
`reported` draft under `facts/<service>/`, validated like any file, and its probe (if one can
reproduce it) requested due for the next runner tick. A dry run reads only: no file, no state.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from agentfacts.probe.budget import BudgetState
from agentfacts.probe.loader import load_repo
from agentfacts.probe.runner import DEFAULT_VANTAGE, STATE_FILE, check_vantage, kill_reason
from agentfacts.quorum.draft import (
    covering_fact,
    draft_document,
    matching_probe,
    refresh_fact,
    write_draft,
)
from agentfacts.quorum.group import Group, group_observations, load_observations, period_window
from agentfacts.quorum.rules import slug_base, unique_slug
from agentfacts.schema.models import Status
from agentfacts.schema.validate import Problem, validate_paths

DEFAULT_ENV = "prod"  # nobody said, no probe decides: reporters mostly call production


@dataclass(frozen=True)
class QuorumLine:
    action: str  # draft, refresh, covered, below, skipped
    group: Group
    fact_id: str | None = None
    path: Path | None = None
    probe_id: str | None = None
    detail: str = ""


@dataclass
class QuorumReport:
    window: tuple[datetime, datetime]
    killed: str | None = None
    lines: list[QuorumLine] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    def count(self, action: str) -> int:
        return sum(1 for line in self.lines if line.action == action)


def _taken(root: Path, service: str) -> set[str]:
    folder = root / "facts" / service
    return {p.stem for p in folder.glob("*.yaml")} if folder.is_dir() else set()


def run_quorum(
    root: Path,
    db: Path,
    state_dir: Path,
    *,
    now: datetime,
    vantage: str = DEFAULT_VANTAGE,
    since: date | None = None,
    dry_run: bool = False,
    environ: Mapping[str, str] | None = None,
) -> QuorumReport:
    check_vantage(vantage)
    window = period_window(now, since)
    report = QuorumReport(window)
    if reason := kill_reason(root, environ if environ is not None else {}):
        report.killed = reason
        return report
    groups = group_observations(load_observations(db, *window))
    repo = load_repo(root)
    taken: dict[str, set[str]] = {}
    with BudgetState(state_dir / STATE_FILE, read_only=dry_run) as budget:
        for group in groups:
            report.lines.append(
                _one(root, repo, group, taken, budget, now, vantage, dry_run, report)
            )
    return report


def _one(root, repo, group, taken, budget, now, vantage, dry_run, report) -> QuorumLine:
    if not group.meets_quorum:
        nets, clients = len(group.nets), group.clients
        return QuorumLine("below", group, detail=f"{nets} nets, {clients} clients")
    service = repo.services.get(group.service)
    http = service.surfaces.http if service else None
    if http is None or (group.method, group.path_template) not in {
        (t.method, t.path) for t in http.templates
    }:
        return QuorumLine("skipped", group, detail="service or template no longer registered")

    covering = covering_fact(group, repo.facts)
    if covering is not None:
        fact = covering.fact
        if fact.status is Status.retracted:
            return QuorumLine("covered", group, fact.id, covering.path, detail="retracted")
        changed = not dry_run and refresh_fact(covering.path, group, now)
        action = "refresh" if changed else "covered"
        return QuorumLine(action, group, fact.id, covering.path, detail=f"{len(group.nets)} nets")

    probe = matching_probe(group, repo.probes, service, group.env)
    env = group.env or (probe.probe.env.value if probe else DEFAULT_ENV)
    account_state = (probe.probe.account_state if probe else None) or "any"
    names = taken.setdefault(group.service, _taken(root, group.service))
    slug = unique_slug(slug_base(group.status, group.normalized), names)
    names.add(slug)
    probe_id = probe.probe.id if probe else None
    document = draft_document(
        group, slug, env=env, account_state=account_state, probe_id=probe_id, now=now
    )
    path = root / "facts" / group.service / f"{slug}.yaml"
    detail = "probe requested" if probe else "needs a probe"
    if dry_run:
        return QuorumLine("draft", group, document["id"], path, probe_id, detail)
    write_draft(path, document)
    problems = validate_paths([path], root=root).problems
    if problems:  # never leave a file CI would reject
        path.unlink()
        report.problems.extend(problems)
        return QuorumLine("skipped", group, document["id"], detail="draft failed validation")
    if probe is not None:
        budget.request_due(probe.probe.id, vantage, now.timestamp())
    return QuorumLine("draft", group, document["id"], path, probe_id, detail)
