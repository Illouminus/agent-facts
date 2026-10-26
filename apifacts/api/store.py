"""The sqlite file behind `check()`: observation rows, the weekly reporter salt, anonymous counters.

One connection guarded by a lock (the API runs sync handlers in a thread pool, one process). Every
row is validated by `apifacts.schema.models.Observation` with its final id before it is written,
so nothing outside spec 01 can reach the table.
"""

import secrets
import sqlite3
import threading
from collections.abc import Mapping
from datetime import date, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from apifacts.schema.models import Observation

SCHEMA_SQL = Path(__file__).with_name("schema.sql")
COLUMNS = tuple(Observation.model_fields)
SALT_BYTES = 32


def salt_period(day: date) -> date:
    """First day (Monday, UTC) of the salt period holding `day`: the reporter salt rotates weekly
    at Monday 00:00 UTC, and the quorum window is that same week (spec 03 Q6, spec 05)."""
    return day - timedelta(days=day.weekday())


class Drop(StrEnum):
    """Why `add_observation` stored nothing; the value is the counter name."""

    daily_cap = "dropped_daily_cap"
    template_cap = "dropped_template_cap"


def _day_bounds(received_at: str) -> tuple[str, str]:
    day = date.fromisoformat(received_at[:10])
    return f"{day.isoformat()}T00:00:00Z", f"{(day + timedelta(days=1)).isoformat()}T00:00:00Z"


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock, self.connection:
            self.connection.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))

    def close(self) -> None:
        with self._lock:
            self.connection.close()

    def add_observation(
        self,
        row: Mapping[str, Any],
        *,
        daily_cap: int | None = None,
        template_cap: int | None = None,
    ) -> int | Drop:
        """Insert one observation; its id, or why not (spec 05, abuse controls):

        - `Drop.daily_cap` when `reporter_net` already has `daily_cap` rows that UTC day;
        - `Drop.template_cap` when (service, method, path_template, status) already holds
          `template_cap` distinct error strings this salt period, all seen more than once. While
          one of them is a single sighting, the least recent single sighting is deleted instead
          (counter `evicted_template_cap`) and the new row goes in: the most frequent strings stay.

        ValueError if the row is not a valid observation; nothing is written then."""
        with self._lock, self.connection:
            received = str(row.get("received_at", ""))
            if daily_cap is not None:
                start, end = _day_bounds(received)
                (n,) = self.connection.execute(
                    "SELECT COUNT(*) FROM observations"
                    " WHERE reporter_net = ? AND received_at >= ? AND received_at < ?",
                    (row.get("reporter_net"), start, end),
                ).fetchone()
                if n >= daily_cap:
                    return Drop.daily_cap
            (next_id,) = self.connection.execute(
                "SELECT COALESCE(MAX(id), 0) + 1 FROM observations"
            ).fetchone()
            try:
                obs = Observation.model_validate({**row, "id": next_id})
            except ValidationError as exc:
                raise ValueError(f"not an observation: {exc.error_count()} errors") from exc
            values = obs.model_dump(mode="json")
            if template_cap is not None and values["error_hash"] is not None:
                if not self._make_room(values, template_cap, received):
                    return Drop.template_cap
            self.connection.execute(
                f"INSERT INTO observations ({', '.join(COLUMNS)})"
                f" VALUES ({', '.join('?' for _ in COLUMNS)})",
                tuple(values[c] for c in COLUMNS),
            )
            return next_id

    def _make_room(self, values: Mapping[str, Any], cap: int, received: str) -> bool:
        """Under the lock: may a row with this error string join its template group?"""
        period = salt_period(date.fromisoformat(received[:10])).isoformat() + "T00:00:00Z"
        group = (
            "service = ? AND method = ? AND path_template = ? AND status IS ? AND received_at >= ?"
        )
        key = (
            values["service"], values["method"], values["path_template"], values["status"], period
        )
        known = self.connection.execute(
            f"SELECT 1 FROM observations WHERE {group} AND error_hash = ? LIMIT 1",
            (*key, values["error_hash"]),
        ).fetchone()
        if known is not None:
            return True
        (distinct,) = self.connection.execute(
            f"SELECT COUNT(DISTINCT error_hash) FROM observations WHERE {group}"
            " AND error_hash IS NOT NULL",
            key,
        ).fetchone()
        if distinct < cap:
            return True
        single = self.connection.execute(
            f"SELECT error_hash FROM observations WHERE {group} AND error_hash IS NOT NULL"
            " GROUP BY error_hash HAVING COUNT(*) = 1 ORDER BY MAX(id) LIMIT 1",
            key,
        ).fetchone()
        if single is None:
            return False
        self.connection.execute(
            f"DELETE FROM observations WHERE {group} AND error_hash = ?", (*key, single[0])
        )
        self._bump("evicted_template_cap", received[:10])
        return True

    def count(self) -> int:
        with self._lock:
            return self.connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0]

    def period_salt(self, period: str) -> bytes:
        """The salt of the period starting `period` (its Monday, YYYY-MM-DD, from `salt_period`);
        the first call of a new period creates it and deletes every older one, so last week's
        reporter hashes can no longer be recomputed."""
        with self._lock, self.connection:
            found = self.connection.execute("SELECT salt FROM salts WHERE day = ?", (period,))
            if (row := found.fetchone()) is not None:
                return row[0]
            salt = secrets.token_bytes(SALT_BYTES)
            # only older periods: a late request for last week must not delete this week's salt
            self.connection.execute("DELETE FROM salts WHERE day < ?", (period,))
            # adoption rows outlive their salt by one period: the Monday digest reads last week
            previous = (date.fromisoformat(period) - timedelta(days=7)).isoformat()
            self.connection.execute("DELETE FROM traffic WHERE period < ?", (previous,))
            self.connection.execute("INSERT INTO salts (day, salt) VALUES (?, ?)", (period, salt))
            return salt

    def count_call(self, period: str, net: str, *, own: bool, stored: bool) -> None:
        """One answered check() call for the adoption metric (D-092): a row per network per salt
        period, its call and stored-observation counts."""
        with self._lock, self.connection:
            self.connection.execute(
                "INSERT INTO traffic (period, net, own, calls, stored) VALUES (?, ?, ?, 1, ?)"
                " ON CONFLICT (period, net) DO UPDATE SET calls = calls + 1,"
                " stored = stored + excluded.stored",
                (period, net, int(own), int(stored)),
            )

    def bump(self, name: str, day: str) -> None:
        with self._lock, self.connection:
            self._bump(name, day)

    def _bump(self, name: str, day: str) -> None:
        self.connection.execute(
            "INSERT INTO counters (day, name, n) VALUES (?, ?, 1)"
            " ON CONFLICT (day, name) DO UPDATE SET n = n + 1",
            (day, name),
        )

    def counters(self, day: str) -> dict[str, int]:
        with self._lock:
            rows = self.connection.execute(
                "SELECT name, n FROM counters WHERE day = ? ORDER BY name", (day,)
            )
            return dict(rows.fetchall())
