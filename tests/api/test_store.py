"""sqlite store: observation rows exactly as spec 01, weekly salt, anonymous counters."""

import sqlite3

import pytest

from apifacts.api.store import Drop, Store
from apifacts.schema import load_schema

ROW = {
    "received_at": "2026-10-20T10:00:00Z",
    "service": "stripe",
    "method": "POST",
    "path_template": "/v1/payment_intents",
    "status": 400,
    "error_hash": "a" * 64,
    "normalized_error": "keys for idempotent requests",
    "reporter_net": "b" * 64,
    "reporter_ua_class": "pytest-plugin",
    "sdk_package": "stripe",
    "sdk_version": "12.1.0",
    "env_guess": "prod",
    "vantage_country": None,
}
DAY = "2026-10-20"
PERIOD = "2026-10-19"  # the Monday of DAY's week
NEXT = "2026-10-26"


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "obs.sqlite")
    yield s
    s.close()


def _columns(store: Store, table: str) -> list[str]:
    return [r[1] for r in store.connection.execute(f"PRAGMA table_info({table})")]


def test_observation_columns_are_the_observation_schema(store):
    assert _columns(store, "observations") == list(load_schema("observation")["properties"])


def test_add_observation_assigns_ids_and_round_trips(store):
    assert store.add_observation(ROW) == 1
    assert store.add_observation(ROW) == 2
    assert store.count() == 2
    row = store.connection.execute("SELECT * FROM observations WHERE id = 2").fetchone()
    assert dict(zip(_columns(store, "observations"), row, strict=True)) == {"id": 2, **ROW}


@pytest.mark.parametrize(
    "bad",
    [
        {"normalized_error": "x" * 513},
        {"reporter_ua_class": "browser"},
        {"error_hash": "not-a-hash"},
        {"reporter_net": "203.0.0.0/16"},  # a raw network never reaches the table
        {"method": "BREW"},
        {"extra": "field"},
    ],
)
def test_invalid_rows_are_refused_before_any_write(store, bad):
    with pytest.raises(ValueError):
        store.add_observation({**ROW, **bad})
    assert store.count() == 0


def test_daily_cap_drops_beyond_the_limit(store):
    assert store.add_observation(ROW, daily_cap=2) == 1
    assert store.add_observation(ROW, daily_cap=2) == 2
    assert store.add_observation(ROW, daily_cap=2) == Drop.daily_cap
    other_net = {**ROW, "reporter_net": "c" * 64}
    assert store.add_observation(other_net, daily_cap=2) == 3
    next_day = {**ROW, "received_at": "2026-10-21T00:00:00Z"}
    assert store.add_observation(next_day, daily_cap=2) == 4
    assert store.count() == 4


def test_salt_is_stable_within_a_period_and_rotates_with_the_next(store):
    first = store.period_salt(PERIOD)
    assert len(first) == 32
    assert store.period_salt(PERIOD) == first
    second = store.period_salt(NEXT)
    assert second != first
    periods = [r[0] for r in store.connection.execute("SELECT day FROM salts")]
    assert periods == [NEXT]  # last week's salt is gone: its hashes cannot be recomputed


def test_late_request_for_last_period_keeps_this_periods_salt(store):
    current = store.period_salt(NEXT)
    store.period_salt(PERIOD)  # a request whose clock read Sunday 23:59:59.999
    assert store.period_salt(NEXT) == current


def test_salt_survives_a_restart(tmp_path):
    a = Store(tmp_path / "o.sqlite")
    salt = a.period_salt(PERIOD)
    a.close()
    b = Store(tmp_path / "o.sqlite")
    assert b.period_salt(PERIOD) == salt
    b.close()


def test_counters_are_per_day_and_anonymous(store):
    store.bump("unregistered_target", DAY)
    store.bump("unregistered_target", DAY)
    store.bump("stored", DAY)
    store.bump("stored", "2026-10-21")
    assert store.counters(DAY) == {"stored": 1, "unregistered_target": 2}
    assert _columns(store, "counters") == ["day", "name", "n"]


def test_file_is_plain_sqlite(tmp_path):
    s = Store(tmp_path / "o.sqlite")
    s.add_observation(ROW)
    s.close()
    with sqlite3.connect(tmp_path / "o.sqlite") as conn:
        assert conn.execute("SELECT COUNT(*) FROM observations").fetchone() == (1,)


def _hashes(store: Store) -> list[str]:
    rows = store.connection.execute("SELECT error_hash FROM observations ORDER BY id")
    return [h for (h,) in rows]


def _row(n: int, **changes):
    return {**ROW, "error_hash": f"{n:064x}", "normalized_error": f"error {n}", **changes}


def test_template_cap_keeps_the_most_frequent_strings(store):
    """Spec 05: at most `template_cap` distinct strings per (service, method, template, status)
    a salt period; a new one evicts the least recent single sighting, never a repeated one."""
    for n in range(3):
        assert isinstance(store.add_observation(_row(n), template_cap=3), int)
    assert isinstance(store.add_observation(_row(1), template_cap=3), int)  # known: always in
    assert isinstance(store.add_observation(_row(3), template_cap=3), int)  # evicts _row(0)
    assert sorted(set(_hashes(store))) == [f"{n:064x}" for n in (1, 2, 3)]
    assert store.counters(DAY) == {"evicted_template_cap": 1}
    for n in (2, 3):
        store.add_observation(_row(n), template_cap=3)
    assert store.add_observation(_row(4), template_cap=3) == Drop.template_cap  # all repeated
    assert len(set(_hashes(store))) == 3


def test_template_cap_is_per_group_and_per_salt_period(store):
    for n in range(2):
        store.add_observation(_row(n), template_cap=2)
    store.add_observation(_row(0), template_cap=2)
    store.add_observation(_row(1), template_cap=2)
    assert store.add_observation(_row(9), template_cap=2) == Drop.template_cap
    assert isinstance(store.add_observation(_row(9, status=404), template_cap=2), int)
    assert isinstance(store.add_observation(_row(9, path_template="/v1/x"), template_cap=2), int)
    next_week = _row(9, received_at=f"{NEXT}T00:00:00Z")
    assert isinstance(store.add_observation(next_week, template_cap=2), int)


def test_rows_without_an_error_string_ignore_the_template_cap(store):
    store.add_observation(_row(0), template_cap=1)
    store.add_observation(_row(0), template_cap=1)
    assert isinstance(store.add_observation({**ROW, "error_hash": None, "normalized_error": None},
                                            template_cap=1), int)
