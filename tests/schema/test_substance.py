"""What a fact says, minus the counters the runner and the quorum keep moving (incident 24.10)."""

from agentfacts.schema.substance import VOLATILE_EVIDENCE, substance

FACT = {
    "id": "af:acme:x",
    "status": "verified:server:prod",
    "evidence": {"probe": "af:acme:probe:x", "first_seen": "2026-10-01T09:00:00Z",
                 "confirmations": 1, "last_confirmed": "2026-10-01T09:00:00Z",
                 "stale_counter": 0, "vantages": ["illouminus"], "observations": 0},
}


def test_counters_are_not_substance():
    moved = {**FACT, "evidence": {**FACT["evidence"], "confirmations": 9,
                                  "last_confirmed": "2026-10-24T01:00:00Z", "stale_counter": 2,
                                  "vantages": ["illouminus", "freebox"], "observations": 4}}
    assert substance(moved) == substance(FACT)
    assert VOLATILE_EVIDENCE == {"last_confirmed", "confirmations", "stale_counter", "vantages",
                                 "observations"}


def test_status_probe_and_claim_are_substance():
    assert substance({**FACT, "status": "stale"}) != substance(FACT)
    assert substance({**FACT, "evidence": {**FACT["evidence"], "probe": "af:acme:probe:y"}}) != \
        substance(FACT)
    assert substance({**FACT, "claim": "new"}) != substance(FACT)


def test_missing_evidence_is_fine():
    assert substance({"id": "x"}) == {"id": "x", "evidence": {}}
