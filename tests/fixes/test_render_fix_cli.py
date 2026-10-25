"""`apifacts render-fix <json>`: one sentence, exit 1 on an invalid fix, 2 on non-JSON."""

from typer.testing import CliRunner

from apifacts.cli import app

runner = CliRunner()


def test_renders_one_sentence():
    result = runner.invoke(
        app, ["render-fix", '{"action": "none_known", "reason_kind": "by_design"}']
    )
    assert result.exit_code == 0
    assert result.stdout == "No client-side fix known (by design)\n"


def test_free_text_is_rejected():
    result = runner.invoke(app, ["render-fix", '"just retry later"'])
    assert result.exit_code == 1
    assert "fix_invalid" in result.stdout


def test_unknown_action_is_rejected():
    result = runner.invoke(app, ["render-fix", '{"action": "run_shell", "command": "ls"}'])
    assert result.exit_code == 1
    assert "unknown_fix_action" in result.stdout


def test_not_json_is_a_usage_error():
    result = runner.invoke(app, ["render-fix", "{action: none_known"])
    assert result.exit_code == 2
    assert "not valid JSON" in result.stderr
