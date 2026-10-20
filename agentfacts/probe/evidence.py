"""Apply a probe outcome to a fact that cites the probe (spec 04 Execution, spec 01 status rules).

- pass → `last_confirmed`, `confirmations += 1`, `stale_counter = 0`, vantage added; a `stale` fact
  gets back the `previous_status` of its last `stale` history entry (or `verified:server:<env>`).
- fail → `stale_counter += 1`; at ≥ 3 a `verified:*` fact becomes `stale`, the old status kept in
  history. `official`, `reported` only count; `retracted` is never touched.
- A probe in another `env` or `account_state` than the fact (probe without `account_state` = `any`)
  never touches it: `other_dimension` (01: it would be a sibling dimension row, never a refutation).

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

from agentfacts.probe.templating import rfc3339
from agentfacts.schema.models import VERIFIED_STATUSES, Fact, Probe, Status
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


def _confirm(doc: CommentedMap, probe: Probe, vantage: str, now: datetime) -> str:
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


def apply_outcome(path: Path, probe: Probe, outcome: Outcome, vantage: str, now: datetime) -> str:
    """Update one fact file; returns the change: confirmed, restored, failed, stale,
    other_dimension, untouched or invalid (file left as is)."""
    try:
        doc = load_fact(path)
        fact = Fact.model_validate(plain(doc))
    except (OSError, YAMLError, ValidationError):
        return "invalid"
    if not _same_dimension(fact, probe):
        return "other_dimension"
    if fact.status is Status.retracted:
        return "untouched"
    now = now.astimezone(UTC)
    change = _confirm(doc, probe, vantage, now) if outcome == "pass" else _fail(doc, now)
    try:
        Fact.model_validate(plain(doc))
    except ValidationError:
        return "invalid"
    _write_atomic(path, dump_text(doc))
    return change
