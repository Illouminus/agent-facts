"""Fixtures for the ops tests; builders live in ops_builders.py (importable from test modules)."""

from pathlib import Path

import pytest
from ops_builders import FakeState, Registry


@pytest.fixture
def registry(tmp_path: Path) -> Registry:
    return Registry(tmp_path / "repo")


@pytest.fixture
def state(tmp_path: Path) -> FakeState:
    return FakeState(tmp_path / "state")


@pytest.fixture(autouse=True)
def _no_commit_rc(monkeypatch):
    monkeypatch.delenv("FAKE_STATE_COMMIT_RC", raising=False)
