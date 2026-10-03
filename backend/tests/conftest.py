from datetime import datetime

import pytest

from app import config, services
from app.providers.chain import ChainProvider

# Before every recorded departure (the earliest is on 3.10 at 16:00+), so nothing is filtered as departed.
TEST_NOW = datetime.fromisoformat("2026-10-03T12:00:00+02:00")


@pytest.fixture(autouse=True)
def no_real_telegram(monkeypatch):
    """Tests never send real Telegram messages, even when .env has the keys."""
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "")


@pytest.fixture(autouse=True)
def frozen_now(monkeypatch):
    """Tests do not depend on the real clock: results stay the same after the event day."""
    monkeypatch.setattr(config, "DEMO_NOW", TEST_NOW)


@pytest.fixture(autouse=True)
def recorded_data_only(monkeypatch):
    """Tests never hit live Koleo/Gemini, even with TRAIN_PROVIDER=koleo in .env; fresh counters each test."""
    monkeypatch.setattr(config, "TRAIN_PROVIDER", "fixture")
    monkeypatch.setattr(services.planner, "provider", ChainProvider(services.fixtures))
