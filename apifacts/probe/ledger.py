"""Evidence ledger in sqlite (`<state-dir>/evidence-pending.sqlite`): confirmation counters the
runner has not written into the fact YAML yet.

A fact's YAML changes only on a status change, a first confirmation from a new vantage, or the
daily `probe run --refresh-evidence` (spec 04); between those writes every pass and every
non-stale failure lands here. `confirmations` is a delta over the YAML (it survives the YAML being
replaced by main's copy after a refresh PR merges), `last_confirmed` and `stale_counter` are the
current values (None = the YAML's). Losing the file loses at most one day of counters, never a
status.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Self

LEDGER_FILE = "evidence-pending.sqlite"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pending (
    fact_id TEXT PRIMARY KEY, confirmations INTEGER NOT NULL, last_confirmed TEXT,
    stale_counter INTEGER);
"""


@dataclass(frozen=True)
class Pending:
    confirmations: int = 0  # passes not yet in the YAML
    last_confirmed: str | None = None  # RFC 3339 of the latest pass, None = the YAML's
    stale_counter: int | None = None  # current counter, None = the YAML's


class EvidenceLedger:
    def __init__(self, path: Path, *, read_only: bool = False):
        """`read_only` (dry runs): never creates the file; `put` and `clear` are no-ops."""
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

    def get(self, fact_id: str) -> Pending | None:
        if self._db is None:
            return None
        row = self._db.execute(
            "SELECT confirmations, last_confirmed, stale_counter FROM pending WHERE fact_id = ?",
            (fact_id,),
        ).fetchone()
        return Pending(*row) if row else None

    def items(self) -> list[tuple[str, Pending]]:
        if self._db is None:
            return []
        rows = self._db.execute(
            "SELECT fact_id, confirmations, last_confirmed, stale_counter FROM pending"
            " ORDER BY fact_id"
        ).fetchall()
        return [(row[0], Pending(*row[1:])) for row in rows]

    def put(self, fact_id: str, pending: Pending) -> None:
        if self.read_only or self._db is None:
            return
        with self._db:
            self._db.execute(
                "INSERT INTO pending VALUES (?, ?, ?, ?) ON CONFLICT (fact_id) DO UPDATE SET"
                " confirmations = excluded.confirmations, last_confirmed = excluded.last_confirmed,"
                " stale_counter = excluded.stale_counter",
                (fact_id, pending.confirmations, pending.last_confirmed, pending.stale_counter),
            )

    def clear(self, fact_id: str) -> None:
        if self.read_only or self._db is None:
            return
        with self._db:
            self._db.execute("DELETE FROM pending WHERE fact_id = ?", (fact_id,))
