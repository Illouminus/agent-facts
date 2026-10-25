"""The seed-host list behind the unregistered-target metric stays tied to its sources: candidate
names from docs/research/seed-100/candidates.py, hosts of the registered services."""

import runpy
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from apifacts.api.seed_hosts import OTHER, SEED_HOSTS, metric_host
from apifacts.schema.models import Hostname, Service
from apifacts.schema.yamlio import load_yaml, plain

ROOT = Path(__file__).parents[2]
CANDIDATES = ROOT / "docs" / "research" / "seed-100" / "candidates.py"


def _candidate_names() -> set[str]:
    return {row["service"] for row in runpy.run_path(str(CANDIDATES))["rows"]()}


def test_every_entry_is_a_seed_candidate():
    assert set(SEED_HOSTS) <= _candidate_names()


def test_every_host_is_a_lowercase_hostname():
    adapter = TypeAdapter(Hostname)
    for hosts in SEED_HOSTS.values():
        assert hosts, "an entry without hosts is no entry"
        for host in hosts:
            assert adapter.validate_python(host) == host


def test_registered_services_hosts_are_listed():
    for path in sorted((ROOT / "services").glob("*.yaml")):
        service = Service.model_validate(plain(load_yaml(path)))
        if service.key in _candidate_names():
            assert set(service.hosts) <= set(SEED_HOSTS.get(service.key, ())), service.key


@pytest.mark.parametrize(
    "host, label",
    [
        ("api.notion.com", "api.notion.com"),
        ("API.Notion.com.", "api.notion.com"),
        ("acme.api.notion.com", OTHER),  # a tenant subdomain is never kept
        ("my-bucket.s3.amazonaws.com", OTHER),
        ("notion.com", OTHER),
        ("", OTHER),
        (None, OTHER),
    ],
)
def test_metric_host(host, label):
    assert metric_host(host) == label
