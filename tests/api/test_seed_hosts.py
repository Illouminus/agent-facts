"""The seed-host list behind the unregistered-target metric lists every registered service's hosts,
so the metric never drops a host the registry probes."""

from pathlib import Path

import pytest
from pydantic import TypeAdapter

from apifacts.api.seed_hosts import OTHER, SEED_HOSTS, metric_host
from apifacts.schema.models import Hostname, Service
from apifacts.schema.yamlio import load_yaml, plain

ROOT = Path(__file__).parents[2]


def test_every_host_is_a_lowercase_hostname():
    adapter = TypeAdapter(Hostname)
    for hosts in SEED_HOSTS.values():
        assert hosts, "an entry without hosts is no entry"
        for host in hosts:
            assert adapter.validate_python(host) == host


def test_registered_services_hosts_are_listed():
    listed = {host for hosts in SEED_HOSTS.values() for host in hosts}
    for path in sorted((ROOT / "services").glob("*.yaml")):
        service = Service.model_validate(plain(load_yaml(path)))
        assert set(service.hosts) <= listed, service.key  # keyed by candidate name, e.g. firebase


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
