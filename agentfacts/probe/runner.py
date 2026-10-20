"""One probe tick (spec 04): kill switch → load → select → read keys → run → facts → results.

Selection is pure (no network): a probe is `not-due` while its own budget or the budget of a
template it hits is running (invariant 6; `run_all` skips this check only), `skipped:no_key` when it
needs a key that is not there, `deferred` past `max_probes` probes or `max_requests` http steps,
oldest last run first. Keys are read once, after selection and before the first request, only for
the services about to run. Only `pass`/`fail` touch facts; `error` (transport error, unexpected
429, refused request) is not evidence. Every outcome moves the probe's budget (back-off).
"""

import os
import re
import time
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from agentfacts import __version__
from agentfacts.probe.assertions import evaluate
from agentfacts.probe.budget import BudgetState, TemplateKey
from agentfacts.probe.evidence import apply_outcome
from agentfacts.probe.http import (
    TIMEOUT_S,
    Refused,
    auth_for,
    base_url_for,
    make_client,
    matching_template,
    prepare,
    send,
)
from agentfacts.probe.keys import DEFAULT_KEYS_DIR, has_key, read_key
from agentfacts.probe.loader import LoadedProbe, Repo, load_repo
from agentfacts.probe.redact import Redactor
from agentfacts.probe.results import (
    ResultsLog,
    header_whitelist,
    http_step_record,
    refused_step_record,
    sleep_step_record,
)
from agentfacts.probe.templating import NOT_JSON, RunContext, rfc3339
from agentfacts.schema.models import HttpStep, Service, SleepStep
from agentfacts.schema.validate import Problem

STATE_FILE = "probe-state.sqlite"
RESULTS_FILE = "results.jsonl"
DEFAULT_VANTAGE = "illouminus"
KILL_FILE = Path("ops") / "KILL"
_VANTAGE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


@dataclass(frozen=True)
class TickOptions:
    run_all: bool = False
    max_probes: int = 50
    max_requests: int = 50
    vantage: str = DEFAULT_VANTAGE
    dry_run: bool = False
    timeout_s: float = TIMEOUT_S

    def __post_init__(self) -> None:
        if not _VANTAGE.match(self.vantage):
            raise ValueError(f"vantage {self.vantage!r} is not a slug ([a-z0-9-], ≤ 64)")
        if self.max_probes < 0 or self.max_requests < 0:
            raise ValueError("max_probes and max_requests must be ≥ 0")
        if self.timeout_s <= 0:
            raise ValueError("timeout_s must be > 0")


@dataclass(frozen=True)
class ProbeLine:
    probe_id: str
    outcome: str  # pass, fail, error, skipped:no_key; dry run: would-run, not-due, deferred
    detail: str = ""


@dataclass
class TickReport:
    killed: str | None = None
    lines: list[ProbeLine] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)
    refused: list[str] = field(default_factory=list)
    counts: Counter = field(default_factory=Counter)
    results_path: Path | None = None

    @property
    def ok(self) -> bool:
        return not self.problems and not self.refused


def kill_reason(root: Path, environ: Mapping[str, str]) -> str | None:
    if environ.get("AGENTFACTS_KILL") == "1":
        return "AGENTFACTS_KILL=1"
    if (root / KILL_FILE).exists():
        return KILL_FILE.as_posix()
    return None


@dataclass
class _Candidate:
    item: LoadedProbe
    service: Service
    templates: list[TemplateKey]
    requests: int
    keyed: bool

    @property
    def id(self) -> str:
        return self.item.probe.id


