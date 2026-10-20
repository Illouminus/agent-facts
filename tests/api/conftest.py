"""Fixtures for the API tests: a tmp registry repo, a TestClient with lifespan, row counters."""

import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest
from api_fixtures import PEER, write_repo
from fastapi.testclient import TestClient


@pytest.fixture
def repo(tmp_path) -> Path:
    return write_repo(tmp_path / "repo")


@pytest.fixture
def db_path(tmp_path) -> Path:
    return tmp_path / "observations.sqlite"


@pytest.fixture
def make_client(repo, db_path):
    clients = []

    from agentfacts.api.app import create_app

    def make(peer: tuple[str, int] = PEER, **kwargs) -> TestClient:
        client = TestClient(create_app(repo=repo, db_path=db_path, **kwargs), client=peer)
        client.__enter__()  # runs the lifespan: index + store
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()


@pytest.fixture
def rows(db_path) -> Callable[[], int]:
    def count() -> int:
        with sqlite3.connect(db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]

    return count


@pytest.fixture
def counters(db_path) -> Callable[[], dict[str, int]]:
    def read() -> dict[str, int]:
        with sqlite3.connect(db_path) as conn:
            return dict(conn.execute("SELECT name, SUM(n) FROM counters GROUP BY name"))

    return read
