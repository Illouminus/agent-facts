"""GitHub Actions output for `apifacts scan --github`: annotations and the job summary (spec 07).

Annotations (`::warning …::`) show on the run page and the PR's "Files changed" checks panel; the
step summary is markdown appended to `$GITHUB_STEP_SUMMARY`. Coding agents that fix CI read both.

Escaping follows the runner's own rules (actions/toolkit `command.ts`): in the message `%`, `\\r`,
`\\n` become `%25`, `%0D`, `%0A`; in a property value (`title=`) `:` and `,` are escaped as well.
The summary puts every server string inside a code fence longer than any backtick run in it, so a
claim can never turn into markdown, HTML or a link.
"""

import os
import re
from pathlib import Path

_BACKTICKS = re.compile(r"`+")


def escape_data(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def escape_property(text: str) -> str:
    return escape_data(text).replace(":", "%3A").replace(",", "%2C")


def warning(message: str, title: str | None = None) -> str:
    """One `::warning` workflow command line."""
    props = f" title={escape_property(title)}" if title else ""
    return f"::warning{props}::{escape_data(message)}"


def safe_log_line(line: str) -> str:
    """A plain output line the runner will not read as a workflow command."""
    return " " + line if line.lstrip().startswith("::") else line


def fenced(text: str) -> str:
    fence = "`" * max(3, max((len(run) for run in _BACKTICKS.findall(text)), default=0) + 1)
    return f"{fence}text\n{text}\n{fence}"


def is_github_actions() -> bool:
    return os.environ.get("GITHUB_ACTIONS", "").strip().lower() == "true"


def append_summary(markdown: str) -> bool:
    """Append to `$GITHUB_STEP_SUMMARY`; False when there is none or it cannot be written."""
    path = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if not path:
        return False
    try:
        with Path(path).open("a", encoding="utf-8") as fh:
            fh.write(markdown if markdown.endswith("\n") else markdown + "\n")
    except OSError:
        return False
    return True
