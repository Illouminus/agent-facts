import shutil
from pathlib import Path

import pytest
from agentfacts.client.offline import Snapshot
from agentfacts.schema.yamlio import load_yaml, plain

FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "valid"
FACT_FILE = "fact-idempotency-key-reuse-different-params.yaml"
SERVICES = {"services": [{"key": "stripe", "hosts": ["api.stripe.com"], "facts": 1}]}


def answer() -> dict:
    """What a spec-03 server returns for the stripe fixture fact."""
    fact = plain(load_yaml(FIXTURES / FACT_FILE))
    return {
        "service": "stripe",
        "matched_template": {"method": "POST", "path": "/v1/payment_intents"},
        "facts": [{**fact, "fixes_rendered": ["(server sentence)"]}],
        "observed": {"status_distribution_30d": {"200": 0.97, "400": 0.03}},
        "registry": {"version": "2026-10-20", "facts_for_service": 1, "license": "CC-BY-4.0"},
    }


@pytest.fixture
def plugin_env(monkeypatch, tmp_path):
    """Isolate every run: own cache dir, no inherited agent-facts settings."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg-cache"))
    for name in ("AGENTFACTS_DISABLE", "AGENTFACTS_SNAPSHOT", "AGENTFACTS_ENDPOINT"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


@pytest.fixture
def registry(httpserver, plugin_env):
    """A fake check() server: services list + one stripe fact."""
    plugin_env.setenv("AGENTFACTS_ENDPOINT", httpserver.url_for("").rstrip("/"))
    httpserver.expect_request("/v0/services", method="GET").respond_with_json(SERVICES)
    return httpserver


@pytest.fixture
def snapshot_dir(tmp_path):
    root = tmp_path / "snapshot"
    (root / "services").mkdir(parents=True)
    (root / "facts" / "stripe").mkdir(parents=True)
    shutil.copy(FIXTURES / "service-stripe.yaml", root / "services" / "stripe.yaml")
    shutil.copy(FIXTURES / FACT_FILE, root / "facts" / "stripe" / FACT_FILE)
    assert Snapshot.load(root).hosts == {"api.stripe.com"}
    return root


def requests_to(httpserver, path):
    return [req for req, _ in httpserver.log if req.path == path]
