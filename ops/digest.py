#!/usr/bin/env python3
"""Weekly digest of agent-facts (spec 08): facts, check() traffic, probe runs, taps to come.

    ops/digest.py [--root R] [--state-dir S] [--now ISO] [--current] [--dry-run] [--no-send]

Reads only local files: `facts/` + `services/` (the registry), `var/results.jsonl` (probe runs),
`var/observations.sqlite` (check(), opened read-only), `ops/publish-policy.yaml`. No LLM, no vendor
API. Output:

1. `<state>/reviews/agent-facts-<YYYY-MM-DD>.md` — the report (megabrain rule: a report lives in
   state/reviews, rendered at ops.baillot.dev/reports; Telegram only pings);
2. a "needs a probe" card in `<state>/tasks/` when reported facts have no probe and no such card is
   open (spec 05: an agent-hours item, no tap);
3. one entry in the journal `projects/agent-facts.md` (spec 08: a line per weekly digest);
4. one `bin/state-commit --as agent-facts` for exactly those paths;
5. a 5–8 line ping through the Telegram gateway (`send_telegram`, class `digest`, header
   `X-Routine: agent-facts-digest`). The gateway decides; a diverted ping is reported, not retried.

Window = the last complete reporter-net salt period (Monday 00:00 UTC → Monday 00:00 UTC, D-085),
so "networks" is an exact distinct count; `--current` takes the running period up to now (test
runs). `--dry-run` prints the report and the ping and touches nothing.

Exit codes: 0 done (also when the gateway diverted the ping), 1 a write, commit or delivery
failed, 2 usage.
"""

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import state_journal  # noqa: E402  (ops/ is a script directory, not a package)

from agentfacts.pages.build import load_registry  # noqa: E402
from agentfacts.schema.models import Fact, Service  # noqa: E402

PARIS = ZoneInfo("Europe/Paris")
ROUTINE = "agent-facts-digest"
GATEWAY = "http://127.0.0.1:8787/mcp"
REPORTS_URL = "https://ops.baillot.dev/reports"
DEFAULT_BUDGET_S = 300  # spec 04 default per-template budget
CARD_SUFFIX = "agent-facts-needs-a-probe"
RUN_OUTCOMES = ("pass", "fail", "error")
_NO_KEY = re.compile(r"no key (\S+)")


# ── window ─────────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Window:
    start: datetime  # UTC, inclusive
    end: datetime  # UTC, exclusive
    complete: bool

    @property
    def week(self) -> int:
        return self.start.isocalendar().week

    @property
    def days(self) -> tuple[str, ...]:
        """UTC dates the window touches (counters are kept per UTC day)."""
        last = (self.end - timedelta(microseconds=1)).date()
        n = (last - self.start.date()).days + 1
        return tuple((self.start.date() + timedelta(days=i)).isoformat() for i in range(n))

    def contains(self, moment: datetime) -> bool:
        return self.start <= moment < self.end

    def contains_date(self, day: date) -> bool:
        return self.start.date() <= day <= (self.end - timedelta(microseconds=1)).date()


def salt_window(now: datetime, current: bool = False) -> Window:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(UTC)
    monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0,
                                                          microsecond=0)
    if current:
        return Window(monday, now, complete=False)
    return Window(monday - timedelta(days=7), monday, complete=True)


def _moment(text: Any) -> datetime | None:
    try:
        moment = datetime.fromisoformat(str(text))
    except ValueError:
        return None
    return moment if moment.tzinfo else None


# ── facts ──────────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FactMetrics:
    total: int
    counts: dict[str, int]  # verified, official, reported, stale, retracted
    added: int  # provenance.created inside the window
    confirmed: int  # evidence.last_confirmed inside the window
    by_service: dict[str, int]
    needs_probe: tuple[str, ...]  # reported facts without evidence.probe


