"""Builders for probe-runner tests: a service/probe/fact tree in `tmp_path`, no real network.

Imported as `probe_builders` (pytest puts this directory on `sys.path`; `tests/` is no package)."""

import copy
from pathlib import Path
from typing import Any

import yaml

from agentfacts.schema.models import Service

FAKE_KEY = "sk_test_FAKEfake0123456789abcdefXYZ"


def service_doc(**overrides: Any) -> dict[str, Any]:
    doc = {
        "key": "acme",
        "name": "Acme",
        "hosts": ["api.acme.example"],
        "surfaces": {
            "http": {
                "base_url": "https://api.acme.example",
                "templates": [
                    {"method": "GET", "path": "/v1/items"},
                    {"method": "POST", "path": "/v1/items"},
                    {"method": "GET", "path": "/v1/items/{id}"},
                    {"method": "GET", "path": "/v1/redirect"},
                    {"method": "GET", "path": "/v1/slow"},
                    {"method": "GET", "path": "/v1/big"},
                ],
                "signal_fields": ["status", "error.code", "x-echo", "retry-after"],
            }
        },
        "dimensions": {
            "env": {"prod": "https://api.acme.example", "sandbox": "https://api.acme.example"},
            "account_state": ["active", "restricted"],
        },
        "auth": {"kind": "bearer", "key_name": "acme-test", "env": "sandbox"},
        "tos": {
            "automated_access": "allowed",
            "publish_measurements": "allowed",
            "source": "https://acme.example/tos",
        },
        "probe_budget": {"per_template_seconds": 300},
    }
    doc.update(copy.deepcopy(overrides))
    return doc


def make_service(**overrides: Any) -> Service:
    return Service.model_validate(service_doc(**overrides))


def probe_doc(slug: str = "items-list", **overrides: Any) -> dict[str, Any]:
    doc = {
        "id": f"af:acme:probe:{slug}",
        "service": "acme",
        "env": "sandbox",
        "steps": [{"do": "http", "method": "GET", "path": "/v1/items"}],
        "assert": [{"step": 1, "status": 200}],
    }
    doc.update(copy.deepcopy(overrides))
    return doc


def fact_doc(slug: str = "items-list-ok", probe: str = "items-list", **overrides: Any) -> dict:
    env = overrides.pop("env", "sandbox")
    doc = {
        "id": f"af:acme:{slug}",
        "service": "acme",
        "kind": "availability",
        "target": {"surface": "http", "method": "GET", "path_template": "/v1/items"},
        "claim": "GET /v1/items answers 200 for a valid key.",
        "dimensions": {"env": env, "plan": "any", "region": "any", "account_state": "any"},
        "fixes": [{"action": "none_known", "reason_kind": "by_design"}],
        "status": f"verified:server:{env}",
        "evidence": {
            "probe": f"af:acme:probe:{probe}",
            "first_seen": "2026-10-01T09:00:00Z",
            "last_confirmed": "2026-10-01T09:00:00Z",
            "confirmations": 1,
            "vantages": ["illouminus"],
        },
        "provenance": {
            "source": "probe",
            "author": "bot",
            "created": "2026-10-01",
            "history": [{"date": "2026-10-01", "change": "created", "by": "bot"}],
        },
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(doc.get(key), dict):
            doc[key] = {**doc[key], **copy.deepcopy(value)}
        else:
            doc[key] = copy.deepcopy(value)
    return doc


def write_yaml(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


class Repo:
    def __init__(self, root: Path):
        self.root = root
        self.state = root / "var"
        self.keys = root / "keys"
        self.keys.mkdir(parents=True, exist_ok=True)

    def service(self, **overrides: Any) -> Path:
        doc = service_doc(**overrides)
        return write_yaml(self.root / "services" / f"{doc['key']}.yaml", doc)

    def probe(self, slug: str = "items-list", **overrides: Any) -> Path:
        doc = probe_doc(slug, **overrides)
        return write_yaml(self.root / "probes" / doc["service"] / f"{slug}.yaml", doc)

    def fact(self, slug: str = "items-list-ok", probe: str = "items-list", **overrides) -> Path:
        doc = fact_doc(slug, probe, **overrides)
        return write_yaml(self.root / "facts" / doc["service"] / f"{slug}.yaml", doc)

    def key(self, name: str = "acme-test", value: str = FAKE_KEY) -> None:
        (self.keys / f"{name}.key").write_text(value + "\n", encoding="utf-8")

    def results(self) -> list[dict]:
        import json

        path = self.state / "results.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
