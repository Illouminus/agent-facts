"""Invariant 1 (spec 00): no model API in the check() path, not even an import."""

import ast
from pathlib import Path

import agentfacts.api

FORBIDDEN = ("openai", "anthropic", "google.genai", "google.generativeai", "litellm", "cohere")
API_DIR = Path(agentfacts.api.__file__).parent


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_api_package_imports_no_model_sdk():
    sources = sorted(API_DIR.glob("*.py"))
    assert sources, API_DIR
    for path in sources:
        bad = {n for n in _imports(path) if n.startswith(FORBIDDEN)}
        assert not bad, f"{path.name} imports {bad}"
