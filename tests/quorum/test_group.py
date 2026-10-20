"""Grouping by signal and the spec 05 thresholds, inside the salt period."""

from datetime import UTC, date, datetime

import pytest
from conftest import quorum_rows, row

from agentfacts.quorum.group import group_observations, load_observations, period_window

NOW = datetime(2026, 10, 21, 10, 0, tzinfo=UTC)  # a Wednesday


def groups(db, now=NOW, since=None):
    return group_observations(load_observations(db, *period_window(now, since)))


def test_period_window_is_the_salt_week():
    assert period_window(NOW) == (datetime(2026, 10, 19, tzinfo=UTC),
                                  datetime(2026, 10, 26, tzinfo=UTC))
    past = period_window(NOW, date(2026, 10, 14))
    assert past == (datetime(2026, 10, 12, tzinfo=UTC), datetime(2026, 10, 19, tzinfo=UTC))


def test_missing_db_reads_as_empty(tmp_path):
    assert load_observations(tmp_path / "none.sqlite", *period_window(NOW)) == []
    assert not (tmp_path / "none.sqlite").exists()


def test_string_rows_group_by_hash_and_status_rows_by_status(db, observe):
    observe(*quorum_rows(), row(4, message=None, status=429), row(5, message=None, status=429),
            row(6, message="Other thing"))
    found = {(g.normalized, g.status, len(g.nets)) for g in groups(db)}
    assert found == {
        ("keys for idempotent requests can only be used with the same parameters", 400, 3),
        (None, 429, 2),
        ("other thing", 400, 1),
    }


def test_quorum_threshold(db, observe):
    observe(*quorum_rows())
    (g,) = groups(db)
    assert g.meets_quorum and g.clients == 2 and g.first_seen == "2026-10-20T10:00:00Z"


@pytest.mark.parametrize(
    "rows, met",
    [
        ([row(1, ua="sdk"), row(2, ua="pytest-plugin")], False),  # two networks
        ([row(1, ua="sdk"), row(1, ua="mcp"), row(2, ua="other")], False),  # same net twice
        ([row(1), row(2), row(3)], False),  # one client class, no SDK
        ([row(1, sdk="stripe"), row(2, sdk="stripe"), row(3, sdk="stripe")], False),
        ([row(1, sdk="stripe"), row(2, sdk="stripe-node"), row(3)], True),  # 2 SDK packages
        ([row(1, ua="mcp"), row(2, ua="sdk"), row(3, ua="other"), row(4)], True),
    ],
)
def test_thresholds(db, observe, rows, met):
    observe(*rows)
    (g,) = groups(db)
    assert g.meets_quorum is met


def test_rows_outside_the_period_are_ignored(db, observe):
    observe(*quorum_rows(at="2026-10-18T23:59:59Z"))  # Sunday of the previous week
    assert groups(db) == []
    (g,) = groups(db, since=date(2026, 10, 18))
    assert g.meets_quorum


def test_status_and_env_majorities(db, observe):
    observe(row(1, status=400, env="sandbox"), row(2, status=402, env="sandbox"),
            row(3, status=402, env="prod"), row(4, status=None))
    (g,) = groups(db)
    assert (g.status, g.env) == (402, "sandbox")
