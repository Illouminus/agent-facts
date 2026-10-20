"""Observation fixtures written through the W3 store (the same validation as check())."""

import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from agentfacts.api.normalize import error_hash, normalize
from agentfacts.api.store import Store


def net(n: int) -> str:
    return hashlib.sha256(f"net-{n}".encode()).hexdigest()


def row(
    n: int,
    *,
    message: str | None = "Keys for idempotent requests can only be used with the same parameters",
    status: int | None = 400,
    ua: str = "pytest-plugin",
    sdk: str | None = None,
    at: str = "2026-10-20T10:00:00Z",
    service: str = "stripe",
    method: str = "POST",
    template: str = "/v1/payment_intents",
    env: str | None = None,
) -> dict[str, Any]:
    normalized = normalize(message) if message else None
    return {
        "received_at": at, "service": service, "method": method, "path_template": template,
        "status": status, "error_hash": error_hash(normalized) if normalized else None,
        "normalized_error": normalized, "reporter_net": net(n), "reporter_ua_class": ua,
        "sdk_package": sdk, "sdk_version": "1.0.0" if sdk else None, "env_guess": env,
        "vantage_country": None,
    }


@pytest.fixture
def db(tmp_path) -> Path:
    return tmp_path / "observations.sqlite"


@pytest.fixture
def observe(db) -> Callable[..., None]:
    def add(*rows: dict[str, Any]) -> None:
        store = Store(db)
        try:
            for r in rows:
                assert store.add_observation(r) is not None
        finally:
            store.close()

    return add


def quorum_rows(**kw) -> list[dict[str, Any]]:
    """Three networks, two UA classes: just at the threshold."""
    return [row(1, ua="pytest-plugin", **kw), row(2, ua="sdk", **kw), row(3, ua="sdk", **kw)]
