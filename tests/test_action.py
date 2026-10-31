"""The composite action's script, run with bash and a stub `uvx` (no workflow, no network).

The two promises: the step ends with the command's own exit code (pass or fail), and the scan never
changes it, even when it crashes or cannot be installed.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from apifacts import __version__

ACTION = Path(__file__).parent.parent / "action" / "action.yml"
pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")


def action():
    return yaml.safe_load(ACTION.read_text(encoding="utf-8"))


def test_metadata():
    doc = action()
    assert doc["runs"]["using"] == "composite"
    assert set(doc["branding"]) == {"icon", "color"}
    assert set(doc["inputs"]) == {"run", "log-file", "offline", "version"}
    # the pinned default follows the release (ops/README.md: one version for every package)
    assert doc["inputs"]["version"]["default"] == __version__
    (step,) = doc["runs"]["steps"]
    assert "${{" not in step["run"]  # inputs reach the script through env only


@pytest.fixture
def run_action(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls.txt"

    def stub(exit_code):
        uvx = bin_dir / "uvx"
        uvx.write_text(
            "#!/bin/sh\n"
            f'echo "$@" >> "{calls}"\n'
            'for last; do :; done; cat "$last" >> "' + str(calls) + '"\n'
            f"exit {exit_code}\n"
        )
        uvx.chmod(0o755)

    def run(scan_exit=0, **inputs):
        stub(scan_exit)
        env = {
            "PATH": f"{bin_dir}{os.pathsep}/usr/bin{os.pathsep}/bin",
            "RUNNER_TEMP": str(tmp_path),
            "APIFACTS_ACTION_VERSION": __version__,
            **{f"APIFACTS_ACTION_{k.upper()}": v for k, v in inputs.items()},
        }
        (step,) = action()["runs"]["steps"]
        done = subprocess.run(
            ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", step["run"]],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        scanned = calls.read_text() if calls.exists() else ""
        calls.unlink(missing_ok=True)
        return done, scanned

    return run


def test_failing_command_keeps_its_code_and_is_scanned(run_action):
    done, scanned = run_action(run="echo 'HTTP 404: Not Found (https://api.github.com/x)'; exit 7")
    assert done.returncode == 7
    assert "HTTP 404: Not Found" in done.stdout  # tee'd, the log looks as without the action
    assert scanned.startswith(f"--quiet --from apifacts=={__version__} apifacts scan --github ")
    assert "HTTP 404: Not Found (https://api.github.com/x)" in scanned


def test_pipefail_inside_the_command(run_action):
    done, scanned = run_action(run="false | cat")
    assert done.returncode == 1 and scanned


def test_passing_command_is_not_scanned(run_action):
    done, scanned = run_action(run="echo fine")
    assert done.returncode == 0 and done.stdout == "fine\n"
    assert scanned == ""


def test_a_crashing_scan_changes_nothing(run_action):
    done, _ = run_action(scan_exit=2, run="exit 3")
    assert done.returncode == 3
    assert "::notice title=apifacts::scan did not complete (exit 2)" in done.stdout
    done, _ = run_action(scan_exit=2, **{"log": "/dev/null"})
    assert done.returncode == 0


def test_log_file_mode_always_succeeds(run_action, tmp_path):
    log = tmp_path / "pytest.log"
    log.write_text("401 Client Error: Unauthorized for url: https://api.stripe.com/v1/charges\n")
    done, scanned = run_action(log=str(log), offline="true")
    assert done.returncode == 0
    assert "scan --github --offline " in scanned
    done, scanned = run_action(log=str(tmp_path / "missing.log"))
    assert done.returncode == 0 and scanned == ""
    assert "no log file" in done.stdout


def test_no_input_is_a_warning_not_a_failure(run_action):
    done, scanned = run_action()
    assert done.returncode == 0 and scanned == ""
    assert done.stdout.startswith("::warning title=apifacts::")