def _candidate(item: LoadedProbe, service: Service) -> _Candidate:
    templates, requests, keyed = [], 0, False
    for step in item.probe.steps:
        if isinstance(step, HttpStep):
            requests += 1
            template = matching_template(service, step.method, step.path)
            if template is not None:
                templates.append((service.key, step.method, template))
            keyed |= step.auth == "service" and service.auth is not None and (
                service.auth.kind != "none"
            )
    return _Candidate(item, service, templates, requests, keyed)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _select(
    repo: Repo,
    state: BudgetState,
    options: TickOptions,
    epoch: float,
    keys_dir: Path,
) -> list[tuple[_Candidate, str, str]]:
    """(candidate, decision, detail) for every probe, in run order."""
    candidates = [_candidate(item, repo.services[item.probe.service]) for item in repo.probes]

    def age(c: _Candidate) -> tuple[float, str]:
        last = state.last_run(c.id, options.vantage)
        return (last[0] if last else float("-inf"), c.id)

    plan: list[tuple[_Candidate, str, str]] = []
    used: set[TemplateKey] = set()
    started = requests = 0
    for c in sorted(candidates, key=age):
        budget = c.service.probe_budget.per_template_seconds
        if not options.run_all:
            wait = state.wait_seconds(c.id, c.templates, options.vantage, budget, epoch)
            if wait > 0:
                plan.append((c, "not-due", f"due in {wait} s"))
                continue
            if used & set(c.templates):
                plan.append((c, "not-due", "shares a template with a probe in this tick"))
                continue
        if c.keyed and not has_key(c.service.auth.key_name, keys_dir):
            plan.append((c, "skipped:no_key", f"no key {c.service.auth.key_name}"))
            continue
        if started >= options.max_probes or requests + c.requests > options.max_requests:
            plan.append((c, "deferred", "tick budget spent"))
            continue
        plan.append((c, "run", f"{c.requests} requests"))
        started += 1
        requests += c.requests
        used |= set(c.templates)
    return plan


@dataclass
class _Run:
    outcome: str
    detail: str = ""
    run_id: str | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)
    asserts: list[dict[str, Any]] = field(default_factory=list)
    refused: bool = False


def _execute(
    c: _Candidate,
    key: str | None,
    base_urls: Mapping[str, str],
    client: httpx.Client,
    sleep: Callable[[float], None],
    now: datetime,
) -> _Run:
    probe, service = c.item.probe, c.service
    try:
        base_url = base_urls.get(service.key) or base_url_for(service, probe.env)
    except Refused as exc:
        return _Run("error", f"refused:{exc.code}: {exc.message}", refused=True)
    whitelist = header_whitelist(service, probe)
    ctx = RunContext.start(now=now)
    run, responses = _Run("error", run_id=ctx.run_uuid), {}
    for i, step in enumerate(probe.steps, 1):
        ctx.current_step = i
        if isinstance(step, SleepStep):
            sleep(step.seconds)
            ctx.responses[i] = NOT_JSON
            run.steps.append(sleep_step_record(i, step.seconds))
            continue
        try:
            request = prepare(step, ctx, service, probe.env)
        except Refused as exc:
            run.steps.append(refused_step_record(i, step, exc))
            run.detail, run.refused = f"refused:{exc.code}: {exc.message}", True
            return run
        headers, query = auth_for(service, key) if request.uses_key else ({}, {})
        response = send(client, base_url, request, headers, query)
        responses[i] = response
        ctx.responses[i] = response.json
        run.steps.append(http_step_record(i, request, response, whitelist))
        if response.error is not None:
            run.detail = f"step {i}: {response.error}"
            return run
        if response.status == 429 and not step.expect_rate_limit:
            run.detail = f"step {i}: rate limited (429)"
            return run
    results = [evaluate(a, responses) for a in probe.assertions]
    run.asserts = [r.to_record() for r in results]
    failed = [r for r in results if not r.ok]
    run.outcome = "fail" if failed else "pass"
    if failed:
        run.detail = f"assert step {failed[0].step} {failed[0].kind}: {failed[0].detail}"
    return run


def _record(c: _Candidate, vantage: str, now: datetime, run: _Run) -> dict[str, Any]:
    probe = c.item.probe
    return {
        "version": __version__,
        "run_id": run.run_id,
        "probe_id": probe.id,
        "service": probe.service,
        "vantage": vantage,
        "env": probe.env.value,
        "account_state": probe.account_state or "any",
        "started": rfc3339(now),
        "outcome": run.outcome,
        "detail": run.detail,
        "steps": run.steps,
        "asserts": run.asserts,
        "facts": [],
    }


