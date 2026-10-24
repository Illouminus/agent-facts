"""One probe tick (spec 04): kill switch → load → select → read keys → run → facts → results.

Selection is pure (no network): a probe is `not-due` while its own budget or the budget of a
template it hits is running (invariant 6; `run_all` skips this check only), `skipped:no_key` when it
needs a key that is not there, `deferred` past `max_probes` probes or `max_requests` http steps,
oldest last run first. Keys are read once, after selection and before the first request, only for
the services about to run. Only `pass`/`fail` touch facts; `error` (transport error, unexpected
429, refused request) is not evidence. Every outcome moves the probe's budget (back-off).
"""

import fcntl
import os
import re
import time
from collections import Counter
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from agentfacts import __version__
from agentfacts.probe.assertions import evaluate
from agentfacts.probe.budget import BudgetState, TemplateKey
from agentfacts.probe.evidence import apply_outcome
from agentfacts.probe.google_sa import (
    GOOGLE_TOKEN_URL,
    AuthError,
    mint_access_token,
    parse_service_account,
    secrets_of,
)
from agentfacts.probe.http import (
    NO_CREDENTIALS,
    TIMEOUT_S,
    Refused,
    auth_for,
    base_url_for,
    make_client,
    matching_template,
    prepare,
    send,
    uses_key,
)
from agentfacts.probe.keys import DEFAULT_KEYS_DIR, has_key, read_key
from agentfacts.probe.loader import LoadedProbe, Repo, load_repo
from agentfacts.probe.oauth_refresh import (
    instance_base_url,
    parse_auth_url,
    refresh_access_token,
    token_url,
)
from agentfacts.probe.oauth_refresh import secrets_of as oauth_secrets_of
from agentfacts.probe.redact import Redactor
from agentfacts.probe.results import (
    ResultsLog,
    header_whitelist,
    http_step_record,
    refused_step_record,
    sleep_step_record,
)
from agentfacts.probe.templating import NOT_JSON, RunContext, rfc3339
from agentfacts.schema.models import AssertStatus, HttpStep, Service, SleepStep
from agentfacts.schema.registry import key_bound_to_service
from agentfacts.schema.validate import Problem

STATE_FILE = "probe-state.sqlite"
RESULTS_FILE = "results.jsonl"
LOCK_FILE = "probe.lock"
DEFAULT_VANTAGE = "illouminus"
KILL_FILE = Path("ops") / "KILL"
_VANTAGE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
TOKEN_MARGIN_S = 300  # a minted token is not sent in its last 5 minutes
# A refresh grant answers no lifetime; a Salesforce org's session timeout can be as short as
# 15 minutes, so a refreshed token is reused for at most 10 (with TOKEN_MARGIN_S).
OAUTH_LIFETIME_S = 900
MINTING_KINDS = frozenset({"google_service_account", "oauth_refresh_token"})
REFUSING_AUTH_ERRORS = frozenset({"bad_key_file", "foreign_host", "foreign_instance"})


def check_vantage(vantage: str) -> str:
    if not _VANTAGE.match(vantage):
        raise ValueError(f"vantage {vantage!r} is not a slug ([a-z0-9-], ≤ 64 chars)")
    return vantage


@dataclass(frozen=True)
class TickOptions:
    run_all: bool = False
    max_probes: int = 50
    max_requests: int = 50
    vantage: str = DEFAULT_VANTAGE
    dry_run: bool = False
    timeout_s: float = TIMEOUT_S

    def __post_init__(self) -> None:
        check_vantage(self.vantage)
        if self.max_probes < 0 or self.max_requests < 0:
            raise ValueError("max_probes and max_requests must be ≥ 0")
        if self.timeout_s <= 0:
            raise ValueError("timeout_s must be > 0")


@dataclass(frozen=True)
class ProbeLine:
    probe_id: str
    # pass, fail, error, skipped:no_key; dry run also would-run, not-due, deferred, refused
    outcome: str
    detail: str = ""


@dataclass
class TickReport:
    killed: str | None = None
    busy: bool = False  # another tick holds the lock: this one did nothing
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
            keyed |= uses_key(step, service)
    return _Candidate(item, service, templates, requests, keyed)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def rfc3339_epoch(epoch: float) -> str:
    return rfc3339(datetime.fromtimestamp(epoch, UTC))


