"""ops/deploy.sh against a throwaway origin + checkout. `uv`, `systemctl` and `curl` are stubs
in `$HOME/.local/bin` (first on the PATH the script pins); git is real. Runs under macOS bash 3.2
too."""

import fcntl
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from ops_builders import REPO

STUB_LOG = """#!/bin/sh
echo "$(basename "$0") $*" >> "$HOME/calls.log"
"""
CURL = STUB_LOG + """[ -e "$AF_APP/BROKEN" ] && exit 22
echo '{"ok":true,"registry_version":"2026-10-20","probes_last_run":null}'
"""
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
       "-c", "init.defaultBranch=main"]


def git(cwd: Path, *args: str) -> str:
    return subprocess.run([*GIT, *args], cwd=cwd, check=True, capture_output=True,
                          text=True).stdout.strip()


class Host:
    """origin.git + a work clone that commits + the deployed checkout `app` (detached at c1)."""

    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.home = tmp / "home"
        bin_dir = self.home / ".local" / "bin"
        bin_dir.mkdir(parents=True)
        for name, body in (("uv", STUB_LOG), ("systemctl", STUB_LOG), ("curl", CURL)):
            (bin_dir / name).write_text(body, encoding="utf-8")
            (bin_dir / name).chmod(0o755)
        self.origin = tmp / "origin.git"
        git(tmp, "init", "--bare", "-q", str(self.origin))
        self.work = tmp / "work"
        git(tmp, "clone", "-q", str(self.origin), str(self.work))
        self.write("ops/deploy.sh", (REPO / "ops" / "deploy.sh").read_text(encoding="utf-8"))
        (self.work / "ops" / "deploy.sh").chmod(0o755)
        self.write("ops/systemd/agentfacts-api.service", "[Service]\nExecStart=/bin/true\n")
        self.write("facts/s/a.yaml", "value: 1\nnote: a\n\n\n\n\nother: x\n")
        self.c1 = self.commit("c1")
        self.app = tmp / "app"
        git(tmp, "clone", "-q", str(self.origin), str(self.app))
        git(self.app, "checkout", "-q", "--detach", self.c1)

    def write(self, rel: str, text: str) -> None:
        path = self.work / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self, message: str, branch: str = "main") -> str:
        git(self.work, "add", "-A")
        git(self.work, "commit", "-q", "-m", message)
        git(self.work, "push", "-q", "origin", f"HEAD:{branch}")
        return git(self.work, "rev-parse", "HEAD")

    def deploy(self, *args: str, **env: str) -> subprocess.CompletedProcess:
        environ = {"HOME": str(self.home), "PATH": os.environ["PATH"], "AF_APP": str(self.app),
                   "AGENTFACTS_HEALTH_TRIES": "2", "AGENTFACTS_HEALTH_SLEEP": "0", **env}
        return subprocess.run(["bash", str(self.app / "ops" / "deploy.sh"), *args], env=environ,
                              capture_output=True, text=True, check=False)

    def head(self) -> str:
        return git(self.app, "rev-parse", "HEAD")

    def calls(self) -> list[str]:
        log = self.home / "calls.log"
        return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")


@pytest.fixture
def host(tmp_path: Path) -> Host:
    return Host(tmp_path)


def test_refuses_anything_but_40_hex(host):
    for bad in ("", "main", "; rm -rf ~", host.c1[:39], host.c1.upper()):
        result = host.deploy(bad)
        assert result.returncode == 2, (bad, result.stderr)
    assert host.head() == host.c1
    assert host.calls() == []


def test_refuses_a_sha_that_is_not_on_origin_main(host):
    host.write("README", "side\n")
    side = host.commit("side", branch="side")
    result = host.deploy(side)
    assert result.returncode == 2
    assert "not on origin/main (unknown commit)" in result.stdout
    git(host.app, "fetch", "-q", "origin", "side")  # known locally, still not on main
    result = host.deploy(side)
    assert result.returncode == 2
    assert f"{side} is not on origin/main\n" in result.stdout
    assert host.head() == host.c1


def test_deploys_a_main_sha_and_restarts_the_api(host):
    host.write("README", "two\n")
    c2 = host.commit("c2")
    result = host.deploy(c2)
    assert result.returncode == 0, result.stdout + result.stderr
    assert host.head() == c2
    calls = host.calls()
    assert "uv sync --frozen --no-dev --quiet" in calls
    assert "systemctl --user restart agentfacts-api.service" in calls
    assert not any("daemon-reload" in c for c in calls)
    assert (host.app / "var" / "deploy" / "deployed").read_text(encoding="utf-8").strip() == c2


def test_forced_command_passes_the_sha_in_ssh_original_command(host):
    host.write("README", "two\n")
    c2 = host.commit("c2")
    assert host.deploy(SSH_ORIGINAL_COMMAND=c2).returncode == 0
    assert host.head() == c2


def test_unhealthy_release_rolls_back_to_the_previous_sha(host):
    host.write("BROKEN", "1\n")
    c2 = host.commit("broken")
    result = host.deploy(c2)
    assert result.returncode == 1
    assert "rolled back" in result.stdout
    assert host.head() == host.c1
    assert host.calls().count("systemctl --user restart agentfacts-api.service") == 2


