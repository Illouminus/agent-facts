"""Adoption counting (D-092): every answered check() call lands in `traffic`, one row per network
per salt period, flagged own/external at request time; `apifacts stats adoption` prints the line."""

import sqlite3
from datetime import UTC, date, datetime

from api_fixtures import STRIPE_PI
from typer.testing import CliRunner

from apifacts.api.adoption import period_of, read_adoption
from apifacts.api.store import Store
from apifacts.cli import app as cli

EXTERNAL = ("8.8.8.8", 40000)
EXTERNAL_SAME_16 = ("8.8.200.1", 40000)
EXTERNAL_OTHER = ("1.1.1.1", 40000)
WEDNESDAY = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)  # salt period 2026-10-19
PERIOD = date(2026, 10, 19)
PREFLIGHT = {"target": {"method": "POST", "url": STRIPE_PI}}
ERROR = PREFLIGHT | {"error": {"status": 400, "body_excerpt":
                               '{"error": {"message": "No such customer: cus_1"}}'}}


def traffic(db_path) -> list[tuple]:
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            "SELECT period, own, calls, stored FROM traffic ORDER BY own, calls"
        ).fetchall()


def test_preflight_and_reported_calls_count_per_network(make_client, db_path):
    a = make_client(EXTERNAL, utcnow=lambda: WEDNESDAY)
    assert a.post("/v0/check", json=PREFLIGHT).status_code == 200
    assert a.post("/v0/check", json=ERROR).json()["unknown"]["stored_as_observation"]
    b = make_client(EXTERNAL_SAME_16, utcnow=lambda: WEDNESDAY)  # same /16: same client
    b.post("/v0/check", json=PREFLIGHT)
    make_client(EXTERNAL_OTHER, utcnow=lambda: WEDNESDAY).post("/v0/check", json=PREFLIGHT)
    assert traffic(db_path) == [("2026-10-19", 0, 1, 0), ("2026-10-19", 0, 3, 1)]
    found = read_adoption(db_path, PERIOD)
    assert found.line() == "external_clients=2 calls=4 reported_external=1"


def test_loopback_private_and_configured_nets_are_own(make_client, db_path):
    for peer in (("127.0.0.1", 1), ("10.1.2.3", 1)):
        make_client(peer, utcnow=lambda: WEDNESDAY).post("/v0/check", json=PREFLIGHT)
    make_client(EXTERNAL, own_nets=("8.8.0.0/16",),
                utcnow=lambda: WEDNESDAY).post("/v0/check", json=ERROR)
    found = read_adoption(db_path, PERIOD)
    assert found.line() == "external_clients=0 calls=0 reported_external=0"
    assert found.own_calls == 3


def test_own_nets_come_from_env_and_the_file_next_to_the_db(make_client, db_path, monkeypatch):
    db_path.parent.joinpath("own-nets.txt").write_text("# illouminus\n8.8.8.8/32  # vps\n\n")
    monkeypatch.setenv("APIFACTS_OWN_NETS", "1.1.0.0/16")
    for peer in (EXTERNAL, EXTERNAL_OTHER, ("9.9.9.9", 1)):
        make_client(peer, utcnow=lambda: WEDNESDAY).post("/v0/check", json=PREFLIGHT)
    assert read_adoption(db_path, PERIOD).external_clients == 1


def test_a_rejected_request_is_not_a_call(make_client, db_path):
    client = make_client(EXTERNAL, utcnow=lambda: WEDNESDAY)
    no_method = {"target": {"url": STRIPE_PI}}
    assert client.post("/v0/check", json=no_method).status_code == 400
    assert traffic(db_path) == []


def test_traffic_keeps_last_period_for_the_monday_digest(tmp_path):
    store = Store(tmp_path / "o.sqlite")
    for period in ("2026-10-12", "2026-10-19"):
        store.period_salt(period)
        store.count_call(period, "n", own=False, stored=False)
    store.period_salt("2026-10-26")  # rotation: 10-19 is read on Monday 10-26, 10-12 goes
    with store._lock:
        left = store.connection.execute("SELECT period FROM traffic").fetchall()
    assert left == [("2026-10-19",)]


def test_period_of_is_the_last_complete_salt_period():
    monday = datetime(2026, 10, 26, 6, 0, tzinfo=UTC)
    assert period_of(monday) == PERIOD
    assert period_of(monday, current=True) == date(2026, 10, 26)


def test_reader_never_creates_the_db(tmp_path):
    found = read_adoption(tmp_path / "none.sqlite", PERIOD)
    assert not found.available and found.calls == 0
    assert not (tmp_path / "none.sqlite").exists()


def test_cli_prints_one_line(tmp_path):
    db = tmp_path / "o.sqlite"
    store = Store(db)
    store.count_call("2026-10-19", "n1", own=False, stored=True)
    store.count_call("2026-10-19", "n1", own=False, stored=False)
    store.count_call("2026-10-19", "n2", own=True, stored=False)
    store.close()
    runner = CliRunner()
    result = runner.invoke(cli, ["stats", "adoption", "--db", str(db),
                                 "--now", "2026-10-26T08:00:00+01:00"])
    assert result.exit_code == 0, result.output
    assert result.stdout == "external_clients=1 calls=2 reported_external=1\n"
    missing = runner.invoke(cli, ["stats", "adoption", "--db", str(tmp_path / "x.sqlite")])
    assert missing.exit_code == 1
    assert runner.invoke(cli, ["stats", "adoption", "--now", "yesterday"]).exit_code == 2