def _select(
    repo: Repo,
    state: BudgetState,
    options: TickOptions,
    epoch: float,
    keys_dir: Path,
) -> list[tuple[_Candidate, str, str]]:
    """(candidate, decision, detail) for every probe, in run order."""
    candidates = [_candidate(item, repo.services[item.probe.service]) for item in repo.probes]

    def age(c: _Candidate) -> tuple[bool, float, str]:
        """Requested by the quorum first (spec 05), then oldest last run, then id."""
        last = state.last_run(c.id, options.vantage)
        asked = state.requested(c.id, options.vantage)
        return (not asked, last[0] if last else float("-inf"), c.id)

    plan: list[tuple[_Candidate, str, str]] = []
    used: set[TemplateKey] = set()
    minting: set[str] = set()  # minting services whose token request is counted
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
        if c.keyed and not key_bound_to_service(
            c.service.auth.key_name, c.service.key, c.service.hosts, c.service.auth.scopes or ()
        ):
            message = (f"refused:key_not_bound: key {c.service.auth.key_name} is not named after "
                       f"service {c.service.key}, nor a family key on the family's hosts and "
                       "scopes")
            plan.append((c, "refused", message))
            continue
        if c.keyed and not has_key(c.service.auth.key_name, keys_dir):
            plan.append((c, "skipped:no_key", f"no key {c.service.auth.key_name}"))
            continue
        # The token request of a service-account service counts once per tick, with its first
        # keyed probe (a re-mint before expiry in a long tick is not budgeted ahead).
        mints = c.keyed and c.service.auth.kind in MINTING_KINDS
        cost = c.requests + (1 if mints and c.service.key not in minting else 0)
        if started >= options.max_probes or requests + cost > options.max_requests:
            plan.append((c, "deferred", "tick budget spent"))
            continue
        plan.append((c, "run", f"{c.requests} request" + ("s" if c.requests != 1 else "")))
        started += 1
        requests += cost
        if mints:
            minting.add(c.service.key)
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
    redactor: Redactor,
) -> _Run:
    probe, service = c.item.probe, c.service
    try:
        base_url = base_urls.get(service.key) or base_url_for(service, probe.env)
    except Refused as exc:
        return _Run("error", f"refused:{exc.code}: {exc.message}", refused=True)
    whitelist = header_whitelist(service, probe)
    # A 5xx is an outage, not a non-reproduction, unless the probe asserts that very status.
    expected_5xx = {
        a.step for a in probe.assertions if isinstance(a, AssertStatus) and a.status >= 500
    }
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
        try:
            credentials = auth_for(service, key) if request.uses_key else NO_CREDENTIALS
        except Refused as exc:
            run.steps.append(refused_step_record(i, step, exc))
            run.detail, run.refused = f"refused:{exc.code}: {exc.message}", True
            return run
        response = send(client, base_url, request, credentials)
        responses[i] = response
        ctx.responses[i] = response.json
        run.steps.append(http_step_record(i, request, response, whitelist, redactor))
        if response.error is not None:
            run.detail = f"step {i}: {response.error}"
            return run
        if response.status == 429 and not step.expect_rate_limit:
            run.detail = f"step {i}: rate limited (429)"
            return run
        if response.status >= 500 and i not in expected_5xx:
            run.detail = f"step {i}: server error ({response.status})"
            return run
    results = [evaluate(a, responses) for a in probe.assertions]
    run.asserts = [r.to_record() for r in results]
    failed = [r for r in results if not r.ok]
    run.outcome = "fail" if failed else "pass"
    if failed:
        run.detail = f"assert step {failed[0].step} {failed[0].kind}: {failed[0].detail}"
    return run


