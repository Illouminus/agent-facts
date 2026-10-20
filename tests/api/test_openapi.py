"""The published contract: docs/specs/openapi-v0.json is exactly what the app serves.

Regenerate after an intended API change with:
    AGENTFACTS_WRITE_OPENAPI=1 uv run pytest -q tests/api/test_openapi.py
"""

import json
import os
from pathlib import Path

from agentfacts.api.app import create_app

OPENAPI = Path(__file__).parents[2] / "docs" / "specs" / "openapi-v0.json"


def _render() -> str:
    return json.dumps(create_app().openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def test_openapi_document_is_committed_and_current():
    rendered = _render()
    if os.environ.get("AGENTFACTS_WRITE_OPENAPI") == "1":
        OPENAPI.write_text(rendered, encoding="utf-8")
    assert OPENAPI.is_file(), "missing docs/specs/openapi-v0.json; see this module's docstring"
    assert OPENAPI.read_text(encoding="utf-8") == rendered, (
        "docs/specs/openapi-v0.json is stale; see this module's docstring"
    )


def test_openapi_lists_the_spec_03_endpoints():
    paths = json.loads(OPENAPI.read_text(encoding="utf-8"))["paths"]
    assert set(paths) == {
        "/v0/check",
        "/v0/facts/{service}",
        "/v0/facts/{service}/{slug}",
        "/v0/services",
        "/healthz",
    }
    assert set(paths["/v0/check"]) == {"post"}
    assert set(paths["/v0/check"]["post"]["responses"]) == {"200", "400", "413", "429"}
    assert all("422" not in op["responses"] for ops in paths.values() for op in ops.values())
