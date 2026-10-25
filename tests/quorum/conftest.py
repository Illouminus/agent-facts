"""Fixtures: an observations.sqlite written through the W3 store (the same validation as
check())."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from apifacts.api.store import Store


@pytest.fixture
def db(tmp_path) -> Path:
    return tmp_path / "observations.sqlite"


@pytest.fixture
def observe(db) -> Callable[..., None]:
    def add(*rows: dict[str, Any]) -> None:
        store = Store(db)
        try:
            for r in rows:
                assert isinstance(store.add_observation(r), int)
        finally:
            store.close()

    return add
