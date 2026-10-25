"""From a group that met quorum to a fact file: is it already a fact (refresh), which probe can
reproduce it, and the `reported` draft itself (spec 05, statuses of spec 01)."""

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from apifacts.api.facts_index import fact_hashes
from apifacts.api.normalize import normalize
from apifacts.probe.evidence import Stamp, dump_text, load_fact, save_fact
from apifacts.probe.http import matching_template
from apifacts.probe.loader import LoadedFact, LoadedProbe
from apifacts.probe.templating import rfc3339
from apifacts.quorum.group import Group
from apifacts.quorum.rules import claim_for, infer_kind
from apifacts.schema.models import (
    AssertBodyContains,
    AssertJsonPath,
    AssertStatus,
    Fact,
    HttpStep,
    Service,
    Status,
)
from apifacts.schema.yamlio import plain

MIN_ASSERTED_STRING = 4  # a normalized assertion shorter than this ("###") proves nothing


def covering_fact(group: Group, facts: Iterable[LoadedFact]) -> LoadedFact | None:
    """The fact that already answers this group the way check() would: same service and
    endpoint, and the same error hash (or normalized string); for a status-only group, the same
    status. A live fact wins over a retracted one (a retracted fact still blocks a new draft)."""
    found = []
    for loaded in facts:
        fact = loaded.fact
        target, signal = fact.target, fact.signal
        if fact.service != group.service:
            continue
        if (target.method, target.path_template) != (group.method, group.path_template):
            continue
        if group.error_hash is not None:
            same = group.error_hash in fact_hashes(fact) or (
                signal is not None and signal.normalized == group.normalized
            )
        else:
            same = signal is not None and group.status is not None and signal.status == group.status
        if same:
            found.append(loaded)
    found.sort(key=lambda f: (f.fact.status is Status.retracted, f.fact.id))
    return found[0] if found else None


def _asserted_string(value: Any) -> str | None:
    text = normalize(str(value)) if value is not None else ""
    return text if len(text) >= MIN_ASSERTED_STRING else None


def _asserts_signal(assertion: Any, group: Group) -> bool:
    if isinstance(assertion, AssertStatus):
        return group.status is not None and assertion.status == group.status
    if not group.normalized:
        return False
    if isinstance(assertion, AssertJsonPath):
        values = (assertion.equals, assertion.contains)
    elif isinstance(assertion, AssertBodyContains):
        values = (assertion.body_contains,)
    else:
        return False
    return any((s := _asserted_string(v)) is not None and s in group.normalized for v in values)


def matching_probe(
    group: Group, probes: Iterable[LoadedProbe], service: Service, env: str | None
) -> LoadedProbe | None:
    """Spec 05: a probe of the service with a step on the group's endpoint whose assertions on
    that step include the signal (status, or a string the normalized error contains). When the
    reporters' env is known the probe must run in it, else it could never confirm the fact."""
    for loaded in sorted(probes, key=lambda p: p.probe.id):
        probe = loaded.probe
        if probe.service != group.service or (env is not None and probe.env != env):
            continue
        for number, step in enumerate(probe.steps, 1):
            if not isinstance(step, HttpStep) or step.method != group.method:
                continue
            if matching_template(service, step.method, step.path) != group.path_template:
                continue
            if any(a.step == number and _asserts_signal(a, group) for a in probe.assertions):
                return loaded
    return None


def draft_document(
    group: Group,
    slug: str,
    *,
    env: str,
    account_state: str,
    probe_id: str | None,
    now: datetime,
) -> dict[str, Any]:
    """A `reported` fact from quorum: kind and claim by rule, no fix known yet."""
    status = group.status
    kind = infer_kind(status, group.normalized)
    signal: dict[str, Any] = {}
    if status is not None:
        signal["status"] = status
    if group.normalized:
        signal["normalized"] = group.normalized
    dimensions = {"env": env} | ({"account_state": account_state} if account_state != "any" else {})
    evidence: dict[str, Any] = {"probe": probe_id} if probe_id else {}
    evidence |= {"first_seen": Stamp(group.first_seen), "observations": len(group.nets)}
    today = Stamp(now.astimezone(UTC).date().isoformat())
    return {
        "id": f"af:{group.service}:{slug}",
        "service": group.service,
        "kind": kind.value,
        "target": {"surface": "http", "method": group.method, "path_template": group.path_template},
        "signal": signal,
        "claim": claim_for(kind, group.method, group.path_template, status, group.normalized),
        "dimensions": dimensions,
        "fixes": [{"action": "none_known", "reason_kind": "investigating"}],
        "status": Status.reported.value,
        "evidence": evidence,
        "provenance": {
            "source": "observation_quorum",
            "author": "bot",
            "created": today,
            "history": [{"date": today, "change": "created", "by": "bot"}],
        },
    }


def write_draft(path: Path, document: dict[str, Any]) -> None:
    """Write a new fact file (never over an existing one); ValueError if it is not a fact."""
    Fact.model_validate(plain(document))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as fh:
        fh.write(dump_text(document))


def refresh_fact(path: Path, group: Group, now: datetime) -> bool:
    """Spec 05 "same group already a fact": `evidence.observations` rises to the networks seen
    this period (never falls: another week's networks are other hashes); a `reported` fact also
    gets `last_confirmed`, once a day, which keeps it on the pages (01: 30 days without quorum
    refresh → removed). Every other byte stays. True when the file changed."""
    doc = load_fact(path)
    fact = Fact.model_validate(plain(doc))
    if fact.status is Status.retracted:
        return False
    evidence, changed = doc["evidence"], False
    if (evidence.get("observations") or 0) < len(group.nets):
        evidence["observations"] = len(group.nets)
        changed = True
    now = now.astimezone(UTC)
    last = evidence.get("last_confirmed")
    if fact.status is Status.reported and (last is None or str(last)[:10] < now.date().isoformat()):
        evidence["last_confirmed"] = Stamp(rfc3339(now))
        changed = True
    if changed:
        save_fact(path, doc)
    return changed
