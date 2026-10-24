"""Apply a probe outcome to a fact that cites the probe (spec 04 Execution, spec 01 status rules).

- pass → `last_confirmed`, `confirmations += 1`, `stale_counter = 0`, vantage added; a `stale` fact
  gets back the `previous_status` of its last `stale` history entry (or `verified:server:<env>`);
  a `reported` fact (quorum draft citing this probe) becomes `verified:server:<env>` (spec 05).
- fail → `stale_counter += 1`; at ≥ 3 a `verified:*` fact becomes `stale`, the old status kept in
  history. `official`, `reported` only count; `retracted` is never touched.
- A probe in another `env` or `account_state` than the fact (probe without `account_state` = `any`)
  never touches it: `other_dimension` (01: it would be a sibling dimension row, never a refutation).

With a ledger (the runner always passes one) the counters stay out of the YAML: the file is
written only on a status change (verified, stale, restored) or a first confirmation from a new
vantage, carrying the pending counters along; every other outcome goes to the ledger, and the
daily `probe run --refresh-evidence` flushes it (`refresh_from_ledger`). Incident 2026-10-20..24:
counters rewritten every 15 minutes became 62 bot PRs, 137 CI runs and 62 deploys.

Files go through a ruamel round-trip that leaves untouched lines byte-identical (comments, quotes,
plain timestamps); the result is re-validated as a `Fact` before an atomic replace.
"""

import io
import os
import stat
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.constructor import RoundTripConstructor
from ruamel.yaml.error import YAMLError
from ruamel.yaml.representer import RoundTripRepresenter

from agentfacts.probe.ledger import EvidenceLedger, Pending
from agentfacts.probe.templating import rfc3339
from agentfacts.schema.models import VERIFIED_STATUSES, Fact, HttpStep, Probe, Status
from agentfacts.schema.registry import match_template
from agentfacts.schema.yamlio import plain

Outcome = Literal["pass", "fail"]
STALE_AFTER = 3
_TIMESTAMP = "tag:yaml.org,2002:timestamp"


class Stamp(str):
    """A YAML timestamp kept as its source text: read as a string, written back plain."""


class _Constructor(RoundTripConstructor):
    pass


class _Representer(RoundTripRepresenter):
    pass


_Constructor.add_constructor(_TIMESTAMP, lambda self, node: Stamp(self.construct_scalar(node)))
_Representer.add_representer(Stamp, lambda self, value: self.represent_scalar(_TIMESTAMP, value))


def _yaml() -> YAML:
    yaml = YAML(typ="rt")
    yaml.Constructor = _Constructor
    yaml.Representer = _Representer
    yaml.preserve_quotes = True
    yaml.width = 4096
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def load_fact(path: Path) -> Any:
    return _yaml().load(path.read_text(encoding="utf-8"))


def dump_text(doc: Any) -> str:
    out = io.StringIO()
    _yaml().dump(doc, out)
    return out.getvalue()


def _write_atomic(path: Path, text: str) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)  # mkstemp makes 0600; keep what readers rely on
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _history(doc: CommentedMap) -> CommentedSeq:
    provenance = doc["provenance"]
    if provenance.get("history") is None:
        provenance["history"] = CommentedSeq()
    return provenance["history"]


def _previous_status(doc: CommentedMap, probe: Probe) -> str:
    for entry in reversed(_history(doc)):
        if entry.get("change") == "stale" and entry.get("previous_status"):
            return str(entry["previous_status"])
    return f"verified:server:{probe.env}"


def _same_dimension(fact: Fact, probe: Probe) -> bool:
    return (fact.dimensions.env == probe.env
            and fact.dimensions.account_state == (probe.account_state or "any"))


def _reproduces(fact: Fact, probe: Probe) -> bool:
    """The probe hits the fact's own endpoint: same service, a step with the fact's method on an
    instance of its path template. Only then may a pass promote a `reported` fact."""
    target = fact.target
    return fact.service == probe.service and any(
        isinstance(step, HttpStep)
        and step.method == target.method
        and target.path_template is not None
        and match_template(step.path, target.path_template)
        for step in probe.steps
    )


def _confirm(
    doc: CommentedMap, fact: Fact, probe: Probe, vantage: str, now: datetime
) -> str:
    evidence = doc["evidence"]
    evidence["last_confirmed"] = Stamp(rfc3339(now))
    evidence["confirmations"] = (evidence.get("confirmations") or 0) + 1
    evidence["stale_counter"] = 0
    vantages = evidence.get("vantages")
    if vantages is None:
        vantages = CommentedSeq()
        vantages.fa.set_flow_style()
        evidence["vantages"] = vantages
    if vantage not in vantages:
        vantages.append(vantage)
    if doc["status"] == Status.reported and _reproduces(fact, probe):
        doc["status"] = f"verified:server:{probe.env}"
        _history(doc).append({
            "date": Stamp(now.date().isoformat()),
            "change": "verified",
            "by": "bot",
            "previous_status": Status.reported.value,
        })
        return "verified"
    if doc["status"] != Status.stale:
        return "confirmed"
    doc["status"] = _previous_status(doc, probe)
    _history(doc).append({"date": Stamp(now.date().isoformat()), "change": "restored", "by": "bot"})
    return "restored"


