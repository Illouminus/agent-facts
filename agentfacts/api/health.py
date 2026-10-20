"""`probes_last_run` for `/healthz` (spec 03): when the probe runner last made a run.

Read from the runner's `results.jsonl` on every call, newest line first, so a probe tick shows up
without a restart. Only `pass`/`fail`/`error` are runs; `skipped:no_key` sends no request.
The file is append-only, so the last run line is the latest run; the scan stops after `MAX_SCAN`
bytes from the end (a tail of skips that long reads as "no run seen"). `/healthz` is public and
not rate limited, so the answer is cached per file state (size, mtime): a scan only after a write.
"""

import json
from collections.abc import Iterator
from pathlib import Path

RUN_OUTCOMES = frozenset({"pass", "fail", "error"})
CHUNK = 64 * 1024
MAX_SCAN = 4 * 1024 * 1024


_cache: dict[Path, tuple[tuple[int, int], str | None]] = {}


def _lines_from_end(path: Path) -> Iterator[bytes]:
    """Complete lines of the file, last first (bytes, without the newline)."""
    with path.open("rb") as fh:
        end = fh.seek(0, 2)
        stop = max(0, end - MAX_SCAN)
        rest = b""
        while end > stop:
            start = max(stop, end - CHUNK)
            fh.seek(start)
            block = fh.read(end - start) + rest
            end = start
            lines = block.split(b"\n")
            rest = lines.pop(0) if end > stop else b""
            yield from reversed(lines)


def last_probe_run(path: Path) -> str | None:
    """`started` of the newest run in `path`, or None (no file, no run line, unreadable)."""
    try:
        stat = path.stat()
    except OSError:
        return None
    seen = (stat.st_size, stat.st_mtime_ns)
    cached = _cache.get(path)
    if cached and cached[0] == seen:
        return cached[1]
    value = _scan(path)
    _cache[path] = (seen, value)
    return value


def _scan(path: Path) -> str | None:
    try:
        for line in _lines_from_end(path):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict) and record.get("outcome") in RUN_OUTCOMES:
                started = record.get("started")
                return started if isinstance(started, str) else None
    except OSError:
        return None
    return None
