from fastapi.testclient import TestClient

from app import config
from app.main import app

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
    assert "event: status" in text and "Ищу поезда" in text
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
    assert "опаздывает на 25 мин" in out["message"]
