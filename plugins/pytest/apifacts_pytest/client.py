"""The plugin's `Client`: settings from the environment, `--apifacts-offline`, its user agent."""

import pytest
from apifacts.client.settings import Settings
from apifacts.client.transport import Client

from apifacts_pytest import __version__

USER_AGENT = f"apifacts-pytest/{__version__} (+https://github.com/Illouminus/apifacts)"


def make_client(config: pytest.Config) -> Client | None:
    """None when the user opted out (`APIFACTS_DISABLE=1`)."""
    settings = Settings.from_env()
    if settings.disabled:
        return None
    return Client(
        settings.endpoint,
        USER_AGENT,
        offline=bool(config.getoption("apifacts_offline", False)),
        snapshot=settings.snapshot,
    )
