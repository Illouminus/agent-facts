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
        self, row: Mapping[str, Any], *, daily_cap: int | None = None
    ) -> int | None:
        """Insert one observation; its id, or None when `reporter_net` already has `daily_cap`
        rows that UTC day (spec 05: silently dropped beyond). ValueError if the row is not a
        valid observation; nothing is written then."""
        with self._lock, self.connection:
            if daily_cap is not None:
                start, end = _day_bounds(str(row.get("received_at", "")))
                (n,) = self.connection.execute(
                    "SELECT COUNT(*) FROM observations"
                    " WHERE reporter_net = ? AND received_at >= ? AND received_at < ?",
                    (row.get("reporter_net"), start, end),
                ).fetchone()
                if n >= daily_cap:
                    return None
            (next_id,) = self.connection.execute(
                "SELECT COALESCE(MAX(id), 0) + 1 FROM observations"
            ).fetchone()
            try:
                obs = Observation.model_validate({**row, "id": next_id})
            except ValidationError as exc:
                raise ValueError(f"not an observation: {exc.error_count()} errors") from exc
            values = obs.model_dump(mode="json")
            self.connection.execute(
                f"INSERT INTO observations ({', '.join(COLUMNS)})"
                f" VALUES ({', '.join('?' for _ in COLUMNS)})",
                tuple(values[c] for c in COLUMNS),
            )
            return next_id

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
            self.connection.execute("INSERT INTO salts (day, salt) VALUES (?, ?)", (period, salt))
            return salt

    def bump(self, name: str, day: str) -> None:
        with self._lock, self.connection:
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
