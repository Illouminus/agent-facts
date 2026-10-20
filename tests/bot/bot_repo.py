"""A runner checkout for bot tests: real git, a local bare `origin`, a recording fake `gh`.

Imported as `bot_repo` (tests/ is no package). No network: `origin` is a directory."""

import json
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

from agentfacts.pages.build import build_pages, load_registry, sync

VALID = Path(__file__).parents[1] / "fixtures" / "valid"
GIT_ENV_USER = ("-c", "user.name=Test", "-c", "user.email=test@example.invalid")


def sh(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *GIT_ENV_USER, *args], cwd=cwd, check=True,
                          capture_output=True, text=True).stdout


class Checkout:
    """`work` cloned from `origin.git`, seeded with the W1 fixtures and their pages."""

    def __init__(self, tmp: Path):
        self.origin = tmp / "origin.git"
        self.work = tmp / "work"
        sh(tmp, "init", "--quiet", "--bare", "-b", "main", str(self.origin))
        sh(tmp, "init", "--quiet", "-b", "main", str(self.work))
        for src, dst in [
            ("service-stripe.yaml", "services/stripe.yaml"),
            ("probe-idempotency-key-reuse.yaml", "probes/stripe/idempotency-key-reuse.yaml"),
            ("fact-idempotency-key-reuse-different-params.yaml",
             "facts/stripe/idempotency-key-reuse-different-params.yaml"),
        ]:
            (self.work / dst).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(VALID / src, self.work / dst)
        (self.work / "agentfacts").mkdir()
        (self.work / "agentfacts" / "code.py").write_text("x = 1\n")
        sync(self.work / "pages", build_pages(*load_registry(self.work)))
        sh(self.work, "add", "-A")
        sh(self.work, "commit", "--quiet", "-m", "seed")
        sh(self.work, "remote", "add", "origin", str(self.origin))
        sh(self.work, "push", "--quiet", "-u", "origin", "main")
        sh(self.work, "fetch", "--quiet", "origin")

    def write(self, rel: str, text: str) -> Path:
        path = self.work / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def remote_branches(self) -> list[str]:
        out = sh(self.origin, "for-each-ref", "--format=%(refname:short)", "refs/heads")
        return sorted(out.split())

    def show(self, ref: str, rel: str) -> str:
        return sh(self.origin, "show", f"{ref}:{rel}")

    def files_in(self, ref: str) -> list[str]:
        return sh(self.origin, "diff", "--name-only", "main", ref).split()

    def push_to_main_from_elsewhere(self, rel: str, text: str, tmp: Path) -> None:
        other = tmp / "other"
        sh(tmp, "clone", "--quiet", str(self.origin), str(other))
        (other / rel).write_text(text, encoding="utf-8")
        sh(other, "commit", "--quiet", "-am", "human edit")
        sh(other, "push", "--quiet", "origin", "main")


class FakeGh:
    """Records every `gh` call; answers `pr list` with `open_prs` and `pr create` with a URL."""

    def __init__(self, open_prs: Sequence[dict] = ()):
        self.calls: list[list[str]] = []
        self.open_prs = list(open_prs)

    def __call__(self, args: Sequence[str]) -> str:
        args = list(args)
        self.calls.append(args)
        if args[:2] == ["pr", "list"]:
            return json.dumps(self.open_prs)
        if args[:2] == ["pr", "create"]:
            return "https://github.com/Illouminus/agent-facts/pull/99\n"
        return ""

    def verbs(self) -> list[str]:
        return [" ".join(c[:2]) for c in self.calls]
