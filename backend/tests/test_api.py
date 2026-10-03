import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import config, services
from app.main import app
from app.models import LocalLeg
from app.planner.local_transport import LocalTransport

config.SSE_STEP_SEC = 0
client = TestClient(app)


def make_plans() -> dict:
    r = client.post("/api/plan", json={"origin": "Wrocław Główny", "event_id": "ev_hackyeah2026"})
    assert r.status_code == 200
    return r.json()


def test_event():
    r = client.get("/api/events/ev_hackyeah2026")
    assert r.status_code == 200
    assert r.json()["venue_station"] == "Kraków Główny"
    assert client.get("/api/events/nope").status_code == 404


def test_plan_uses_contract_field_names():
    body = make_plans()
    assert body["status"] == "ok"
    plan = body["plans"][0]
    assert "from" in plan["train"] and "from_" not in plan["train"]
    assert "from" in plan["local_legs"][0]
    assert set(plan) >= {"labels", "venue_target", "buffer_min", "p_on_time", "overnight_stay", "buy_url"}


def test_unknown_origin_gives_no_options():
    r = client.post("/api/plan", json={"origin": "Gdańsk Główny", "event_id": "ev_hackyeah2026"})
    assert r.json() == {"request_id": r.json()["request_id"], "plans": [], "status": "no_options"}


def test_stream_replays_statuses():
    body = make_plans()
    with client.stream("GET", f"/api/plan/{body['request_id']}/stream") as r:
        text = "".join(r.iter_text())
    assert "event: status" in text and "Searching for trains" in text
    assert text.rstrip().splitlines()[-2] == "event: done"


def test_disruption_replans():
    body = make_plans()
    fastest = next(p for p in body["plans"] if "fastest" in p["labels"])
    r = client.post("/api/simulate/disruption", json={"plan_id": fastest["id"], "train_delay_min": 25})
    assert r.status_code == 200
    out = r.json()
    assert out["affected_plan"]["train"]["known_delay_min"] == 25
    assert out["affected_plan"]["p_on_time"] < fastest["p_on_time"]
    assert out["notified"] is False  # no Telegram yet
    assert "is delayed by 25 min" in out["message"]


def test_plan_without_path_is_valid(tmp_path, monkeypatch):
    # A route without `path` stays valid: the field is present in the response and null.
    routes = [{
        "station": "Kraków Główny", "venue": "Tauron Arena Kraków", "legs": [
            {"mode": "walk", "from": "Kraków Główny", "to": "Tauron Arena Kraków",
             "duration_min": 28, "std_min": 5, "line": None},
        ],
    }]
    routes_file = tmp_path / "local_routes.json"
    routes_file.write_text(json.dumps(routes), encoding="utf-8")
    monkeypatch.setattr(services.planner, "local", LocalTransport(routes_file))

    leg = make_plans()["plans"][0]["local_legs"][0]
    assert "path" in leg and leg["path"] is None


def test_path_reaches_plan(tmp_path, monkeypatch):
    station, arena = [50.0677, 19.9479], [50.0675, 19.9917]
    routes = [{
        "station": "Kraków Główny", "venue": "Tauron Arena Kraków", "legs": [
            {"mode": "walk", "from": "Kraków Główny", "to": "Tauron Arena Kraków",
             "duration_min": 28, "std_min": 5, "line": None, "path": [station, arena]},
        ],
    }]
    routes_file = tmp_path / "local_routes.json"
    routes_file.write_text(json.dumps(routes), encoding="utf-8")
    monkeypatch.setattr(services.planner, "local", LocalTransport(routes_file))

    leg = make_plans()["plans"][0]["local_legs"][0]
    assert leg["path"] == [station, arena]


def test_path_rejects_bad_coordinates():
    with pytest.raises(ValidationError):
        LocalLeg(
            mode="walk", from_="a", to="b",
            dep="2026-10-04T08:20:00+02:00", arr="2026-10-04T08:48:00+02:00",
            duration_min=28, std_min=5, path=[[19.9479, 250.0]],
        )
