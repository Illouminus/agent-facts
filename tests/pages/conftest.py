"""Fixture registry for the page tests: files from tests/fixtures/valid laid out as a repo."""

import shutil
from pathlib import Path

import pytest

from apifacts.schema.yamlio import load_yaml

VALID = Path(__file__).parents[1] / "fixtures" / "valid"
GOLDEN = Path(__file__).parent / "golden"

# Explicit, so fixtures other packages add to tests/fixtures/valid do not change the W5 goldens.
SERVICE_FILES = ("service-stripe.yaml", "service-example.yaml")
FACT_FILES = (
    "fact-idempotency-key-reuse-different-params.yaml",
    "fact-idempotency-key-reuse-sandbox.yaml",
    "fact-customer-retrieve-rate-limit.yaml",
    "fact-payment-intent-lock-timeout-expired.yaml",
    "fact-deleted-customer-returns-200.yaml",
    "fact-amount-too-small-retracted.yaml",
    "fact-example-sdk-v2-legacy-endpoint.yaml",
)
PROBE_FILES = ("probe-idempotency-key-reuse.yaml", "probe-deleted-customer.yaml")


def lay_out(root: Path) -> Path:
    """Copy the fixture set into `root` as services/<key>.yaml, facts/<service>/<slug>.yaml and
    probes/<service>/<slug>.yaml."""
    for name in SERVICE_FILES:
        key = load_yaml(VALID / name)["key"]
        (root / "services").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(VALID / name, root / "services" / f"{key}.yaml")
    for name in FACT_FILES:
        _, service, slug = load_yaml(VALID / name)["id"].split(":", 2)
        (root / "facts" / service).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(VALID / name, root / "facts" / service / f"{slug}.yaml")
    for name in PROBE_FILES:
        _, service, _, slug = load_yaml(VALID / name)["id"].split(":", 3)
        (root / "probes" / service).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(VALID / name, root / "probes" / service / f"{slug}.yaml")
    return root


@pytest.fixture
def fixture_root(tmp_path: Path) -> Path:
    return lay_out(tmp_path / "repo")