def fact_metrics(facts: Sequence[Fact], window: Window) -> FactMetrics:
    added = sum(1 for f in facts if window.contains_date(date.fromisoformat(f.provenance.created)))
    confirmed = 0
    for fact in facts:
        moment = _moment(fact.evidence.last_confirmed) if fact.evidence.last_confirmed else None
        confirmed += bool(moment and window.contains(moment))
    return FactMetrics(
        total=len(facts),
        counts=state_journal.status_counts(facts),
        added=added,
        confirmed=confirmed,
        by_service=dict(sorted(Counter(f.service for f in facts).items())),
        needs_probe=tuple(sorted(
            f.id for f in facts if f.status.value == "reported" and f.evidence.probe is None
        )),
    )


# ── probe runs ─────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ProbeMetrics:
    available: bool
    outcomes: dict[str, int] = field(default_factory=dict)
    runs: int = 0
    probes: int = 0
    vantages: dict[str, int] = field(default_factory=dict)
    missing_keys: tuple[str, ...] = ()
    budget_violations: int = 0
    violation_keys: tuple[str, ...] = ()
    bad_lines: int = 0
    last_run: str | None = None


def probe_metrics(path: Path, services: Iterable[Service], window: Window) -> ProbeMetrics:
    """Runs in the window from results.jsonl. A budget violation = two runs that hit one
    (service, method, template, vantage) closer than the service's per-template budget
    (invariant 6; `probe run --all` ignores that budget by design, so a manual --all shows here)."""
    if not path.is_file():
        return ProbeMetrics(available=False)
    budget = {s.key: s.probe_budget.per_template_seconds for s in services}
    outcomes: Counter[str] = Counter()
    vantages: Counter[str] = Counter()
    probes: set[str] = set()
    keys: set[str] = set()
    hits: defaultdict[tuple[str, str, str, str], list[datetime]] = defaultdict(list)
    bad = 0
    last: datetime | None = None
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                record = json.loads(line)
                started = _moment(record["started"])
                outcome = str(record["outcome"])
            except (ValueError, KeyError, TypeError):
                bad += 1
                continue
            if started is None:
                bad += 1
                continue
            if not window.contains(started):
                continue
            outcomes[outcome] += 1
            if outcome == "skipped:no_key":
                if match := _NO_KEY.search(str(record.get("detail") or "")):
                    keys.add(match.group(1))
                continue
            if outcome not in RUN_OUTCOMES:
                continue
            probes.add(str(record.get("probe_id")))
            vantage = str(record.get("vantage"))
            vantages[vantage] += 1
            last = max(last, started) if last else started
            service = str(record.get("service"))
            used = {(service, str(s.get("method")), str(s.get("template")), vantage)
                    for s in record.get("steps") or ()
                    if s.get("do") == "http" and s.get("template") and not s.get("refused")}
            for key in used:
                hits[key].append(started)
    violations = 0
    violated: set[str] = set()
    for key, moments in hits.items():
        moments.sort()
        limit = budget.get(key[0], DEFAULT_BUDGET_S)
        for earlier, later in zip(moments, moments[1:], strict=False):
            if (later - earlier).total_seconds() < limit:
                violations += 1
                violated.add(f"{key[0]} {key[1]} {key[2]} @{key[3]}")
    return ProbeMetrics(
        available=True,
        outcomes=dict(sorted(outcomes.items())),
        runs=sum(outcomes[o] for o in RUN_OUTCOMES),
        probes=len(probes),
        vantages=dict(sorted(vantages.items())),
        missing_keys=tuple(sorted(keys)),
        budget_violations=violations,
        violation_keys=tuple(sorted(violated)),
        bad_lines=bad,
        last_run=last.strftime("%Y-%m-%dT%H:%M:%SZ") if last else None,
    )