def _record(c: _Candidate, options: TickOptions, now: datetime, run: _Run) -> dict[str, Any]:
    """`selection` says whether the tick honoured the budgets (`due`) or ran everything (`all`)."""
    probe = c.item.probe
    return {
        "version": __version__,
        "run_id": run.run_id,
        "probe_id": probe.id,
        "service": probe.service,
        "vantage": options.vantage,
        "selection": "all" if options.run_all else "due",
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
    token_urls: Mapping[str, str] = field(default_factory=dict)
    # service → (access token, base URL the token names or None, epoch it stops being used), or
    # why there is none: a failure is not retried within the tick, a token is minted again
    # before it expires.
    tokens: dict[str, tuple[str, str | None, float] | AuthError] = field(default_factory=dict)

    def line(self, c: _Candidate, outcome: str, detail: str) -> None:
        self.report.counts[_count_key(outcome)] += 1
        self.report.lines.append(ProbeLine(c.id, outcome, detail))

    def dry_run(self, plan: list[tuple[_Candidate, str, str]]) -> None:
        for c, decision, detail in plan:
            self.line(c, "would-run" if decision == "run" else decision, detail)

    def run(self, plan: list[tuple[_Candidate, str, str]], results: Path) -> None:
        keys = {
            c.service.key: value
            for c, decision, _ in plan
            if decision == "run" and c.keyed
            and (value := read_key(c.service.auth.key_name, self.keys_dir)) is not None
        }
        redactor = Redactor.for_keys(keys.values())
        for service_key, value in keys.items():
            kind = self.repo.services[service_key].auth.kind
            if kind == "google_service_account":
                redactor.add(secrets_of(value))
            elif kind == "oauth_refresh_token":
                redactor.add(oauth_secrets_of(value))
        log = ResultsLog(results, redactor)
        with make_client(timeout=self.options.timeout_s) as client:
            for c, decision, detail in plan:
                if decision in ("not-due", "deferred"):  # counted, not printed: timer noise
                    self.report.counts[_count_key(decision)] += 1
                elif decision == "skipped:no_key":
                    self._skip(c, detail, log)
                elif decision == "refused":
                    self._refuse(c, detail, log)
                elif decision == "run":
                    if reason := kill_reason(self.root, self.environ):
                        self.report.killed = reason
                        return
                    if c.keyed and c.service.key not in keys:  # unreadable since selection
                        self._skip(c, "key unreadable", log)
                    else:
                        self._probe(c, keys.get(c.service.key), client, log, redactor)

    def _skip(self, c: _Candidate, detail: str, log: ResultsLog) -> None:
        now = self.clock()
        redacted = log.append(_record(c, self.options, now, _Run("skipped:no_key", detail)))
        # The probe's own budget moves (one line per budget window); no template was used.
        self.state.record(c.id, [], self.options.vantage, now.timestamp(), "skipped:no_key")
        self.line(c, "skipped:no_key", redacted["detail"])

    def _refuse(self, c: _Candidate, detail: str, log: ResultsLog) -> None:
        """A probe refused before any request (its key is not bound to its service)."""
        now = self.clock()
        redacted = log.append(_record(c, self.options, now, _Run("error", detail)))
        self.state.record(c.id, [], self.options.vantage, now.timestamp(), "error")
        self.report.refused.append(c.id)
        self.line(c, "error", redacted["detail"])

    def _probe(
        self,
        c: _Candidate,
        key: str | None,
        client: httpx.Client,
        log: ResultsLog,
        redactor: Redactor,
    ) -> None:
        now = self.clock()
        secret, templates, base_urls = key, c.templates, self.base_urls
        if c.keyed and c.service.auth.kind in MINTING_KINDS:
            minted = self._access_token(c.service, key, client, redactor)
            if isinstance(minted, AuthError):
                secret = minted
            else:
                secret, instance = minted
                if instance is not None and c.service.key not in base_urls:
                    base_urls = {**base_urls, c.service.key: instance}
        if isinstance(secret, AuthError):
            # No probe request was sent: a bad key file or a host off the service's hosts is
            # refused (an operator fixes it), a failed token exchange is an outage. Neither is
            # evidence; no template was used.
            run = _Run("error", f"auth:{secret.code}: {secret.message}",
                       refused=secret.code in REFUSING_AUTH_ERRORS)
            templates = []
        else:
            run = _execute(c, secret, base_urls, client, self.sleep, now, redactor)
        record = _record(c, self.options, now, run)
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
        self.state.record(c.id, templates, self.options.vantage, now.timestamp(), run.outcome)
        if run.refused:
            self.report.refused.append(c.id)
        self.line(c, run.outcome, redacted["detail"])

    def _access_token(
        self, service: Service, key: str | None, client: httpx.Client, redactor: Redactor
    ) -> tuple[str, str | None] | AuthError:
        """(access token, base URL it names or None) per service, reused within the tick until
        `TOKEN_MARGIN_S` before it expires (sleep steps can make a tick long); the token joins
        the redactor before any write, and before its instance URL is even checked."""
        cached = self.tokens.get(service.key)
        if isinstance(cached, AuthError):
            return cached
        now = self.clock()
        if cached is not None and now.timestamp() < cached[2]:
            return cached[0], cached[1]
        instance = None
        try:
            if service.auth.kind == "google_service_account":
                account = parse_service_account(key or "")
                url = self.token_urls.get(service.key, GOOGLE_TOKEN_URL)
                token, lifetime = mint_access_token(client, account, service.auth.scopes, now,
                                                    url)
                redactor.add({token})
            else:
                grant = parse_auth_url(key or "")
                url = token_url(service, grant)  # refuses a key host off the service's hosts
                token, answered = refresh_access_token(
                    client, grant, self.token_urls.get(service.key, url))
                redactor.add({token})
                instance, lifetime = instance_base_url(service, answered), OAUTH_LIFETIME_S
        except AuthError as exc:
            self.tokens[service.key] = exc
            return exc
        self.tokens[service.key] = (token, instance, now.timestamp() + lifetime - TOKEN_MARGIN_S)
        return token, instance


def _count_key(outcome: str) -> str:
    return outcome.replace("-", "_").replace(":", "_")


@contextmanager
def _tick_lock(state_dir: Path) -> Iterator[bool]:
    """One tick at a time per state dir: two overlapping ticks would both see the same probes due
    (double requests, invariant 6) and race on the same fact files. False = another tick runs."""
    state_dir.mkdir(parents=True, exist_ok=True)
    with (state_dir / LOCK_FILE).open("a") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


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
    token_urls: Mapping[str, str] | None = None,
) -> TickReport:
    """Run one tick. `base_urls` and `token_urls` (service → URL) are test seams: they replace
    the env URL (or the instance a token names) and its vendor-host check, and the token
    endpoint; neither is reachable from the CLI."""
    environ = os.environ if environ is None else environ
    results = state_dir / RESULTS_FILE
    report = TickReport(results_path=None if options.dry_run else results)
    if reason := kill_reason(root, environ):
        report.killed = reason
        return report

    # A dry run writes nothing, so it needs no lock (and must not create the state dir).
    with nullcontext(True) if options.dry_run else _tick_lock(state_dir) as locked:
        if not locked:
            report.busy = True
            return report
        repo = load_repo(root)
        report.problems.extend(repo.problems)
        with BudgetState(state_dir / STATE_FILE, read_only=options.dry_run) as state:
            plan = _select(repo, state, options, clock().timestamp(), keys_dir)
            tick = _Tick(root, options, keys_dir, base_urls or {}, sleep, clock, environ, repo,
                         state, report, token_urls or {})
            if options.dry_run:
                tick.dry_run(plan)
            else:
                tick.run(plan, results)
    return report


