"""The bot's own GitHub token (sec card 2026-10-23, variant 1, D-089).

A fine-grained PAT that reaches only Illouminus/agent-facts (Contents + Pull requests RW), placed
with `keyput agent-facts-bot` at `~/.private_keys/agent-facts-bot.key` and read by name like the
probe keys (`probe.keys.read_key`). The bot never falls back to the host's personal `gh` login,
which opens every repository of the owner: `gh` gets the token as `GH_TOKEN`; git gets it through
an env-only credential helper that first resets every configured helper (on illouminus
`~/.gitconfig` has `gh auth git-credential` for github.com). The value never reaches argv, logs
or error messages (redacted). A dry run needs no token: its git calls go anonymous.
"""

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from agentfacts.bot.collect import GitError, git
from agentfacts.probe.keys import DEFAULT_KEYS_DIR, key_path, read_key
from agentfacts.probe.redact import REDACTED, Redactor

BOT_KEY = "agent-facts-bot"
# Reads the token from the environment git passes to the helper: the value is not in git's config
# or argv. `get` only; `store`/`erase` are no-ops.
_HELPER = ('!f() { test "$1" = get || exit 0; echo username=x-access-token; '
           'echo "password=$GH_TOKEN"; }; f')


# Any GitHub token shape or URL credentials, whoever's they are (a git/gh error could echo the
# owner's token from another source); SHAs stay readable (no generic hex rule).
_GITHUB_SECRETS = (
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), REDACTED),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), REDACTED),
    (re.compile(r"(https?://)[^/@\s:]+:[^/@\s]+@"), rf"\1{REDACTED}@"),
)


class MissingToken(GitError):
    pass


@dataclass(frozen=True, repr=False)
class BotAuth:
    token: str | None  # None: anonymous (dry runs)

    def __repr__(self) -> str:  # never print the token by accident
        return f"BotAuth({'token' if self.token else 'anonymous'})"

    @classmethod
    def load(cls, keys_dir: Path | None = None) -> "BotAuth":
        keys_dir = DEFAULT_KEYS_DIR if keys_dir is None else keys_dir
        token = read_key(BOT_KEY, keys_dir)
        if token is None:
            raise MissingToken(
                f"no bot token: {key_path(BOT_KEY, keys_dir)} is missing or empty; put the "
                f"fine-grained PAT with `keyput {BOT_KEY}`. The bot never uses the personal gh "
                "login of the host (D-089)."
            )
        return cls(token)

    @classmethod
    def anonymous(cls) -> "BotAuth":
        return cls(None)

    def gh_env(self, base: Mapping[str, str]) -> dict[str, str]:
        env = {k: v for k, v in base.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN")}
        if self.token:
            env["GH_TOKEN"] = self.token
        env["GH_PROMPT_DISABLED"] = "1"
        return env

    def git_env(self, base: Mapping[str, str]) -> dict[str, str]:
        env = {k: v for k, v in base.items()
               if k not in ("GH_TOKEN", "GITHUB_TOKEN", "GIT_CONFIG_COUNT")
               and not k.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))}
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GIT_CONFIG_COUNT"] = "2" if self.token else "1"
        env["GIT_CONFIG_KEY_0"], env["GIT_CONFIG_VALUE_0"] = "credential.helper", ""  # reset
        if self.token:
            env["GIT_CONFIG_KEY_1"], env["GIT_CONFIG_VALUE_1"] = "credential.helper", _HELPER
            env["GH_TOKEN"] = self.token
        return env

    def redact(self, text: str) -> str:
        if self.token:
            text = Redactor.for_keys([self.token]).text_strict(text)
        for pattern, replacement in _GITHUB_SECRETS:
            text = pattern.sub(replacement, text)
        return text

    def git(self, root: Path, *args: str) -> str:
        """git that talks to the remote (fetch, ls-remote, push) with this token only."""
        try:
            return git(root, *args, env=self.git_env(os.environ))
        except GitError as exc:
            raise GitError(self.redact(str(exc))) from None