# ── check() ────────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CheckMetrics:
    available: bool
    stored: int = 0
    unregistered: int = 0
    top_unregistered: tuple[tuple[str, int], ...] = ()
    dropped: dict[str, int] = field(default_factory=dict)
    networks: int = 0
    ua_classes: dict[str, int] = field(default_factory=dict)

    @property
    def counted(self) -> int:
        """check() calls the API counts: stored, unregistered, dropped. Answered pre-flight calls
        on a registered target are not counted anywhere (spec 03, Q5)."""
        return self.stored + self.unregistered + sum(self.dropped.values())


def check_metrics(db: Path, window: Window) -> CheckMetrics:
    if not db.is_file():
        return CheckMetrics(available=False)
    con = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)
    try:
        days = window.days
        marks = ", ".join("?" * len(days))
        counters = Counter[str]()
        for name, n in con.execute(
            f"SELECT name, SUM(n) FROM counters WHERE day IN ({marks}) GROUP BY name", days
        ):
            counters[name] = int(n)
        bounds = (window.start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                  window.end.strftime("%Y-%m-%dT%H:%M:%SZ"))
        where = "received_at >= ? AND received_at < ?"
        (networks,) = con.execute(
            f"SELECT COUNT(DISTINCT reporter_net) FROM observations WHERE {where}", bounds
        ).fetchone()
        ua = dict(con.execute(
            f"SELECT reporter_ua_class, COUNT(*) FROM observations WHERE {where} "
            "GROUP BY reporter_ua_class ORDER BY reporter_ua_class", bounds
        ).fetchall())
    except sqlite3.Error as exc:
        print(f"digest: {db}: {exc}", file=sys.stderr)
        return CheckMetrics(available=False)
    finally:
        con.close()
    # `unregistered_target` is the total; `unregistered_target:<host>` rows are its breakdown
    # (summing the prefix would count every call twice — W4 hand-over).
    hosts = Counter({name.split(":", 1)[1]: n for name, n in counters.items()
                     if name.startswith("unregistered_target:")})
    top = tuple(sorted(((h, n) for h, n in hosts.items() if h != "other"),
                       key=lambda item: (-item[1], item[0]))[:3])
    return CheckMetrics(
        available=True,
        stored=counters["stored"],
        unregistered=counters["unregistered_target"],
        top_unregistered=top,
        dropped={k: v for k, v in sorted(counters.items()) if k.startswith("dropped_")},
        networks=int(networks),
        ua_classes=ua,
    )


# ── publications ───────────────────────────────────────────────────────────────────────────────


class PolicyError(Exception):
    pass


_POLICY_KEYS = {"version", "approved", "approved_by", "approved_on", "vendors", "rules",
                "templates", "ledger"}
_RULE_KEYS = {"statuses", "exclude_kinds", "min_confirmations", "max_items_per_batch",
              "forbidden"}


@dataclass(frozen=True)
class Policy:
    approved: bool
    vendors: frozenset[str]
    statuses: frozenset[str]
    exclude_kinds: frozenset[str]
    min_confirmations: int
    ledger: str


def load_policy(path: Path) -> Policy:
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise PolicyError(f"{path}: {exc}") from None
    if not isinstance(doc, dict):
        raise PolicyError(f"{path}: not a mapping")
    if unknown := set(doc) - _POLICY_KEYS:
        raise PolicyError(f"{path}: unknown keys {sorted(unknown)}")
    rules = doc.get("rules") or {}
    if not isinstance(rules, dict) or (unknown := set(rules) - _RULE_KEYS):
        raise PolicyError(f"{path}: rules: unknown keys {sorted(unknown)}")
    return Policy(
        approved=doc.get("approved") is True,
        vendors=frozenset(doc.get("vendors") or ()),
        statuses=frozenset(rules.get("statuses") or ()),
        exclude_kinds=frozenset(rules.get("exclude_kinds") or ()),
        min_confirmations=int(rules.get("min_confirmations") or 0),
        ledger=str(doc.get("ledger") or "var/publications.jsonl"),
    )


