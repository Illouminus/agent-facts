"""systemd user units in ops/systemd say what spec 08 and the W8 plan say."""

import configparser
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
UNITS = ROOT / "ops" / "systemd"
APP = "%h/apps/agent-facts"


def unit(name: str) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(strict=False, interpolation=None, delimiters=("=",))
    parser.optionxform = str  # keys are case-sensitive in systemd
    parser.read_string((UNITS / name).read_text(encoding="utf-8"))
    return parser


def environment(name: str) -> dict[str, str]:
    """`Environment=` lines, one variable each (configparser would keep only the last one)."""
    raw = (UNITS / name).read_text(encoding="utf-8")
    return dict(re.findall(r"^Environment=(\w+)=(\S+)$", raw, flags=re.M))


def test_api_service_runs_one_quiet_local_worker():
    exec_start = unit("agentfacts-api.service")["Service"]["ExecStart"]
    assert exec_start.startswith(f"{APP}/.venv/bin/uvicorn agentfacts.api.app:app")
    for flag in ("--workers 1", "--no-access-log", "--host 127.0.0.1", "--port 8795"):
        assert flag in exec_start


def test_api_service_environment():
    env = environment("agentfacts-api.service")
    assert env == {
        "AGENTFACTS_REPO": APP,
        "AGENTFACTS_DB": f"{APP}/var/observations.sqlite",
        "AGENTFACTS_TRUSTED_PROXIES": "127.0.0.1,::1",
    }


def test_api_service_restarts_and_is_wanted_by_default_target():
    api = unit("agentfacts-api.service")
    assert api["Service"]["Restart"] == "on-failure"
    assert api["Install"]["WantedBy"] == "default.target"


def test_probe_timer_every_15_minutes():
    timer = unit("agentfacts-probe.timer")["Timer"]
    assert timer["OnCalendar"] == "*:0/15"
    assert timer["Unit"] == "agentfacts-probe.service"


def test_probe_service_runs_due_probes_from_illouminus():
    service = unit("agentfacts-probe.service")["Service"]
    assert service["Type"] == "oneshot"
    assert service["ExecStart"] == (
        f"{APP}/.venv/bin/agentfacts probe run --due --max 50 --vantage illouminus --root {APP}"
    )


def test_digest_timer_monday_8_paris():
    timer = unit("agentfacts-digest.timer")["Timer"]
    assert timer["OnCalendar"] == "Mon *-*-* 08:00:00 Europe/Paris"
    assert timer["Persistent"] == "true"


def test_digest_service_runs_ops_digest():
    service = unit("agentfacts-digest.service")["Service"]
    assert service["ExecStart"] == f"{APP}/.venv/bin/python {APP}/ops/digest.py --root {APP}"


def test_quorum_service_puts_user_local_bin_on_path():
    # systemd user units get a minimal PATH; gh lives in ~/.local/bin on illouminus (2026-10-20)
    text = (UNITS / "agentfacts-quorum.service").read_text(encoding="utf-8")
    assert "Environment=PATH=%h/.local/bin:" in text
    assert "NOT ENABLED" not in text


def test_quorum_service_reads_the_api_database():
    exec_start = unit("agentfacts-quorum.service")["Service"]["ExecStart"]
    assert f"quorum run --root {APP} --db {APP}/var/observations.sqlite" in exec_start
    assert f"bot publish --root {APP}" in exec_start


def test_quorum_timer_hourly():
    assert unit("agentfacts-quorum.timer")["Timer"]["OnCalendar"] == "hourly"


@pytest.mark.parametrize("name", sorted(p.name for p in UNITS.glob("agentfacts-*")))
def test_no_unit_touches_keys_or_model_apis(name):
    text = (UNITS / name).read_text(encoding="utf-8").lower()
    for needle in ("private_keys", "anthropic", "openai", "gemini", "api_key"):
        assert needle not in text


@pytest.mark.parametrize("name", sorted(p.name for p in UNITS.glob("agentfacts-*.timer")))
def test_every_timer_has_a_service(name):
    assert (UNITS / name.replace(".timer", ".service")).exists()


def test_kill_file_is_ignored_by_git():
    result = subprocess.run(
        ["git", "check-ignore", "-q", "ops/KILL"], cwd=ROOT, check=False
    )
    assert result.returncode == 0
