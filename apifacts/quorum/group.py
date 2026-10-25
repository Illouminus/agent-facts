"""Group the observations of one salt period and count who saw each signal (spec 05 Quorum).

The window is the salt period (Monday 00:00 UTC → now, ≤ 7 days): inside it one reporter network
has one hash, so "≥ 3 distinct networks" counts networks, not network-days. The database is read
read-only; a missing file reads as no observations (a fresh host, a dry run).
"""

import sqlite3
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from apifacts.api.store import salt_period

MIN_NETS = 3  # spec 05: distinct reporter networks
MIN_CLIENTS = 2  # spec 05: distinct UA classes or SDK packages
MIN_NET_ROWS = 2  # spec 05 (D-093): a network's client counts only from its second row of the week
PERIOD = timedelta(days=7)


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def period_window(now: datetime, since: date | None = None) -> tuple[datetime, datetime]:
    """[start, end) of the salt period holding `since` (default: today): Monday 00:00 UTC to the
    next Monday (for the current period nothing after `now` exists yet)."""
    start = datetime.combine(salt_period(since or now.astimezone(UTC).date()), time(), UTC)
    return start, start + PERIOD


def load_observations(db: Path, start: datetime, end: datetime) -> list[dict[str, Any]]:
    """Rows received in [start, end) that carry a signal, oldest first."""
    if not db.is_file():
        return []
    conn = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM observations WHERE received_at >= ? AND received_at < ?"
            " AND (status IS NOT NULL OR error_hash IS NOT NULL) ORDER BY received_at, id",
            (_stamp(start), _stamp(end)),
        )
        return [dict(r) for r in rows]
    finally:
        conn.close()


GroupKey = tuple[str, str, str, str]  # (service, method, path_template, error_hash | "status:<n>")


@dataclass
class Group:
    service: str
    method: str
    path_template: str
    error_hash: str | None
    normalized: str | None
    statuses: Counter = field(default_factory=Counter)
    nets: set[str] = field(default_factory=set)
    ua_classes: set[str] = field(default_factory=set)
    sdk_packages: set[str] = field(default_factory=set)
    env_guesses: Counter = field(default_factory=Counter)
    first_seen: str = ""

    @property
    def status(self) -> int | None:
        """The most frequent status (ties: the lowest), None when no reporter sent one."""
        if not self.statuses:
            return None
        return min(self.statuses, key=lambda s: (-self.statuses[s], s))

    @property
    def env(self) -> str | None:
        """The most frequent env guess (ties: alphabetical), None when nobody could tell."""
        if not self.env_guesses:
            return None
        return min(self.env_guesses, key=lambda e: (-self.env_guesses[e], e))

    @property
    def clients(self) -> int:
        """Spec 05 "distinct UA classes or SDK packages": the larger of the two counts, both
        taken only from networks with at least two rows in the salt period. The client declares
        its own UA and SDK; one row from a fresh network must not buy the second factor."""
        return max(len(self.ua_classes), len(self.sdk_packages))

    @property
    def meets_quorum(self) -> bool:
        return len(self.nets) >= MIN_NETS and self.clients >= MIN_CLIENTS

    @property
    def label(self) -> str:
        signal = f'"{self.normalized}"' if self.normalized else f"status {self.status}"
        return f"{self.service} {self.method} {self.path_template} {signal}"


def _key(row: Mapping[str, Any]) -> GroupKey:
    signal = row["error_hash"] or f"status:{row['status']}"
    return (row["service"], row["method"], row["path_template"], signal)


def group_observations(rows: Iterable[Mapping[str, Any]]) -> list[Group]:
    """By `(service, method, path_template, error_hash)`; rows without a string by
    `(service, method, path_template, status)`. Sorted by key. `rows` is the whole salt period:
    a network's row count (for `clients`) runs across every group."""
    rows = list(rows)
    per_net = Counter(row["reporter_net"] for row in rows)
    groups: dict[GroupKey, Group] = {}
    for row in rows:
        key = _key(row)
        group = groups.get(key)
        if group is None:
            group = groups[key] = Group(
                row["service"], row["method"], row["path_template"], row["error_hash"],
                row["normalized_error"], first_seen=row["received_at"],
            )
        if row["status"] is not None:
            group.statuses[row["status"]] += 1
        group.nets.add(row["reporter_net"])
        if per_net[row["reporter_net"]] >= MIN_NET_ROWS:
            group.ua_classes.add(row["reporter_ua_class"])
            if row["sdk_package"]:
                group.sdk_packages.add(row["sdk_package"])
        if row["env_guess"]:
            group.env_guesses[row["env_guess"]] += 1
        group.first_seen = min(group.first_seen, row["received_at"])
    return [groups[k] for k in sorted(groups)]