def published_ids(ledger: Path) -> set[str]:
    if not ledger.is_file():
        return set()
    ids = set()
    for line in ledger.read_text(encoding="utf-8").splitlines():
        try:
            ids.add(str(json.loads(line)["fact"]))
        except (ValueError, KeyError, TypeError):
            continue
    return ids


def publication_candidates(policy: Policy, facts: Iterable[Fact], published: set[str]
                           ) -> tuple[str, ...]:
    return tuple(sorted(
        f.id for f in facts
        if f.status.value in policy.statuses
        and f.service in policy.vendors
        and f.kind.value not in policy.exclude_kinds
        and (f.evidence.confirmations or 0) >= policy.min_confirmations
        and not f.evidence.stale_counter
        and f.id not in published
    ))


# ── the digest ─────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Digest:
    window: Window
    today: date  # Paris date of the run: names the report and the card
    facts: FactMetrics
    probes: ProbeMetrics
    checks: CheckMetrics
    policy_approved: bool | None  # None: policy unreadable
    candidates: tuple[str, ...]
    open_card: str | None = None

    @property
    def report_id(self) -> str:
        return f"agent-facts-{self.today.isoformat()}"


def build(root: Path, now: datetime, current: bool = False, results: Path | None = None,
          db: Path | None = None, policy_path: Path | None = None,
          open_card: str | None = None) -> Digest:
    window = salt_window(now, current)
    services, facts = load_registry(root)
    policy_path = policy_path or root / "ops" / "publish-policy.yaml"
    try:
        policy = load_policy(policy_path)
    except PolicyError as exc:
        print(f"digest: {exc}", file=sys.stderr)
        policy = None
    candidates = ()
    if policy is not None:
        candidates = publication_candidates(policy, facts, published_ids(root / policy.ledger))
    return Digest(
        window=window,
        today=now.astimezone(PARIS).date(),
        facts=fact_metrics(facts, window),
        probes=probe_metrics(results or root / "var" / "results.jsonl", services, window),
        checks=check_metrics(db or root / "var" / "observations.sqlite", window),
        policy_approved=None if policy is None else policy.approved,
        candidates=candidates,
        open_card=open_card,
    )


def _span(w: Window) -> str:
    last = (w.end - timedelta(microseconds=1)).date()
    return f"{w.start:%d.%m}–{last:%d.%m.%Y}"


def _counts_line(d: Digest) -> str:
    c = d.facts.counts
    return " · ".join(f"{name} {c[name]}" for name in c)


def _publications_line(d: Digest) -> str:
    n = len(d.candidates)
    if d.policy_approved is None:
        return f"публикации: ops/publish-policy.yaml не читается, кандидатов {n}"
    if not d.policy_approved:
        return f"публикации: политика не утверждена, кандидатов {n}"
    return f"публикации: политика утверждена, кандидатов {n} (кнопка ещё не подключена)"


def _probes_line(d: Digest) -> str:
    p = d.probes
    if not p.available:
        return "пробы: нет var/results.jsonl"
    split = ", ".join(f"{p.outcomes.get(o, 0)} {o}" for o in RUN_OUTCOMES if p.outcomes.get(o))
    keys = ", ".join(p.missing_keys) or "—"
    return (f"пробы: {p.runs} прогонов ({split or '—'}) · нарушений бюджета "
            f"{p.budget_violations} · ключей нет: {keys}")


def _check_line(d: Digest) -> str:
    c = d.checks
    if not c.available:
        return "check(): нет var/observations.sqlite"
    top = f" (top: {', '.join(h for h, _ in c.top_unregistered)})" if c.top_unregistered else ""
    return (f"check(): {c.counted} обращений · сетей {c.networks} · незарегистрированных целей "
            f"{c.unregistered}{top}")


def _needs_probe_line(d: Digest) -> str:
    n = len(d.facts.needs_probe)
    line = f"нужна проба: {n} reported без пробы"
    if n and d.open_card:
        line += f" → карточка {d.open_card}"
    return line


