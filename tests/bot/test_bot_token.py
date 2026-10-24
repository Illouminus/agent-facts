"""The bot's own token (sec card 2026-10-23, variant 1, D-089): read by name, passed to gh as
GH_TOKEN and to git through an env-only credential helper that overrides the host's personal
`gh auth git-credential`; never in argv or error messages; missing → a clear refusal."""

import os
import subprocess
from datetime import date

import pytest
from bot_repo import FAKE_BOT_TOKEN, Checkout, FakeGh
from typer.testing import CliRunner

import agentfacts.bot.token as token_mod
from agentfacts.bot.pr import gh_cli, publish
from agentfacts.bot.token import BotAuth, MissingToken
from agentfacts.cli import app

TODAY = date(2026, 10, 24)
DRAFT_FROM = "facts/stripe/idempotency-key-reuse-different-params.yaml"


@pytest.fixture
def repo(tmp_path) -> Checkout:
    checkout = Checkout(tmp_path)
    checkout.write("facts/stripe/second.yaml", checkout.show("main", DRAFT_FROM).replace(
        "af:stripe:idempotency-key-reuse-different-params", "af:stripe:second"))
    return checkout


def test_load_reads_the_key_by_name(bot_keys):
    assert BotAuth.load().token == FAKE_BOT_TOKEN
    assert FAKE_BOT_TOKEN not in repr(BotAuth.load())


def test_missing_key_is_a_clear_error(bot_keys):
    (bot_keys / "agent-facts-bot.key").unlink()
    with pytest.raises(MissingToken) as exc:
        BotAuth.load()
    assert "keyput agent-facts-bot" in str(exc.value) and "personal gh login" in str(exc.value)


def test_git_helper_overrides_the_personal_gh_helper(tmp_path):
    """Real git: ~/.gitconfig names a personal helper for github.com (as on illouminus)."""
    home = tmp_path / "home"
    home.mkdir()
    (home / ".gitconfig").write_text(
        '[credential "https://github.com"]\n\thelper = \n'
        '\thelper = "!f() { echo username=owner; echo password=PERSONAL; }; f"\n')
    base = {"HOME": str(home), "PATH": os.environ["PATH"], "GIT_CONFIG_NOSYSTEM": "1",
            "GH_TOKEN": "PERSONAL_ENV"}

    def fill(env):
        done = subprocess.run(["git", "credential", "fill"], env=env, cwd=home, check=False,
                              input="protocol=https\nhost=github.com\n\n", capture_output=True,
                              text=True)
        return done.stdout + done.stderr

    assert "password=PERSONAL" in fill(base)  # the trap the bot must avoid
    assert f"password={FAKE_BOT_TOKEN}" in fill(BotAuth(FAKE_BOT_TOKEN).git_env(base))
    anonymous = fill(BotAuth.anonymous().git_env(base))
    assert "PERSONAL" not in anonymous and "terminal prompts disabled" in anonymous


def test_the_helper_carries_no_token_in_config():
    env = BotAuth(FAKE_BOT_TOKEN).git_env({"GIT_CONFIG_COUNT": "5", "GITHUB_TOKEN": "x"})
    assert env["GIT_CONFIG_COUNT"] == "2" and env["GIT_CONFIG_VALUE_0"] == ""
    helper = env["GIT_CONFIG_VALUE_1"]
    assert FAKE_BOT_TOKEN not in helper and "$GH_TOKEN" in helper
    assert env["GH_TOKEN"] == FAKE_BOT_TOKEN and "GITHUB_TOKEN" not in env


def fake_gh(tmp_path, body):
    exe = tmp_path / "gh"
    exe.write_text(f"#!/bin/sh\n{body}\n")
    exe.chmod(0o755)
    return exe


def test_gh_gets_the_token_in_env_not_argv(tmp_path, monkeypatch):
    seen = tmp_path / "seen"
    monkeypatch.setenv("AGENTFACTS_GH", str(fake_gh(
        tmp_path, f'echo "$GH_TOKEN|$GH_PROMPT_DISABLED|$*" > {seen}')))
    monkeypatch.setenv("GH_TOKEN", "PERSONAL_ENV")
    gh_cli(tmp_path, BotAuth(FAKE_BOT_TOKEN))(["pr", "list"])
    assert seen.read_text().strip() == f"{FAKE_BOT_TOKEN}|1|pr list"


