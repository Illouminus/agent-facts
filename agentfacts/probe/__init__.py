"""Probe runner (docs/specs/04-probe-runner.md): declarative probes, budgets, keys, redaction.

No LLM anywhere in this package (invariant 1); `tests/probe/test_runner.py` checks the imports.
"""

from agentfacts import __version__

OPT_OUT_EMAIL = "edouard@baillot.dev"
USER_AGENT = (
    f"agent-facts-probe/{__version__} "
    f"(+https://github.com/Illouminus/agent-facts; opt-out: {OPT_OUT_EMAIL})"
)
