"""`/healthz` reads `probes_last_run` from the runner's results.jsonl (spec 03)."""

import json
from pathlib import Path

import pytest

from agentfacts.api import health
from agentfacts.api.health import last_probe_run


def _write(path: Path, records: list[dict | str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [r if isinstance(r, str) else json.dumps(r) for r in records]
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    return path


def _run(started: str, outcome: str = "pass") -> dict:
    return {"probe_id": "af:stripe:probe:p1", "started": started, "outcome": outcome}


def test_last_run_is_the_newest_run_line_skips_do_not_count(tmp_path):
    path = _write(tmp_path / "results.jsonl", [
        _run("2026-10-20T13:57:57Z"),
        _run("2026-10-20T15:00:00Z", "fail"),
        _run("2026-10-20T15:15:00Z", "skipped:no_key"),
        '{"broken',
        "",
    ])
    assert last_probe_run(path) == "2026-10-20T15:00:00Z"


def test_no_file_or_no_run_reads_as_none(tmp_path):
    assert last_probe_run(tmp_path / "nope.jsonl") is None
    only_skips = _write(tmp_path / "skips.jsonl", [_run("2026-10-20T15:15:00Z", "skipped:no_key")])
    assert last_probe_run(only_skips) is None


def test_lines_across_chunk_boundaries_are_whole(tmp_path, monkeypatch):
    monkeypatch.setattr(health, "CHUNK", 7)
    records = [_run(f"2026-10-20T1{i}:00:00Z", "error" if i % 2 else "pass") for i in range(6)]
    path = _write(tmp_path / "results.jsonl", records + [_run("2026-10-20T17:00:00Z", "skipped")])
    assert last_probe_run(path) == "2026-10-20T15:00:00Z"
    lines = list(health._lines_from_end(path))
    assert [json.loads(x)["started"] for x in lines if x] == [
        r["started"] for r in reversed(records + [_run("2026-10-20T17:00:00Z")])
    ]


def test_healthz_shows_the_last_run_without_a_restart(repo, make_client):
    client = make_client()
    assert client.get("/healthz").json()["probes_last_run"] is None
    _write(repo / "var" / "results.jsonl", [_run("2026-10-20T15:00:00Z")])
    assert client.get("/healthz").json() == {
        "ok": True, "registry_version": "2026-10-22", "probes_last_run": "2026-10-20T15:00:00Z"
    }


def test_results_path_from_the_environment(tmp_path, monkeypatch, make_client):
    path = _write(tmp_path / "elsewhere.jsonl", [_run("2026-10-21T08:00:00Z")])
    monkeypatch.setenv("AGENTFACTS_RESULTS", str(path))
    assert make_client().get("/healthz").json()["probes_last_run"] == "2026-10-21T08:00:00Z"


def test_unchanged_file_is_not_rescanned(tmp_path, monkeypatch):
    path = _write(tmp_path / "results.jsonl", [_run("2026-10-20T15:00:00Z")])
    assert last_probe_run(path) == "2026-10-20T15:00:00Z"
    monkeypatch.setattr(health, "_scan", lambda p: pytest.fail("rescanned an unchanged file"))
    assert last_probe_run(path) == "2026-10-20T15:00:00Z"
    monkeypatch.undo()
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(_run("2026-10-20T15:15:00Z")) + "\n")
    assert last_probe_run(path) == "2026-10-20T15:15:00Z"
