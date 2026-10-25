import shutil
from pathlib import Path

import pytest

from apifacts.client.offline import PACKAGED, Snapshot

VALID = Path(__file__).parent.parent / "fixtures" / "valid"
FACT_ID = "af:stripe:idempotency-key-reuse-different-params"


@pytest.fixture
def snapshot_dir(tmp_path):
    (tmp_path / "services").mkdir()
    (tmp_path / "facts" / "stripe").mkdir(parents=True)
    shutil.copy(VALID / "service-stripe.yaml", tmp_path / "services" / "stripe.yaml")
    shutil.copy(
        VALID / "fact-idempotency-key-reuse-different-params.yaml",
        tmp_path / "facts" / "stripe" / "idempotency-key-reuse-different-params.yaml",
    )
    (tmp_path / "facts" / "stripe" / "broken.yaml").write_text("key: [unclosed")
    return tmp_path


def check(snapshot, method, url, status=None):
    payload = {"target": {"method": method, "url": url}}
    if status is not None:
        payload["error"] = {"status": status}
    return snapshot.check(payload)


def test_fact_found_by_template_and_status(snapshot_dir):
    snapshot = Snapshot.load(snapshot_dir)
    assert snapshot.hosts == frozenset({"api.stripe.com"})
    answer = check(snapshot, "POST", "https://api.stripe.com/v1/payment_intents", 400)
    assert answer["service"] == "stripe"
    assert answer["matched_template"] == {"method": "POST", "path": "/v1/payment_intents"}
    (fact,) = answer["facts"]
    assert fact["id"] == FACT_ID
    assert fact["evidence"]["first_seen"] == "2026-10-22T09:14:00Z"  # timestamps stay strings
    assert fact["fixes_rendered"] == [
        "Set parameter Idempotency-Key to new UUID per distinct request"
    ]
    assert answer["registry"]["license"] == "CC-BY-4.0"


def test_other_status_or_template_gives_no_fact(snapshot_dir):
    snapshot = Snapshot.load(snapshot_dir)
    assert check(snapshot, "POST", "https://api.stripe.com/v1/payment_intents", 500)["facts"] == []
    answer = check(snapshot, "GET", "https://api.stripe.com/v1/customers/cus_1", 400)
    assert answer["matched_template"] == {"method": "GET", "path": "/v1/customers/{id}"}
    assert answer["facts"] == []
    assert answer["unknown"]["reason"] == "no_fact_for_signal"


def test_unknown_host_is_unregistered(snapshot_dir):
    answer = check(Snapshot.load(snapshot_dir), "GET", "https://api.github.com/user", 401)
    assert answer["facts"] == []
    assert answer["unknown"] == {"reason": "unregistered_target", "stored_as_observation": False}


def test_rate_limit_facts_answer_for_any_template(snapshot_dir):
    path = snapshot_dir / "facts" / "stripe" / "idempotency-key-reuse-different-params.yaml"
    path.write_text(path.read_text().replace("kind: error_meaning", "kind: rate_limit"))
    answer = check(
        Snapshot.load(snapshot_dir), "GET", "https://api.stripe.com/v1/unregistered", 429
    )
    assert [f["id"] for f in answer["facts"]] == [FACT_ID]


def test_retracted_facts_are_never_returned(snapshot_dir):
    path = snapshot_dir / "facts" / "stripe" / "idempotency-key-reuse-different-params.yaml"
    path.write_text(path.read_text().replace("status: verified:server:prod", "status: retracted"))
    answer = check(
        Snapshot.load(snapshot_dir), "POST", "https://api.stripe.com/v1/payment_intents", 400
    )
    assert answer["facts"] == []


def test_packaged_snapshot_is_empty():
    assert PACKAGED.is_dir()
    snapshot = Snapshot.load()
    assert snapshot.hosts == frozenset()
    assert check(snapshot, "GET", "https://api.stripe.com/v1/x", 400)["facts"] == []


def test_missing_snapshot_dir_is_empty(tmp_path):
    assert Snapshot.load(tmp_path / "nowhere").hosts == frozenset()
