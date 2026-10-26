"""The adoption number of D-092: who outside our own hosts calls `check()`, read from `traffic`.

One salt period (Monday 00:00 UTC → next Monday) is the only window where "distinct networks" is
exact: the network hash changes with the salt. The gate (≥ 10 external clients in 23–29.11, or ≥ 1
external stored observation) is one such period. Read-only: a missing db or table is all zeros
with `available=False`, never created.
"""

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from apifacts.api.store import salt_period


@dataclass(frozen=True)
class Adoption:
    period: date  # the salt period's Monday
    available: bool
    external_clients: int = 0
    calls: int = 0
    reported_external: int = 0
    own_calls: int = 0

    def line(self) -> str:
        """The one line `source_cmd` of the gate reads: first field = the gated number."""
        return (f"external_clients={self.external_clients} calls={self.calls} "
                f"reported_external={self.reported_external}")


def period_of(now: datetime, current: bool = False) -> date:
    """The last complete salt period at `now`, or the running one with `current`."""
    monday = salt_period(now.date())
    return monday if current else monday - timedelta(days=7)


def read_adoption(db: Path, period: date) -> Adoption:
    if not db.is_file():
        return Adoption(period, available=False)
    con = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT own, COUNT(*), SUM(calls), SUM(stored) FROM traffic WHERE period = ?"
            " GROUP BY own", (period.isoformat(),)
        ).fetchall()
    except sqlite3.Error:  # an API older than the table: nothing measured yet
        return Adoption(period, available=False)
    finally:
        con.close()
    by_own = {bool(own): (nets, calls, stored) for own, nets, calls, stored in rows}
    nets, calls, stored = by_own.get(False, (0, 0, 0))
    return Adoption(period, available=True, external_clients=nets, calls=calls,
                    reported_external=stored, own_calls=by_own.get(True, (0, 0, 0))[1])
