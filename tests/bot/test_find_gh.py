"""`find_gh` resolves the gh binary when PATH lacks it (systemd user units on the host)."""

import os
import stat
from pathlib import Path

import pytest

from agentfacts.bot.pr import GitError, find_gh


def _fake_gh(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    exe = directory / "gh"
    exe.write_text("#!/bin/sh\nexit 0\n")
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    return exe


def test_explicit_env_wins(tmp_path: Path) -> None:
    assert find_gh({"AGENTFACTS_GH": "/opt/x/gh", "PATH": str(tmp_path)}) == "/opt/x/gh"


def test_path_lookup(tmp_path: Path) -> None:
    exe = _fake_gh(tmp_path / "bin")
    assert find_gh({"PATH": str(tmp_path / "bin"), "HOME": str(tmp_path)}) == str(exe)


def test_falls_back_to_user_local_bin_when_path_is_minimal(tmp_path: Path) -> None:
    exe = _fake_gh(tmp_path / ".local" / "bin")
    assert find_gh({"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}) == str(exe)


def test_missing_gh_raises(tmp_path: Path) -> None:
    with pytest.raises(GitError, match="gh not found"):
        find_gh({"PATH": str(tmp_path / "empty"), "HOME": str(tmp_path)})


def test_non_executable_candidate_is_skipped(tmp_path: Path) -> None:
    exe = _fake_gh(tmp_path / ".local" / "bin")
    exe.chmod(stat.S_IRUSR | stat.S_IWUSR)
    assert not os.access(exe, os.X_OK)
    with pytest.raises(GitError):
        find_gh({"PATH": str(tmp_path / "empty"), "HOME": str(tmp_path)})