def render_ping(d: Digest, reports_url: str) -> str:
    title = f"agent-facts · неделя {d.window.week}"
    if not d.window.complete:
        title += " (неполная)"
    f = d.facts
    lines = [
        title,
        f"факты: {f.total} (+{f.added}) · {_counts_line(d)}",
        _check_line(d),
        _probes_line(d),
        _needs_probe_line(d),
        _publications_line(d),
        f"{reports_url.rstrip('/')}/{d.report_id}",
    ]
    return "\n".join(lines)


def render_report(d: Digest) -> str:
    w, f, p, c = d.window, d.facts, d.probes, d.checks
    title = f"# agent-facts — неделя {w.week}"
    if w.complete:
        title += f" ({_span(w)})"
    else:
        title += f", неполная ({_span(w)}, до {w.end:%H:%M} UTC)"
    out = [
        title,
        "",
        f"Окно: {w.start:%Y-%m-%dT%H:%MZ} → {w.end:%Y-%m-%dT%H:%MZ} (период соли reporter_net, "
        "UTC). Источники: `facts/`, `var/results.jsonl`, `var/observations.sqlite`, "
        "`ops/publish-policy.yaml`. Сгенерировано `ops/digest.py`, без LLM.",
        "",
        "## Факты",
        "",
        f"- всего {f.total} (+{f.added} за неделю): {_counts_line(d)}",
        f"- подтверждено пробами за неделю: {f.confirmed}",
        "- по сервисам: " + (" · ".join(f"{s} {n}" for s, n in f.by_service.items()) or "—"),
        "",
        "## check()",
        "",
    ]
    if c.available:
        dropped = ", ".join(f"{k} {v}" for k, v in c.dropped.items()) or "0"
        top = ", ".join(f"{h} {n}" for h, n in c.top_unregistered) or "—"
        ua = ", ".join(f"{k} {v}" for k, v in c.ua_classes.items()) or "—"
        out += [
            f"- учтено обращений {c.counted}: сохранено {c.stored}, незарегистрированных целей "
            f"{c.unregistered}, отброшено {dropped}",
            f"- сетей-репортёров (/16, /32 IPv6): {c.networks}",
            f"- незарегистрированные цели, top (хосты из списка семени): {top}",
            f"- клиенты сохранённых наблюдений: {ua}",
            "- pre-flight-вызовы на зарегистрированные цели не считаются нигде (спека 03, Q5)",
        ]
    else:
        out.append("- нет var/observations.sqlite (API ещё не принял ни одного наблюдения)")
    out += ["", "## Пробы", ""]
    if p.available:
        split = ", ".join(f"{k} {v}" for k, v in p.outcomes.items()) or "—"
        out += [
            f"- прогонов {p.runs} ({p.probes} проб): {split}",
            f"- нарушений бюджета (два прогона на шаблон ближе бюджета): {p.budget_violations}"
            + (f" — {'; '.join(p.violation_keys)}" if p.violation_keys else ""),
            f"- ключей нет (skipped:no_key): {', '.join(p.missing_keys) or '—'}",
            "- vantage: " + (", ".join(f"{k} {v}" for k, v in p.vantages.items()) or "—"),
            f"- последний прогон: {p.last_run or '—'}",
        ]
        if p.bad_lines:
            out.append(f"- нечитаемых строк в results.jsonl: {p.bad_lines}")
    else:
        out.append("- нет var/results.jsonl")
    out += ["", "## Нужна проба", ""]
    if f.needs_probe:
        card = f" Карточка: {d.open_card}." if d.open_card else ""
        out.append(f"{len(f.needs_probe)} reported-фактов без пробы (агент-часы, без тапа).{card}")
        out += ["", *(f"- {fact_id}" for fact_id in f.needs_probe)]
    else:
        out.append("- 0 reported-фактов без пробы")
    out += ["", "## Публикации", "", f"- {_publications_line(d).removeprefix('публикации: ')}"]
    if d.policy_approved is False:
        out.append("- кнопки «✅ Publish batch» нет, пока Edouard не утвердит "
                   "`ops/publish-policy.yaml` (`approved: true`)")
    return "\n".join(out) + "\n"


