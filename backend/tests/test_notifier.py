import logging
import time

import httpx
import pytest

from app import config
from app.notifier import notify

FAKE_TOKEN = "123456:FAKE-token-for-tests"


@pytest.fixture
def telegram_on(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", FAKE_TOKEN)
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "42")


def fake_post(monkeypatch, response=None, error=None) -> list:
    calls = []

    def post(url, json, timeout):
        calls.append({"url": url, "json": json, "timeout": timeout})
        if error is not None:
            raise error
        return response

    monkeypatch.setattr(httpx, "post", post)
    return calls


def test_not_configured_sends_nothing(monkeypatch):
    calls = fake_post(monkeypatch)
    assert notify("hello") is False
    assert calls == []


def test_sends_message(monkeypatch, telegram_on):
    calls = fake_post(monkeypatch, httpx.Response(200, json={"ok": True, "result": {}}))
    assert notify("IC 05:10 is delayed by 25 min.") is True
    assert calls[0]["url"].endswith(f"/bot{FAKE_TOKEN}/sendMessage")
    assert calls[0]["json"] == {"chat_id": "42", "text": "IC 05:10 is delayed by 25 min."}
    assert calls[0]["timeout"] == config.TELEGRAM_TIMEOUT_SEC


def test_telegram_error_gives_false(monkeypatch, telegram_on):
    fake_post(monkeypatch, httpx.Response(400, json={"ok": False, "description": "chat not found"}))
    assert notify("hello") is False


def test_no_network_gives_false_and_hides_token(monkeypatch, telegram_on, caplog):
    fake_post(monkeypatch, error=httpx.ConnectError(f"cannot reach /bot{FAKE_TOKEN}/sendMessage"))
    with caplog.at_level(logging.WARNING):
        assert notify("hello") is False
    assert FAKE_TOKEN not in caplog.text


def test_hung_request_gives_false_quickly(monkeypatch, telegram_on):
    """Without a network the DNS lookup can hang past httpx's own timeout."""
    monkeypatch.setattr(config, "TELEGRAM_TIMEOUT_SEC", 0.05)
    monkeypatch.setattr(httpx, "post", lambda url, json, timeout: time.sleep(1))
    started = time.monotonic()
    assert notify("hello") is False
    assert time.monotonic() - started < 0.5
