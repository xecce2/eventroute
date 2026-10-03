import pytest

from app import config


@pytest.fixture(autouse=True)
def no_real_telegram(monkeypatch):
    """Tests never send real Telegram messages, even when .env has the keys."""
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "")