def _fail(doc: CommentedMap, now: datetime) -> str:
    evidence = doc["evidence"]
    counter = (evidence.get("stale_counter") or 0) + 1
    evidence["stale_counter"] = counter
    status = doc["status"]
    if counter < STALE_AFTER or status not in VERIFIED_STATUSES:
        return "failed"
    doc["status"] = Status.stale.value
    _history(doc).append({
        "date": Stamp(now.date().isoformat()),
        "change": "stale",
        "by": "bot",
        "previous_status": str(status),
    })
    return "stale"


def save_fact(path: Path, doc: Any) -> None:
    """Re-validate a round-tripped fact document and replace the file atomically (ValueError if
    the document is not a valid fact; the file is left as is)."""
    try:
        Fact.model_validate(plain(doc))
    except ValidationError as exc:
        raise ValueError(f"{path}: not a valid fact: {exc.error_count()} errors") from exc
    _write_atomic(path, dump_text(doc))


def _overlay(evidence: CommentedMap, pending: Pending | None) -> None:
    """Put the ledger's counters onto the YAML's evidence (in memory)."""
    if pending is None:
        return
    if pending.confirmations:
        evidence["confirmations"] = (evidence.get("confirmations") or 0) + pending.confirmations
    if pending.last_confirmed is not None:
        evidence["last_confirmed"] = Stamp(pending.last_confirmed)
    if pending.stale_counter is not None:
        evidence["stale_counter"] = pending.stale_counter


def _pending(evidence: CommentedMap, written_confirmations: int) -> Pending:
    """The counters of `evidence` that the YAML (with `written_confirmations`) does not hold."""
    last = evidence.get("last_confirmed")
    return Pending(
        (evidence.get("confirmations") or 0) - written_confirmations,
        None if last is None else str(last),
        evidence.get("stale_counter"),
    )


def _load(path: Path) -> tuple[Any, Fact] | None:
    try:
        doc = load_fact(path)
        return doc, Fact.model_validate(plain(doc))
    except (OSError, YAMLError, ValidationError):
        return None


def apply_outcome(
    path: Path,
    probe: Probe,
    outcome: Outcome,
    vantage: str,
    now: datetime,
    *,
    ledger: EvidenceLedger | None = None,
) -> str:
    """Update one fact; returns the change: confirmed, verified, restored, failed, stale,
    other_dimension, untouched or invalid (file left as is). Without `ledger` every outcome is
    written to the YAML; with it, only status changes and a new vantage are (module doc)."""
    if (loaded := _load(path)) is None:
        return "invalid"
    doc, fact = loaded
    if not _same_dimension(fact, probe):
        return "other_dimension"
    if fact.status is Status.retracted:
        return "untouched"
    now = now.astimezone(UTC)
    evidence = doc["evidence"]
    written_confirmations = evidence.get("confirmations") or 0
    new_vantage = vantage not in (evidence.get("vantages") or [])
    if ledger is not None:
        _overlay(evidence, ledger.get(fact.id))
    if outcome == "pass":
        change = _confirm(doc, fact, probe, vantage, now)
    else:
        change = _fail(doc, now)
    quiet = change in ("confirmed", "failed") and not (outcome == "pass" and new_vantage)
    if ledger is not None and quiet:
        ledger.put(fact.id, _pending(evidence, written_confirmations))
        return change
    try:
        save_fact(path, doc)
    except ValueError:
        return "invalid"
    if ledger is not None:
        ledger.clear(fact.id)
    return change


def refresh_from_ledger(path: Path, ledger: EvidenceLedger) -> str:
    """Daily refresh of one fact: write its pending counters into the YAML and clear them.
    Returns refreshed, unchanged (counters equal the YAML's), untouched (nothing pending, or a
    retracted fact whose entry is dropped) or invalid (file and entry left as they are)."""
    if (loaded := _load(path)) is None:
        return "invalid"
    doc, fact = loaded
    pending = ledger.get(fact.id)
    if pending is None:
        return "untouched"
    if fact.status is Status.retracted:
        ledger.clear(fact.id)
        return "untouched"
    before = plain(doc)
    _overlay(doc["evidence"], pending)
    if plain(doc) == before:
        ledger.clear(fact.id)
        return "unchanged"
    try:
        save_fact(path, doc)
    except ValueError:
        return "invalid"
    ledger.clear(fact.id)
    return "refreshed"
