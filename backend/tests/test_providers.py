import time
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import config, services
from app.main import app
from app.providers.chain import ChainProvider
from app.providers.validator import Rejection, ValidationResult

client = TestClient(app)
WROCLAW = {"origin": "Wrocław Główny", "event_id": "ev_hackyeah2026"}
DAY = date(2026, 10, 4)


def recorded_wroclaw():
    return services.fixtures.search("Wrocław Główny", "Kraków Główny", DAY)


class FakeLive:
    """Plays back a list of outcomes: a ValidationResult or an exception to raise."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0
        self.windows = []

    def fetch(self, origin, destination, day, *, since=None, until=None):
        self.windows.append((since, until))
        outcome = self.outcomes[min(self.calls, len(self.outcomes) - 1)]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def live_options():
    return [t.model_copy(update={"source": "koleo"}) for t in recorded_wroclaw()]


def search(chain):
    return chain.search("Wrocław Główny", "Kraków Główny", DAY)


def test_fixture_provider_is_recorded_without_reason():
    chain = ChainProvider(services.fixtures)
    found = search(chain)
    assert found.data_source == "recorded" and found.fallback_reason is None
    assert (chain.stats.requests_total, chain.stats.live_ok, chain.stats.fallback) == (1, 0, 0)


def test_live_ok():
    chain = ChainProvider(services.fixtures, live=FakeLive(ValidationResult(accepted=live_options())))
    found = search(chain)
    assert found.data_source == "live" and found.fallback_reason is None
    assert all(t.source == "koleo" for t in found.options)
    assert chain.stats.live_ok == 1


def test_live_retried_once_then_fixtures_with_reason():
    live = FakeLive(TimeoutError("Koleo did not answer"))
    chain = ChainProvider(services.fixtures, live=live)
    found = search(chain)
    assert live.calls == 2  # one retry
    assert found.data_source == "recorded"
    assert found.options == recorded_wroclaw()
    assert found.fallback_reason == "live search failed: TimeoutError: Koleo did not answer"
    assert (chain.stats.fallback, chain.stats.last_fallback_reason) == (1, found.fallback_reason)


def test_retry_can_succeed():
    live = FakeLive(ConnectionError("blip"), ValidationResult(accepted=live_options()))
    found = search(ChainProvider(services.fixtures, live=live))
    assert found.data_source == "live" and live.calls == 2


def test_all_rejected_by_validator_gives_validator_reason():
    rejected = ValidationResult(rejected=[Rejection(0, "implausible price", {})])
    found = search(ChainProvider(services.fixtures, live=FakeLive(rejected)))
    assert found.data_source == "recorded"
    assert "validator rejected 1/1 options: implausible price" in found.fallback_reason


def test_api_key_never_leaks_into_reason(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "SECRET-KEY-123")
    live = FakeLive(RuntimeError("bad request for key SECRET-KEY-123"))
    found = search(ChainProvider(services.fixtures, live=live))
    assert "SECRET-KEY-123" not in found.fallback_reason


def test_configured_but_unavailable_live_is_an_honest_fallback():
    chain = ChainProvider(services.fixtures, unavailable_reason="live Koleo provider is not implemented yet")
    found = search(chain)
    assert found.data_source == "recorded"
    assert found.fallback_reason == "live Koleo provider is not implemented yet"
    assert chain.stats.fallback == 1


def test_make_provider_for_koleo_without_a_key(monkeypatch):
    monkeypatch.setattr(config, "TRAIN_PROVIDER", "koleo")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    chain = services.make_provider(services.fixtures)
    assert chain.live is None and chain.unavailable_reason == "GEMINI_API_KEY is not set"


def test_make_provider_for_koleo_with_a_key_plugs_in_the_live_provider(monkeypatch):
    from app.providers.koleo_agent import KoleoAgentProvider

    monkeypatch.setattr(config, "TRAIN_PROVIDER", "koleo")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "some-key")
    chain = services.make_provider(services.fixtures)
    assert isinstance(chain.live, KoleoAgentProvider) and chain.unavailable_reason is None


def test_api_reports_fallback_everywhere(monkeypatch):
    chain = ChainProvider(services.fixtures, live=FakeLive(TimeoutError("no network")))
    monkeypatch.setattr(services.planner, "provider", chain)
    monkeypatch.setattr(config, "SSE_STEP_SEC", 0)

    body = client.post("/api/plan", json=WROCLAW).json()
    assert body["data_source"] == "recorded"
    assert body["fallback_reason"] == "live search failed: TimeoutError: no network"
    assert body["plans"]  # the demo still works on recorded data

    with client.stream("GET", f"/api/plan/{body['request_id']}/stream") as r:
        text = "".join(r.iter_text())
    assert '"step": "fallback"' in text

    status = client.get("/api/providers/status").json()
    assert status["fallback"] == 1 and status["live_ok"] == 0
    assert status["last_fallback_reason"] == body["fallback_reason"]
    assert status["live_available"] is True


def test_status_endpoint_by_default():
    status = client.get("/api/providers/status").json()
    assert status["provider"] == "fixture"
    assert status["live_available"] is False
    assert set(status) == {
        "provider", "live_available", "requests_total", "live_ok", "live_partial", "fallback",
        "last_fallback_reason", "last_rejection_reason",
    }


def test_partly_rejected_live_search_is_live_but_counted():
    partly = ValidationResult(
        accepted=live_options(), rejected=[Rejection(0, "implausible price", {})]
    )
    chain = ChainProvider(services.fixtures, live=FakeLive(partly))
    found = search(chain)
    assert found.data_source == "live" and found.fallback_reason is None  # no fixtures were used
    assert (chain.stats.live_ok, chain.stats.live_partial, chain.stats.fallback) == (1, 1, 0)
    assert "validator rejected 1/" in chain.stats.last_rejection_reason
    assert "implausible price" in chain.stats.last_rejection_reason


def test_hung_live_search_times_out_without_a_retry():
    class Hung(FakeLive):
        def fetch(self, origin, destination, day, *, since=None, until=None):
            self.calls += 1
            time.sleep(1)

    live = Hung()
    chain = ChainProvider(services.fixtures, live=live, timeout_sec=0.05)
    started = time.monotonic()
    found = search(chain)
    assert time.monotonic() - started < 0.5
    assert live.calls == 1  # the first attempt is still running: no second browser
    assert found.data_source == "recorded" and found.options == recorded_wroclaw()
    assert found.fallback_reason == "live search failed: no answer within 0.05 s"


def test_search_window_reaches_the_live_provider():
    live = FakeLive(ValidationResult(accepted=live_options()))
    since = datetime.fromisoformat("2026-10-10T21:30:00+02:00")
    until = datetime.fromisoformat("2026-10-11T08:57:00+02:00")
    ChainProvider(services.fixtures, live=live).search("Wrocław Główny", "Kraków Główny", DAY, since=since, until=until)
    assert live.windows == [(since, until)]


def test_empty_window_is_no_search_and_no_fallback():
    # "Now" is already past the station deadline: nothing can arrive in time.
    live = FakeLive(ValidationResult(accepted=live_options()))
    chain = ChainProvider(services.fixtures, live=live)
    late = datetime.fromisoformat("2026-10-04T09:00:00+02:00")
    found = chain.search("Wrocław Główny", "Kraków Główny", DAY, since=late, until=late - timedelta(minutes=3))
    assert (found.options, found.fallback_reason, live.calls) == ([], None, 0)
    assert (chain.stats.requests_total, chain.stats.fallback) == (0, 0)


def test_reason_is_one_line():
    live = FakeLive(RuntimeError("unexpected page\n  <html>\n\tAccess denied"))
    found = search(ChainProvider(services.fixtures, live=live))
    assert found.fallback_reason == "live search failed: RuntimeError: unexpected page <html> Access denied"
