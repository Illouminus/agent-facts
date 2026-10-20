"""Loader: the W1 validator gates every file; only clean files become models."""

from agentfacts.probe.loader import load_repo
from agentfacts.schema.models import Fact, Probe, Service


def test_valid_repo_loads_models(repo):
    repo.service()
    repo.probe()
    repo.fact()
    loaded = load_repo(repo.root)
    assert loaded.problems == []
    assert isinstance(loaded.services["acme"], Service)
    assert [type(p.probe) for p in loaded.probes] == [Probe]
    assert [type(f.fact) for f in loaded.facts] == [Fact]
    assert loaded.probes[0].path.name == "items-list.yaml"
    assert loaded.facts_citing("af:acme:probe:items-list")[0].fact.id == "af:acme:items-list-ok"


def test_prod_post_probe_is_not_loaded(repo):
    repo.service(auth={"kind": "none"})
    repo.probe(
        "write-in-prod",
        env="prod",
        steps=[{"do": "http", "method": "POST", "path": "/v1/items", "form": {"a": 1}}],
    )
    loaded = load_repo(repo.root)
    assert loaded.probes == []
    assert "prod_probe_not_readonly" in {p.code for p in loaded.problems}


def test_probe_of_an_unknown_service_is_reported(repo):
    repo.probe()
    loaded = load_repo(repo.root)
    assert loaded.probes == []
    assert {p.code for p in loaded.problems} == {"unknown_service"}


def test_probe_of_an_invalid_service_is_not_loaded(repo):
    repo.service(tos={"automated_access": "forbidden", "publish_measurements": "allowed",
                      "source": "https://acme.example/tos"})
    repo.probe()
    loaded = load_repo(repo.root)
    assert loaded.services == {} and loaded.probes == []
    codes = {p.code for p in loaded.problems}
    assert "unknown_service" in codes and len(codes) == 2


def test_empty_root(tmp_path):
    loaded = load_repo(tmp_path)
    assert (loaded.services, loaded.probes, loaded.facts, loaded.problems) == ({}, [], [], [])
