from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app import clock, config
from app.config import _aware_datetime
from app.main import app

client = TestClient(app)
WROCLAW = {"origin": "Wrocław Główny", "event_id": "ev_hackyeah2026"}


def at(time: str) -> datetime:
    return datetime.fromisoformat(f"2026-10-04T{time}:00+02:00")


def deps(plans: list[dict]) -> list[datetime]:
    return [datetime.fromisoformat(p["train"]["dep"]) for p in plans]


def test_departed_options_are_hidden(monkeypatch):
    monkeypatch.setattr(config, "DEMO_NOW", at("05:00"))
    body = client.post("/api/plan", json=WROCLAW).json()
    assert body["status"] == "ok"
    assert all(d >= at("05:00") for d in deps(body["options"] + body["plans"]))
    assert "tr_wro_1004_0510" in {p["train"]["id"] for p in body["options"]}  # IC 05:10 still there


def test_status_says_how_many_departed(monkeypatch):
    monkeypatch.setattr(config, "DEMO_NOW", at("05:00"))
    monkeypatch.setattr(config, "SSE_STEP_SEC", 0)
    body = client.post("/api/plan", json=WROCLAW).json()
    with client.stream("GET", f"/api/plan/{body['request_id']}/stream") as r:
        text = "".join(r.iter_text())
    assert "already departed" in text


def test_everything_departed_gives_no_options(monkeypatch):
    monkeypatch.setattr(config, "DEMO_NOW", at("09:00"))
    body = client.post("/api/plan", json=WROCLAW).json()
    assert body["status"] == "no_options"
    assert body["plans"] == [] and body["options"] == []


def test_disruption_alternatives_not_in_the_past(monkeypatch):
    monkeypatch.setattr(config, "DEMO_NOW", at("03:00"))
    body = client.post("/api/plan", json=WROCLAW).json()
    ic = next(p for p in body["options"] if p["train"]["id"] == "tr_wro_1004_0510")
    # The delay is reported later than the train's departure.
    monkeypatch.setattr(config, "DEMO_NOW", at("06:00"))
    out = client.post("/api/simulate/disruption", json={"plan_id": ic["id"], "train_delay_min": 25}).json()
    assert all(d >= at("06:00") for d in deps(out["options"]))
    assert out["affected_plan"]["train"]["id"] == "tr_wro_1004_0510"


def test_real_clock_when_demo_now_is_not_set(monkeypatch):
    monkeypatch.setattr(config, "DEMO_NOW", None)
    assert clock.now().tzinfo is not None


def test_demo_now_must_have_time_zone(monkeypatch):
    monkeypatch.setenv("DEMO_NOW", "2026-10-04T04:30:00")
    with pytest.raises(ValueError, match="time zone"):
        _aware_datetime("DEMO_NOW")
    monkeypatch.setenv("DEMO_NOW", "2026-10-04T04:30:00+02:00")
    assert _aware_datetime("DEMO_NOW") == at("04:30")
    monkeypatch.setenv("DEMO_NOW", "")
    assert _aware_datetime("DEMO_NOW") is None
