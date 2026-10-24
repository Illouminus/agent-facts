"""Evidence ledger: confirmation counters kept by the runner between two YAML writes."""

from agentfacts.probe.ledger import EvidenceLedger, Pending


def test_put_get_clear(tmp_path):
    with EvidenceLedger(tmp_path / "l.sqlite") as ledger:
        assert ledger.get("af:a:x") is None
        ledger.put("af:a:x", Pending(3, "2026-10-24T01:00:00Z", 0))
        ledger.put("af:a:y", Pending(0, None, 2))
        assert ledger.get("af:a:x") == Pending(3, "2026-10-24T01:00:00Z", 0)
        ledger.put("af:a:x", Pending(4, "2026-10-24T01:15:00Z", 0))
        assert ledger.items() == [("af:a:x", Pending(4, "2026-10-24T01:15:00Z", 0)),
                                  ("af:a:y", Pending(0, None, 2))]
        ledger.clear("af:a:x")
        assert ledger.get("af:a:x") is None
    with EvidenceLedger(tmp_path / "l.sqlite") as again:  # survives the process
        assert again.get("af:a:y") == Pending(0, None, 2)


def test_read_only_never_creates_the_file(tmp_path):
    path = tmp_path / "var" / "l.sqlite"
    with EvidenceLedger(path, read_only=True) as ledger:
        assert ledger.get("af:a:x") is None and ledger.items() == []
        ledger.put("af:a:x", Pending(1))
        ledger.clear("af:a:x")
    assert not path.parent.exists()


def test_read_only_reads_an_existing_file(tmp_path):
    path = tmp_path / "l.sqlite"
    with EvidenceLedger(path) as ledger:
        ledger.put("af:a:x", Pending(2, "2026-10-24T01:00:00Z", 0))
    with EvidenceLedger(path, read_only=True) as ledger:
        assert ledger.items() == [("af:a:x", Pending(2, "2026-10-24T01:00:00Z", 0))]
        ledger.put("af:a:x", Pending(9))
    with EvidenceLedger(path) as ledger:
        assert ledger.get("af:a:x").confirmations == 2