# ── the "needs a probe" card ───────────────────────────────────────────────────────────────────


def open_needs_probe_card(state_dir: Path) -> str | None:
    """The newest needs-a-probe card that is not done or dropped."""
    for path in sorted((state_dir / "tasks").glob(f"*-{CARD_SUFFIX}.md"), reverse=True):
        head = path.read_text(encoding="utf-8").split("\n---", 1)[0]
        match = re.search(r"^status:\s*(\S+)", head, flags=re.M)
        if match and match.group(1) not in ("done", "dropped"):
            return path.stem
    return None


def needs_probe_card(d: Digest) -> tuple[str, str] | None:
    ids = d.facts.needs_probe
    if not ids:
        return None
    card_id = f"{d.today.isoformat()}-{CARD_SUFFIX}"
    day = d.today.isoformat()
    text = f"""---
id: {card_id}
project: agent-facts
title: agent-facts — пробы для {len(ids)} reported-фактов без пробы
status: backlog
owner: agent
machine: vps
priority: normal
created: {day}
updated: {day}
---

## Что
{len(ids)} фактов в статусе reported не имеют пробы: кворум наблюдений есть, проверки нет.

## Почему
Недельный дайджест agent-facts ({d.report_id}). Без пробы факт не станет verified и через 30 дней
без обновления кворума уходит со страниц (спека 01); спека 05 — пункт агент-часов, без тапа.

## Что сделать
1. Для каждого факта из «Детали» написать декларативную пробу в probes/<service>/ (спека 04;
   prod — только чтение), сослаться на неё в evidence.probe.
2. Прогнать её в scratch-корне (`agentfacts probe run --all --root <копия>`), не трогая чужие факты.
3. PR в Illouminus/agent-facts по процессу спеки 09; факт, который декларативно не пробуется,
   остаётся reported с пометкой в PR.

## Готово когда
- у каждого факта из списка есть evidence.probe и статус verified:*, либо PR объясняет, почему нет
- `uv run agentfacts validate` и CI зелёные

## Детали
""" + "".join(f"- {fact_id}\n" for fact_id in ids)
    return card_id, text


# ── Telegram gateway ───────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SendResult:
    state: str  # sent | diverted | failed
    detail: str


def _rpc_payload(body: str, content_type: str) -> dict[str, Any]:
    if "text/event-stream" in content_type:
        for line in body.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
        raise ValueError("no data line in the event stream")
    return json.loads(body)


def send_telegram(text: str, endpoint: str, routine: str, timeout: float = 20.0) -> SendResult:
    """One `tools/call send_telegram` on the gateway's MCP endpoint (stateless, no session)."""
    request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": "send_telegram",
                          "arguments": {"text": text, "class": "digest", "markdown": False}}}
    try:
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            response = client.post(endpoint, json=request, headers={
                "Accept": "application/json, text/event-stream", "X-Routine": routine})
        response.raise_for_status()
        payload = _rpc_payload(response.text, response.headers.get("content-type", ""))
    except (httpx.HTTPError, ValueError) as exc:
        return SendResult("failed", f"gateway {endpoint}: {exc}")
    if "error" in payload:
        return SendResult("failed", json.dumps(payload["error"], ensure_ascii=False))
    result = payload.get("result") or {}
    said = " ".join(c.get("text", "") for c in result.get("content") or ()
                    if c.get("type") == "text")
    if result.get("isError"):
        return SendResult("failed", said)
    if said.startswith("Telegram message sent"):
        return SendResult("sent", said)
    if said.startswith("Not sent to Telegram"):
        return SendResult("diverted", said)
    return SendResult("failed", f"unexpected reply: {said}")


