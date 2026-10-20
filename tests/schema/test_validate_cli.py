"""`agentfacts validate [paths]`: exit 0 ok, 1 invalid (`file:line: code message`), 2 usage."""

import re
from pathlib import Path

from typer.testing import CliRunner

from agentfacts.cli import app

FIXTURES = Path(__file__).parents[1] / "fixtures"
PROBLEM_LINE = re.compile(r"^.+:\d+: [a-z_]+ .+$")

runner = CliRunner()


def test_valid_fixtures_exit_0():
    result = runner.invoke(app, ["validate", str(FIXTURES / "valid")])
    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert "ok: 3 files (1 fact, 1 probe, 1 service)" in result.stderr


def test_invalid_fixtures_exit_1_with_one_problem_per_line():
    result = runner.invoke(app, ["validate", str(FIXTURES / "valid"), str(FIXTURES / "invalid")])
    assert result.exit_code == 1
    lines = result.stdout.splitlines()
    assert len(lines) >= 5
    assert all(PROBLEM_LINE.match(line) for line in lines), lines
    assert "problems in 5 of 8 files" in result.stderr


def test_missing_path_is_a_usage_error():
    result = runner.invoke(app, ["validate", "does/not/exist"])
    assert result.exit_code == 2
    assert "no such path" in result.stderr


def test_no_paths_validates_the_registry_dirs_under_root(tmp_path):
    result = runner.invoke(app, ["validate", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "ok: 0 files" in result.stderr

    (tmp_path / "facts").mkdir()
    (tmp_path / "facts" / "bad.yaml").write_text("kind: nope\n", encoding="utf-8")
    result = runner.invoke(app, ["validate", "--root", str(tmp_path)])
    assert result.exit_code == 1
    assert "bad.yaml:1: " in result.stdout


def test_unknown_option_is_a_usage_error():
    assert runner.invoke(app, ["validate", "--nope"]).exit_code == 2
