"""What a fact says, without the evidence counters that the probe runner and the quorum move.

`evidence.last_confirmed`, `confirmations`, `stale_counter`, `vantages` and `observations` change
with every confirmation; everything else (status, claim, history, the probe it cites, …) is the
fact's substance. A substance change is news: the bot publishes it at once and the deploy journal
records it. A counter-only change waits for the daily evidence refresh (incident 2026-10-20..24:
counters rewritten every 15 minutes became 62 bot PRs, 137 CI runs and 40 journal lines).
"""

from collections.abc import Mapping
from typing import Any

from agentfacts.schema.yamlio import plain

VOLATILE_EVIDENCE = frozenset(
    {"last_confirmed", "confirmations", "stale_counter", "vantages", "observations"}
)


def substance(doc: Mapping[str, Any]) -> dict[str, Any]:
    """A plain copy of the fact document with the volatile evidence keys removed."""
    data = plain(doc)
    evidence = data.get("evidence") or {}
    return {**data, "evidence": {k: v for k, v in evidence.items() if k not in VOLATILE_EVIDENCE}}
