"""No bot test reads the real ~/.private_keys: the default keys dir is a temp dir with a fake
agent-facts-bot key (tests that need it missing delete it)."""

import pytest
from bot_repo import FAKE_BOT_TOKEN


@pytest.fixture(autouse=True)
def bot_keys(tmp_path_factory, monkeypatch):
    keys = tmp_path_factory.mktemp("keys")
    (keys / "agent-facts-bot.key").write_text(FAKE_BOT_TOKEN + "\n", encoding="utf-8")
    monkeypatch.setattr("apifacts.bot.token.DEFAULT_KEYS_DIR", keys)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    return keys
