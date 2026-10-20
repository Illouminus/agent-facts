"""Client configuration from the environment (spec 07): one place for the plugin and the CLI."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ENDPOINT = "https://facts.baillot.dev"
_TRUE = frozenset({"1", "true", "yes", "on"})


@dataclass(frozen=True)
class Settings:
    endpoint: str = DEFAULT_ENDPOINT  # AGENTFACTS_ENDPOINT
    disabled: bool = False  # AGENTFACTS_DISABLE=1
    snapshot: Path | None = None  # AGENTFACTS_SNAPSHOT=<dir with services/ and facts/>

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if environ is None else environ
        snapshot = env.get("AGENTFACTS_SNAPSHOT", "").strip()
        return cls(
            endpoint=(env.get("AGENTFACTS_ENDPOINT", "").strip() or DEFAULT_ENDPOINT).rstrip("/"),
            disabled=env.get("AGENTFACTS_DISABLE", "").strip().lower() in _TRUE,
            snapshot=Path(snapshot).expanduser() if snapshot else None,
        )