def test_daemon_reload_only_when_units_changed(host):
    host.write("ops/systemd/agentfacts-api.service", "[Service]\nExecStart=/bin/false\n")
    c2 = host.commit("units")
    assert host.deploy(c2).returncode == 0
    assert "systemctl --user daemon-reload" in host.calls()


def test_probe_edits_to_facts_survive_a_deploy(host):
    (host.app / "facts" / "s" / "a.yaml").write_text(
        "value: 1\nnote: a\n\n\n\n\nother: y\n", encoding="utf-8")
    host.write("README", "two\n")
    c2 = host.commit("c2")
    assert host.deploy(c2).returncode == 0
    assert host.head() == c2
    assert "other: y" in (host.app / "facts" / "s" / "a.yaml").read_text(encoding="utf-8")


def test_conflicting_facts_edit_is_parked_not_lost(host):
    (host.app / "facts" / "s" / "a.yaml").write_text(
        "value: 9\nnote: a\n\n\n\n\nother: x\n", encoding="utf-8")
    host.write("facts/s/a.yaml", "value: 2\nnote: a\n\n\n\n\nother: x\n")
    c2 = host.commit("c2")
    result = host.deploy(c2)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (host.app / "facts" / "s" / "a.yaml").read_text(encoding="utf-8").startswith("value: 2")
    (parked,) = (host.app / "var" / "deploy").glob("facts-unapplied-*.patch")
    assert "+value: 9" in parked.read_text(encoding="utf-8")


def test_same_sha_and_healthy_is_a_no_op(host):
    result = host.deploy(host.c1)
    assert result.returncode == 0
    assert "already deployed" in result.stdout
    assert host.calls() == ["curl -fsS -m 3 http://127.0.0.1:8795/healthz"]


def test_journal_hook_is_skipped_without_state_and_never_fails_the_deploy(host):
    host.write("README", "two\n")
    c2 = host.commit("c2")
    result = host.deploy(c2)
    assert result.returncode == 0
    assert "journal hook skipped" in result.stdout


def test_ssh_refuses_a_downgrade_but_by_hand_rollback_works(host):
    host.write("README", "two\n")
    c2 = host.commit("c2")
    assert host.deploy(SSH_ORIGINAL_COMMAND=c2).returncode == 0
    result = host.deploy(SSH_ORIGINAL_COMMAND=host.c1)
    assert result.returncode == 2
    assert "downgrade over ssh" in result.stdout
    assert host.head() == c2
    assert host.deploy(host.c1).returncode == 0  # by hand
    assert host.head() == host.c1


def test_untracked_files_under_facts_survive_a_deploy(host):
    (host.app / "facts" / "s" / "draft.yaml").write_text("draft: 1\n", encoding="utf-8")
    host.write("README", "two\n")
    c2 = host.commit("c2")
    assert host.deploy(c2).returncode == 0
    assert (host.app / "facts" / "s" / "draft.yaml").read_text(encoding="utf-8") == "draft: 1\n"


def test_untracked_draft_that_main_now_tracks_is_parked(host):
    (host.app / "facts" / "s" / "draft.yaml").write_text("draft: host\n", encoding="utf-8")
    host.write("facts/s/draft.yaml", "draft: merged\n")
    c2 = host.commit("c2")
    assert host.deploy(c2).returncode == 0
    assert (host.app / "facts" / "s" / "draft.yaml").read_text(encoding="utf-8") == \
        "draft: merged\n"
    (parked,) = (host.app / "var" / "deploy").glob("facts-unapplied-*.patch")
    assert "+draft: host" in parked.read_text(encoding="utf-8")


@pytest.mark.skipif(shutil.which("flock") is None, reason="flock(1) only on Linux")
def test_waits_for_a_running_probe_tick_then_gives_up(host):
    host.write("README", "two\n")
    c2 = host.commit("c2")
    (host.app / "var").mkdir(exist_ok=True)
    with (host.app / "var" / "probe.lock").open("a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)  # what the runner does during a tick
        result = host.deploy(c2, AGENTFACTS_PROBE_LOCK_WAIT="1")
    assert result.returncode == 75
    assert host.head() == host.c1


def test_edits_that_main_already_has_are_dropped_not_parked(host):
    edited = "value: 1\nnote: a\n\n\n\n\nother: bot\n"
    (host.app / "facts" / "s" / "a.yaml").write_text(edited, encoding="utf-8")
    (host.app / "facts" / "s" / "draft.yaml").write_text("draft: 1\n", encoding="utf-8")
    host.write("facts/s/a.yaml", edited)  # the bot's PR, merged
    host.write("facts/s/draft.yaml", "draft: 1\n")
    c2 = host.commit("bot facts")
    result = host.deploy(c2)
    assert result.returncode == 0
    assert "already in" in result.stdout
    assert list((host.app / "var" / "deploy").glob("facts-unapplied-*.patch")) == []
    assert git(host.app, "status", "--porcelain", "--", "facts") == ""
