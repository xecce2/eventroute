import json
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.city.overview import build_overview, choose_plan, load_of, slot_of
from app.city.participants import generate, load_participants
from app.main import app
from app.models import Participant, PlanRequest
from app.planner.planner import PlanResult
from app.services import events, planner

client = TestClient(app)
EVENT = events["ev_hackyeah2026"]
ORIGINS = ["Katowice", "Poznań Główny", "Warszawa Centralna", "Wrocław Główny"]


def test_stations_for_registration_form():
    r = client.get("/api/events/ev_hackyeah2026/stations")
    assert r.status_code == 200
    assert r.json() == ORIGINS
    assert client.get("/api/events/nope/stations").status_code == 404


def test_overview_endpoint():
    r = client.get("/api/city/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["participants_total"] == 420
    assert sum(o["count"] for o in body["origins"]) == 420
    assert {n["name"] for n in body["nodes"]} == {"Kraków Główny", "Tauron Arena Kraków"}
    # The wave has no gaps: consecutive 15-minute slots.
    slots = [datetime.fromisoformat(s["slot"]) for s in body["arrivals_by_slot"]]
    assert all(b - a == timedelta(minutes=15) for a, b in zip(slots, slots[1:]))
    assert sum(s["count"] for s in body["arrivals_by_slot"]) <= 420


def test_generator_is_deterministic_and_anonymous():
    a, b = generate(ORIGINS), generate(ORIGINS)
    assert a == b
    assert len(a) == 420
    assert set(Participant.model_fields) == {"id", "origin", "pref"}  # no personal data
    assert {p.origin for p in a} == set(ORIGINS)


def test_participants_file_wins_over_generator(tmp_path):
    f = tmp_path / "participants.json"
    f.write_text(json.dumps([{"id": "u_1", "origin": "Katowice", "pref": "cheapest"}]), encoding="utf-8")
    assert load_participants(ORIGINS, f) == [Participant(id="u_1", origin="Katowice", pref="cheapest")]
    assert len(load_participants(ORIGINS, tmp_path / "missing.json")) == 420


def test_choose_plan_falls_back_to_safest():
    plans = planner.plan(EVENT, PlanRequest(origin="Poznań Główny", event_id=EVENT.id)).plans
    cheapest = next(p for p in plans if "cheapest" in p.labels)
    assert choose_plan(plans, "cheapest") is cheapest
    without_cheapest = [p for p in plans if "cheapest" not in p.labels]
    assert "safest" in choose_plan(without_cheapest, "cheapest").labels
    only_fastest = [plans[0].model_copy(update={"labels": ["fastest"]})]
    assert choose_plan(only_fastest, "cheapest") is only_fastest[0]
    assert choose_plan([], "safest") is None


def test_overnight_participants_not_in_wave():
    plan = planner.plan(EVENT, PlanRequest(origin="Wrocław Główny", event_id=EVENT.id)).plans[0]

    class StubPlanner:
        def plan(self, event, req):
            overnight = plan.model_copy(update={"overnight_stay": True})
            return PlanResult(plans=[overnight], options=[overnight])

    people = [Participant(id="u_1", origin="Wrocław Główny", pref="safest")]
    overview = build_overview(EVENT, people, StubPlanner())
    assert overview.participants_total == 1
    assert overview.arrivals_by_slot == []


def test_no_recommendations_when_capacity_is_enough(tmp_path):
    nodes = tmp_path / "nodes.json"
    nodes.write_text(json.dumps([
        {"kind": "station", "name": "Kraków Główny", "lat": 50.0677, "lon": 19.9479, "capacity_per_slot": 10_000},
        {"kind": "venue", "capacity_per_slot": 10_000},
    ]), encoding="utf-8")
    overview = build_overview(EVENT, generate(ORIGINS), planner, nodes)
    assert overview.recommendations == []
    assert {n.load for n in overview.nodes} == {"low"}


def test_load_and_slot_helpers():
    assert (load_of(50, 100), load_of(60, 100), load_of(100, 100)) == ("low", "medium", "high")
    t = datetime.fromisoformat("2026-10-04T08:48:30+02:00")
    assert slot_of(t) == datetime.fromisoformat("2026-10-04T08:45:00+02:00")
