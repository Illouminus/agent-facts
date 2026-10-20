from typer.testing import CliRunner

from agentfacts import __version__
from agentfacts.cli import app

runner = CliRunner()


def test_version_prints_package_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_help_lists_version_command():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "version" in result.stdout


def test_no_command_is_a_usage_error():
    result = runner.invoke(app, [])
    assert result.exit_code == 2
