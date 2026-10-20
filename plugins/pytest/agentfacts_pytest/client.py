"""The plugin's `Client`: settings from the environment, `--agentfacts-offline`, its user agent."""

import pytest
from agentfacts.client.settings import Settings
from agentfacts.client.transport import Client

from agentfacts_pytest import __version__

USER_AGENT = f"agentfacts-pytest/{__version__} (+https://github.com/Illouminus/agent-facts)"


def make_client(config: pytest.Config) -> Client | None:
    """None when the user opted out (`AGENTFACTS_DISABLE=1`)."""
    settings = Settings.from_env()
    if settings.disabled:
        return None
    return Client(
        settings.endpoint,
        USER_AGENT,
        offline=bool(config.getoption("agentfacts_offline", False)),
        snapshot=settings.snapshot,
    )