# ── main ───────────────────────────────────────────────────────────────────────────────────────


def _write_if_changed(path: Path, text: str) -> bool:
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def _journal(state_dir: Path, d: Digest, reports_url: str) -> bool:
    path = state_dir / state_journal.PROJECT_FILE
    text = path.read_text(encoding="utf-8")
    f = d.facts
    title = f"{d.today.isoformat()} — дайджест, неделя {d.window.week}"
    if not d.window.complete:
        title += " (неполная)"
    bullets = [
        f"- факты {f.total} (+{f.added}): {_counts_line(d)}; {_probes_line(d)}; "
        f"{_needs_probe_line(d)}; {_publications_line(d)}.",
        f"- отчёт: [{d.report_id}]({reports_url.rstrip('/')}/{d.report_id})",
    ]
    # a re-run on the same day replaces its own entry, so journal and report agree
    updated = state_journal.insert_entry(
        state_journal.remove_entry(text, f"/{d.report_id})"), title, bullets)
    if updated == text:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def _args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="agent-facts weekly digest (spec 08)")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--state-dir", type=Path, default=state_journal.DEFAULT_STATE)
    parser.add_argument("--results", type=Path, default=None)
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--policy", type=Path, default=None)
    parser.add_argument("--now", default=None, help="ISO time with offset (default: now)")
    parser.add_argument("--current", action="store_true",
                        help="the running salt period up to now instead of the last complete one")
    parser.add_argument("--dry-run", action="store_true", help="print only")
    parser.add_argument("--no-send", action="store_true", help="state only, no Telegram")
    parser.add_argument("--gateway", default=GATEWAY)
    parser.add_argument("--reports-url", default=REPORTS_URL)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _args(argv)
        now = _moment(args.now) if args.now else datetime.now(UTC)
        if now is None:
            raise ValueError(f"--now needs an ISO time with an offset, got {args.now!r}")
    except SystemExit as exc:
        return 2 if exc.code else 0
    except ValueError as exc:
        print(f"digest: {exc}", file=sys.stderr)
        return 2
    state_dir: Path = args.state_dir
    open_card = open_needs_probe_card(state_dir)  # read-only, also in a dry run
    d = build(args.root, now, args.current, args.results, args.db, args.policy, open_card)
    card = needs_probe_card(d) if open_card is None else None
    if card:
        d = replace(d, open_card=card[0])
    report, ping = render_report(d), render_ping(d, args.reports_url)
    if args.dry_run:
        print(report)
        print("---- ping ----")
        print(ping)
        if card:
            print(f"---- would create card {card[0]} ----")
        return 0

    changed: list[str] = []
    if _write_if_changed(state_dir / "reviews" / f"{d.report_id}.md", report):
        changed.append(f"reviews/{d.report_id}.md")
    if card and _write_if_changed(state_dir / "tasks" / f"{card[0]}.md", card[1]):
        changed.append(f"tasks/{card[0]}.md")
    try:
        if _journal(state_dir, d, args.reports_url):
            changed.append(state_journal.PROJECT_FILE)
    except (OSError, state_journal.JournalError) as exc:
        print(f"digest: journal not written: {exc}", file=sys.stderr)
        return 1
    if changed:
        label = f"неделя {d.window.week}" + ("" if d.window.complete else " (неполная)")
        rc = state_journal.commit(state_dir, f"agent-facts: дайджест, {label}", changed)
        if rc != 0:
            print(f"digest: state-commit exited {rc}; files written, not committed: {changed}",
                  file=sys.stderr)
            return 1
        print(f"digest: committed {', '.join(changed)}")
    else:
        print("digest: state already up to date")
    if args.no_send:
        return 0
    sent = send_telegram(ping, args.gateway, ROUTINE)
    print(f"digest: telegram {sent.state}: {sent.detail}",
          file=sys.stdout if sent.state == "sent" else sys.stderr)
    return 1 if sent.state == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
