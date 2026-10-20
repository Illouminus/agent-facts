"""Builders for the ops tests: a registry tree, results.jsonl, observations.sqlite, a fake megabrain
state directory whose `bin/state-commit` only records how it was called. No network, no VPS."""

import copy
import json
import sqlite3
import stat
import sys
from pathlib import Path
from typing import Any

import yaml

from agentfacts.schema.yamlio import load_yaml, plain

REPO = Path(__file__).resolve().parents[2]
VALID = REPO / "tests" / "fixtures" / "valid"
sys.path.insert(0, str(REPO / "ops"))  # ops/*.py are scripts, imported here as modules

# One verified fact with a probe and one reported fact without; tests derive the rest from these.
VERIFIED = plain(load_yaml(VALID / "fact-idempotency-key-reuse-different-params.yaml"))
REPORTED = plain(load_yaml(VALID / "fact-customer-retrieve-rate-limit.yaml"))
STRIPE = plain(load_yaml(VALID / "service-stripe.yaml"))

JOURNAL = """---
name: agent-facts
title: agent-facts
stage: mvp
status: active
next: что-то одно
updated: 2026-10-20
---

## Журнал

### 2026-10-20 — старая запись

- было
"""

RECORDER = """#!/bin/sh
# records argv (one argument per line, a RS line ends a call), exits $FAKE_STATE_COMMIT_RC (0)
log="$(dirname "$0")/../calls.txt"
for arg in "$@"; do printf '%s\\n' "$arg" >> "$log"; done
printf '\\036\\n' >> "$log"
exit "${FAKE_STATE_COMMIT_RC:-0}"
"""


class Registry:
    def __init__(self, root: Path):
        self.root = root
        (root / "services").mkdir(parents=True, exist_ok=True)
        (root / "services" / "stripe.yaml").write_text(yaml.safe_dump(STRIPE), encoding="utf-8")

    def fact(self, slug: str, base: dict[str, Any] = VERIFIED, **changes: Any) -> dict[str, Any]:
        """Write facts/stripe/<slug>.yaml from `base`; `evidence__probe=...` edits a nested
        field, a value of None deletes it."""
        doc = copy.deepcopy(base)
        doc["id"] = f"af:stripe:{slug}"
        for dotted, value in changes.items():
            *parents, leaf = dotted.split("__")
            node = doc
            for part in parents:
                node = node.setdefault(part, {})
            if value is None:
                node.pop(leaf, None)
            else:
                node[leaf] = value
        path = self.root / "facts" / "stripe" / f"{slug}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        return doc


def write_results(path: Path, records: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    return path


def run_record(
    started: str,
    outcome: str = "pass",
    probe_id: str = "af:stripe:probe:p1",
    template: str = "/v1/customers/{id}",
    method: str = "GET",
    vantage: str = "illouminus",
    detail: str | None = None,
) -> dict[str, Any]:
    steps = []
    if outcome in ("pass", "fail", "error"):
        steps = [{"step": 1, "do": "http", "method": method, "path": "/v1/customers/x",
                  "template": template, "status": 200}]
    return {"probe_id": probe_id, "service": "stripe", "vantage": vantage, "env": "prod",
            "started": started, "outcome": outcome, "detail": detail, "steps": steps,
            "asserts": []}


def make_db(path: Path, observations: list[dict[str, Any]], counters: list[tuple[str, str, int]]):
    """observations.sqlite with the W3 schema (agentfacts/api/schema.sql)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript((REPO / "agentfacts" / "api" / "schema.sql").read_text(encoding="utf-8"))
    for i, row in enumerate(observations, start=1):
        full = {"id": i, "service": "stripe", "method": "GET",
                "path_template": "/v1/customers/{id}", "status": 429, "error_hash": None,
                "normalized_error": None,
                "reporter_ua_class": "pytest-plugin", "sdk_package": None, "sdk_version": None,
                "env_guess": None, "vantage_country": None, **row}
        cols = ", ".join(full)
        con.execute(f"INSERT INTO observations ({cols}) VALUES ({', '.join('?' * len(full))})",
                    tuple(full.values()))
    con.executemany("INSERT INTO counters (day, name, n) VALUES (?, ?, ?)", counters)
    con.commit()
    con.close()
    return path


class FakeState:
    def __init__(self, root: Path):
        self.root = root
        for sub in ("projects", "tasks", "reviews", "bin"):
            (root / sub).mkdir(parents=True, exist_ok=True)
        self.journal = root / "projects" / "agent-facts.md"
        self.journal.write_text(JOURNAL, encoding="utf-8")
        commit = root / "bin" / "state-commit"
        commit.write_text(RECORDER, encoding="utf-8")
        commit.chmod(commit.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def calls(self) -> list[list[str]]:
        log = self.root / "calls.txt"
        if not log.exists():
            return []
        calls = log.read_text(encoding="utf-8").split("\x1e\n")[:-1]
        return [call.splitlines() for call in calls]
