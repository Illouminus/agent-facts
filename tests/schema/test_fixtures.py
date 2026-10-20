"""Spec 01 Done-when: valid fixtures pass; each invalid fixture is rejected with its code."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from agentfacts.schema.models import Fact, Probe
from agentfacts.schema.validate import validate_paths
from agentfacts.schema.yamlio import load_yaml, plain

FIXTURES = Path(__file__).parents[1] / "fixtures"
VALID = FIXTURES / "valid"
INVALID = FIXTURES / "invalid"

EXPECTED = {
    "free-text-fix.yaml": {"fix_invalid"},
    "unregistered-path-template.yaml": {"unregistered_template"},
    "prod-probe-post.yaml": {"prod_probe_not_readonly"},
    "claim-too-long.yaml": {"claim_too_long"},
    "unknown-kind.yaml": {"unknown_kind"},
}

# Rejected by the JSON Schema alone, so the pydantic mirror must reject them too.
SCHEMA_LEVEL = {
    "free-text-fix.yaml": Fact,
    "claim-too-long.yaml": Fact,
    "unknown-kind.yaml": Fact,
    "prod-probe-post.yaml": Probe,
}


def test_valid_fixtures_pass(tmp_path):
    report = validate_paths([VALID], root=tmp_path)
    assert [str(p) for p in report.problems] == []
    assert report.files == len(list(VALID.glob("*.yaml")))


def test_every_invalid_fixture_has_an_expectation():
    assert {p.name for p in INVALID.glob("*.yaml")} == set(EXPECTED)


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_invalid_fixture_rejected_with_code(name, tmp_path):
    report = validate_paths([VALID, INVALID / name], root=tmp_path)
    assert {p.code for p in report.problems} == EXPECTED[name], [str(p) for p in report.problems]
    assert {p.file.name for p in report.problems} == {name}


@pytest.mark.parametrize("name", sorted(SCHEMA_LEVEL))
def test_model_rejects_schema_level_fixture(name):
    with pytest.raises(ValidationError):
        SCHEMA_LEVEL[name].model_validate(plain(load_yaml(INVALID / name)))


def _line_starting(path: Path, prefix: str) -> int:
    lines = path.read_text(encoding="utf-8").splitlines()
    return next(i for i, line in enumerate(lines, 1) if line.startswith(prefix))


@pytest.mark.parametrize(
    ("name", "prefix"),
    [
        ("claim-too-long.yaml", "claim:"),
        ("unknown-kind.yaml", "kind:"),
        ("free-text-fix.yaml", '  - "Regenerate'),
        ("unregistered-path-template.yaml", "  path_template:"),
        (
            "prod-probe-post.yaml",
            "  - {do: http, method: POST, path: /v1/payment_intents, form: {amount: 100",
        ),
    ],
)
def test_problem_points_at_the_offending_line(name, prefix, tmp_path):
    problems = validate_paths([VALID, INVALID / name], root=tmp_path).problems
    problem = problems[0]  # sorted by line: the first offending step for the prod probe
    assert problem.line == _line_starting(INVALID / name, prefix)
    assert str(problem).startswith(f"{INVALID / name}:{problem.line}: {problem.code} ")