@dataclass(frozen=True)
class ProbeStatus:
    probe_id: str
    env: str
    requests: int
    key: str  # none (keyless), ok, missing, unbound (key_name not named after the service)
    last_run: tuple[float, str] | None
    wait_s: int  # 0 = due


def probe_status(
    root: Path,
    state_dir: Path,
    vantage: str = DEFAULT_VANTAGE,
    *,
    keys_dir: Path = DEFAULT_KEYS_DIR,
    clock: Callable[[], datetime] = _utcnow,
) -> tuple[list[ProbeStatus], list[Problem]]:
    """What `probe run --due` would consider, without writing anything."""
    check_vantage(vantage)
    repo = load_repo(root)
    epoch = clock().timestamp()
    statuses = []
    with BudgetState(state_dir / STATE_FILE, read_only=True) as state:
        for item in sorted(repo.probes, key=lambda i: i.probe.id):
            c = _candidate(item, repo.services[item.probe.service])
            key = "none"
            if c.keyed and not key_bound_to_service(
                c.service.auth.key_name, c.service.key, c.service.hosts,
                c.service.auth.scopes or (),
            ):
                key = "unbound"
            elif c.keyed:
                key = "ok" if has_key(c.service.auth.key_name, keys_dir) else "missing"
            budget = c.service.probe_budget.per_template_seconds
            statuses.append(ProbeStatus(
                c.id,
                item.probe.env.value,
                c.requests,
                key,
                state.last_run(c.id, vantage),
                state.wait_seconds(c.id, c.templates, vantage, budget, epoch),
            ))
    return statuses, repo.problems