@dataclass
class _Tick:
    root: Path
    options: TickOptions
    keys_dir: Path
    base_urls: Mapping[str, str]
    sleep: Callable[[float], None]
    clock: Callable[[], datetime]
    environ: Mapping[str, str]
    repo: Repo
    state: BudgetState
    report: TickReport

    def dry_run(self, plan: list[tuple[_Candidate, str, str]]) -> None:
        self.report.counts["would_run"] = sum(decision == "run" for _, decision, _ in plan)
        self.report.lines = [
            ProbeLine(c.id, "would-run" if decision == "run" else decision, detail)
            for c, decision, detail in plan
        ]

    def run(self, plan: list[tuple[_Candidate, str, str]], results: Path) -> None:
        keys = {
            c.service.key: value
            for c, decision, _ in plan
            if decision == "run" and c.keyed
            and (value := read_key(c.service.auth.key_name, self.keys_dir)) is not None
        }
        redactor = Redactor.for_keys(keys.values())
        log = ResultsLog(results, redactor)
        with make_client(timeout=self.options.timeout_s) as client:
            for c, decision, detail in plan:
                if decision == "skipped:no_key":
                    self._skip(c, detail, log)
                elif decision == "run":
                    if reason := kill_reason(self.root, self.environ):
                        self.report.killed = reason
                        return
                    if c.keyed and c.service.key not in keys:  # unreadable since selection
                        self.report.counts["skipped_no_key"] += 1
                        self._skip(c, "key unreadable", log)
                    else:
                        self._probe(c, keys.get(c.service.key), client, log)

    def _skip(self, c: _Candidate, detail: str, log: ResultsLog) -> None:
        now = self.clock()
        redacted = log.append(_record(c, self.options.vantage, now, _Run("skipped:no_key", detail)))
        # The probe's own budget moves (one line per budget window); no template was used.
        self.state.record(c.id, [], self.options.vantage, now.timestamp(), "skipped:no_key")
        self.report.lines.append(ProbeLine(c.id, "skipped:no_key", redacted["detail"]))

    def _probe(self, c: _Candidate, key: str | None, client: httpx.Client, log: ResultsLog) -> None:
        now = self.clock()
        run = _execute(c, key, self.base_urls, client, self.sleep, now)
        record = _record(c, self.options.vantage, now, run)
        if run.outcome in ("pass", "fail"):
            for loaded in self.repo.facts_citing(c.id):
                change = apply_outcome(
                    loaded.path, c.item.probe, run.outcome, self.options.vantage, now
                )
                record["facts"].append({"id": loaded.fact.id, "change": change})
                if change == "invalid":
                    message = f"{loaded.fact.id} would become invalid; left as is"
                    self.report.problems.append(
                        Problem(loaded.path, 1, "fact_not_updated", message)
                    )
        redacted = log.append(record)
        self.state.record(c.id, c.templates, self.options.vantage, now.timestamp(), run.outcome)
        self.report.counts[run.outcome] += 1
        if run.refused:
            self.report.refused.append(c.id)
        self.report.lines.append(ProbeLine(c.id, run.outcome, redacted["detail"]))


def _count_key(outcome: str) -> str:
    return outcome.replace("-", "_").replace(":", "_")


def run_tick(
    root: Path,
    state_dir: Path,
    options: TickOptions,
    *,
    keys_dir: Path = DEFAULT_KEYS_DIR,
    base_urls: Mapping[str, str] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], datetime] = _utcnow,
    environ: Mapping[str, str] | None = None,
) -> TickReport:
    """Run one tick. `base_urls` (service → URL) is a test seam: it replaces the env URL and its
    vendor-host check, and is not reachable from the CLI."""
    environ = os.environ if environ is None else environ
    results = state_dir / RESULTS_FILE
    report = TickReport(results_path=None if options.dry_run else results)
    if reason := kill_reason(root, environ):
        report.killed = reason
        return report

    repo = load_repo(root)
    report.problems.extend(repo.problems)
    with BudgetState(state_dir / STATE_FILE, read_only=options.dry_run) as state:
        plan = _select(repo, state, options, clock().timestamp(), keys_dir)
        for _, decision, _ in plan:
            if decision != "run":
                report.counts[_count_key(decision)] += 1
        tick = _Tick(root, options, keys_dir, base_urls or {}, sleep, clock, environ, repo, state,
                     report)
        if options.dry_run:
            tick.dry_run(plan)
        else:
            tick.run(plan, results)
    return report