def test_gh_error_never_shows_the_token(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTFACTS_GH", str(fake_gh(
        tmp_path, 'echo "HTTP 401: bad credentials $GH_TOKEN" >&2; exit 1')))
    with pytest.raises(token_mod.GitError) as exc:
        gh_cli(tmp_path, BotAuth(FAKE_BOT_TOKEN))(["pr", "list"])
    assert "HTTP 401" in str(exc.value) and FAKE_BOT_TOKEN not in str(exc.value)


def test_remote_git_calls_carry_the_bot_helper(repo, monkeypatch):
    calls = []
    real = token_mod.git

    def spy(root, *args, env=None):
        calls.append((args[0], env))
        return real(root, *args, env=env)

    monkeypatch.setattr(token_mod, "git", spy)
    gh = FakeGh()
    report = publish(repo.work, today=TODAY, environ={}, gh=gh)
    assert report.action == "opened"
    assert {verb for verb, _ in calls} == {"fetch", "ls-remote", "push"}
    for _, env in calls:
        assert env["GH_TOKEN"] == FAKE_BOT_TOKEN and env["GIT_CONFIG_VALUE_0"] == ""
    assert not any(FAKE_BOT_TOKEN in arg for call in gh.calls for arg in call)


def test_publish_without_the_key_refuses_before_any_remote_call(repo, bot_keys):
    (bot_keys / "agent-facts-bot.key").unlink()
    gh = FakeGh()
    with pytest.raises(MissingToken):
        publish(repo.work, today=TODAY, environ={}, gh=gh)
    assert gh.calls == [] and repo.remote_branches() == ["main"]


def test_dry_run_needs_no_key(repo, bot_keys):
    (bot_keys / "agent-facts-bot.key").unlink()
    assert publish(repo.work, today=TODAY, environ={}, dry_run=True).action == "would-open"


def test_cli_missing_key_is_exit_1_with_the_message(repo, bot_keys):
    (bot_keys / "agent-facts-bot.key").unlink()
    r = CliRunner().invoke(app, ["bot", "publish", "--root", str(repo.work)],
                           env={"AGENTFACTS_KILL": "0"})
    assert r.exit_code == 1 and "keyput agent-facts-bot" in r.output


def test_git_env_keeps_unrelated_git_config_variables():
    base = {"GIT_CONFIG_GLOBAL": "/tmp/g", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_PARAMETERS": "x",
            "GIT_CONFIG_COUNT": "3", "GIT_CONFIG_KEY_2": "a", "GIT_CONFIG_VALUE_2": "b"}
    env = BotAuth(FAKE_BOT_TOKEN).git_env(base)
    assert {k: env[k] for k in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM",
                                "GIT_CONFIG_PARAMETERS")} == {
        "GIT_CONFIG_GLOBAL": "/tmp/g", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_PARAMETERS": "x"}
    assert env["GIT_CONFIG_COUNT"] == "2" and "GIT_CONFIG_KEY_2" not in env


def test_redaction_keeps_shas_readable():
    sha = "c2567507c886bc075b4f3ddd154338271b273fdf"
    out = BotAuth(FAKE_BOT_TOKEN).redact(f"push {sha} with {FAKE_BOT_TOKEN} refused")
    assert sha in out and FAKE_BOT_TOKEN not in out


def test_redaction_also_hides_other_github_credentials():
    other = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4"
    pat = "github_pat_" + "11ABCDEFG0123456789_abcdefXYZ"
    text = f"fatal: https://owner:{other}@github.com/x.git {pat} anon"
    for auth in (BotAuth(FAKE_BOT_TOKEN), BotAuth.anonymous()):
        out = auth.redact(text)
        assert other not in out and pat not in out and "owner:" not in out
        assert "https://[redacted]@github.com/x.git" in out
