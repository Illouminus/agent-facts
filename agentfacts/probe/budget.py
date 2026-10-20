"""Budget state in sqlite (`<state-dir>/probe-state.sqlite`): when each probe and each endpoint
template last ran, per vantage.

A probe is due when its own last run *and* the last run of every template it hits are at least
the service's `per_template_seconds` ago (invariant 6: ≤ 1 request / 5 min per service, endpoint
template and vantage — two probes on one template must not double the rate). Transient state:
losing the file makes every probe due once, nothing verified is lost.
"""

import math
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Self

TemplateKey = tuple[str, str, str]  # (service, method, path template)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS probe_runs (
    probe_id TEXT NOT NULL, vantage TEXT NOT NULL, at REAL NOT NULL, outcome TEXT NOT NULL,
    PRIMARY KEY (probe_id, vantage));
CREATE TABLE IF NOT EXISTS template_runs (
    service TEXT NOT NULL, method TEXT NOT NULL, template TEXT NOT NULL, vantage TEXT NOT NULL,
    at REAL NOT NULL,
    PRIMARY KEY (service, method, template, vantage));
"""


class BudgetState:
    def __init__(self, path: Path, *, read_only: bool = False):
        """`read_only` (dry runs): never creates the file, `record` is a no-op."""
        self.read_only = read_only
        self._db: sqlite3.Connection | None = None
        if read_only:
            if path.is_file():
                self._db = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(path, timeout=30)
            self._db.executescript(_SCHEMA)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None

    def _one(self, sql: str, args: tuple) -> tuple | None:
        if self._db is None:
            return None
        return self._db.execute(sql, args).fetchone()

    def last_run(self, probe_id: str, vantage: str) -> tuple[float, str] | None:
        row = self._one(
            "SELECT at, outcome FROM probe_runs WHERE probe_id = ? AND vantage = ?",
            (probe_id, vantage),
        )
        return (row[0], row[1]) if row else None

    def template_last(self, service: str, method: str, template: str, vantage: str) -> float | None:
        row = self._one(
            "SELECT at FROM template_runs WHERE service = ? AND method = ? AND template = ?"
            " AND vantage = ?",
            (service, method, template, vantage),
        )
        return row[0] if row else None

    def wait_seconds(
        self,
        probe_id: str,
        templates: Iterable[TemplateKey],
        vantage: str,
        budget_s: float,
        now: float,
    ) -> int:
        """Seconds until the probe is due (0 = due now), rounded up."""
        times = [self.template_last(*t, vantage) for t in templates]
        last = self.last_run(probe_id, vantage)
        times.append(last[0] if last else None)
        latest = max((t for t in times if t is not None), default=None)
        if latest is None:
            return 0
        return max(0, math.ceil(latest + budget_s - now))

    def record(
        self, probe_id: str, templates: Iterable[TemplateKey], vantage: str, at: float, outcome: str
    ) -> None:
        if self.read_only or self._db is None:
            return
        with self._db:
            self._db.execute(
                "INSERT INTO probe_runs VALUES (?, ?, ?, ?) ON CONFLICT (probe_id, vantage)"
                " DO UPDATE SET at = excluded.at, outcome = excluded.outcome",
                (probe_id, vantage, at, outcome),
            )
            self._db.executemany(
                "INSERT INTO template_runs VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT (service, method, template, vantage) DO UPDATE SET at = excluded.at",
                [(*t, vantage, at) for t in set(templates)],
            )
