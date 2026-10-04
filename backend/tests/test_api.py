import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import config, services
from app.city.overview import build_overview
from app.city.participants import generate
from app.config import FIXTURES_DIR
from app.main import app
from app.models import LocalLeg
from app.planner.local_transport import LocalTransport
from app.planner.planner import Planner
from app.providers.chain import ChainProvider
from app.providers.fixture import FixtureProvider

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
    assert r.json() == {
        "request_id": r.json()["request_id"], "plans": [], "options": [], "status": "no_options",
        "data_source": "recorded", "fallback_reason": None,
    }


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


def test_disruption_returns_options():
    body = make_plans()
    out = client.post(
        "/api/simulate/disruption", json={"plan_id": body["plans"][0]["id"], "train_delay_min": 10}
    ).json()
    assert "options" in out
    assert {p["id"] for p in out["plans"]} <= {p["id"] for p in out["options"]}


def test_disruption_on_option_that_is_not_a_card():
    body = make_plans()
    card_ids = {p["id"] for p in body["plans"]}
    other = next(p for p in body["options"] if p["id"] not in card_ids)
    r = client.post("/api/simulate/disruption", json={"plan_id": other["id"], "train_delay_min": 15})
    assert r.status_code == 200
    assert r.json()["affected_plan"]["train"]["id"] == other["train"]["id"]


def test_cors_allows_vite_by_ip():
    r = client.options("/api/plan", headers={
        "Origin": "http://127.0.0.1:5173", "Access-Control-Request-Method": "POST",
    })
    assert r.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"


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


def test_disruption_replans_without_a_new_search():
    body = make_plans()
    searches = services.planner.provider.stats.requests_total
    out = client.post(
        "/api/simulate/disruption", json={"plan_id": body["plans"][0]["id"], "train_delay_min": 25}
    ).json()
    assert services.planner.provider.stats.requests_total == searches
    assert {p["train"]["id"] for p in out["options"]} <= {p["train"]["id"] for p in body["options"]}
    assert (out["data_source"], out["fallback_reason"]) == (body["data_source"], body["fallback_reason"])


def test_arrive_by_in_another_offset_gives_the_same_plans():
    def summary(arrive_by):
        body = client.post("/api/plan", json={
            "origin": "Wrocław Główny", "event_id": "ev_hackyeah2026", "arrive_by": arrive_by,
        }).json()
        return [(p["train"]["id"], p["labels"], p["overnight_stay"], p["p_on_time"]) for p in body["options"]]

    local = summary("2026-10-04T09:30:00+02:00")
    assert local and local == summary("2026-10-04T07:30:00Z") == summary("2026-10-04T03:30:00-04:00")


def test_arrive_by_after_the_event_start_is_accepted():
    # The event is the place; its start is only the default time to be there.
    r = client.post("/api/plan", json={
        "origin": "Wrocław Główny", "event_id": "ev_hackyeah2026", "arrive_by": "2026-10-04T13:00:00+02:00",
    })
    assert r.status_code == 200
    options = r.json()["options"]
    assert options and all(p["venue_target"] == "2026-10-04T13:00:00+02:00" for p in options)
    # The window is the 12 hours before 13:00, so nothing from the evening before.
    assert all(p["train"]["dep"] >= "2026-10-04T01:00:00+02:00" for p in options)
    assert all(p["arrival_at_venue"] <= "2026-10-04T13:00:00+02:00" for p in options)


def test_arrive_by_without_a_time_zone_is_rejected():
    r = client.post("/api/plan", json={
        "origin": "Wrocław Główny", "event_id": "ev_hackyeah2026", "arrive_by": "2026-10-11T09:30:00",
    })
    assert r.status_code == 422


def week_later_fixtures(tmp_path) -> FixtureProvider:
    """The recorded files plus the same trips a week later, as `record_fixtures.py` would add them."""
    trains_dir = FIXTURES_DIR / "trains"
    for path in trains_dir.glob("*.json"):
        raw = path.read_text(encoding="utf-8")
        (tmp_path / path.name).write_text(raw, encoding="utf-8")
        later = [
            {**t, "id": t["id"] + "_w2", **{
                k: (datetime.fromisoformat(t[k]) + timedelta(days=7)).isoformat() for k in ("dep", "arr")
            }}
            for t in json.loads(raw)
        ]
        (tmp_path / f"{path.stem}_1011.json").write_text(json.dumps(later), encoding="utf-8")
    return FixtureProvider(tmp_path)


def test_another_date_is_planned_from_its_own_trips(tmp_path, monkeypatch):
    monkeypatch.setattr(services.planner, "provider", ChainProvider(week_later_fixtures(tmp_path)))

    def departures(arrive_by=None):
        request = {"origin": "Wrocław Główny", "event_id": "ev_hackyeah2026"}
        body = client.post("/api/plan", json=request | ({"arrive_by": arrive_by} if arrive_by else {}))
        assert body.status_code == 200
        return sorted(datetime.fromisoformat(p["train"]["dep"]) for p in body.json()["options"])

    event_day = departures()
    assert event_day == departures("2026-10-04T09:30:00+02:00")
    assert all(d.date().isoformat() in ("2026-10-03", "2026-10-04") for d in event_day)
    week_later = departures("2026-10-11T09:30:00+02:00")
    assert week_later == [d + timedelta(days=7) for d in event_day]
    assert week_later == departures("2026-10-11T07:30:00Z")


def test_city_overview_ignores_fixtures_of_other_dates(tmp_path):
    event = services.events["ev_hackyeah2026"]
    people = generate(services.fixtures.origins(event.venue_station))
    both = Planner(ChainProvider(week_later_fixtures(tmp_path)), services.local_transport, runs=config.MC_RUNS)
    assert build_overview(event, people, both) == build_overview(event, people, services.city_planner)


@pytest.mark.parametrize("budget", [0, -5])
def test_budget_must_be_positive(budget):
    r = client.post("/api/plan", json={
        "origin": "Wrocław Główny", "event_id": "ev_hackyeah2026", "budget_pln": budget,
    })
    assert r.status_code == 422


@pytest.mark.parametrize("budget", ["NaN", "Infinity", "-Infinity"])
def test_budget_that_is_not_a_number_is_rejected_not_a_server_error(budget):
    body = '{"origin": "Wrocław Główny", "event_id": "ev_hackyeah2026", "budget_pln": %s}' % budget
    r = client.post("/api/plan", content=body.encode(), headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", "budget_pln"]


@pytest.mark.parametrize("arrive_by", [
    "0001-01-01T00:00:00+02:00", "0001-01-01T00:00:00Z", "9999-12-31T23:59:59-12:00",
])
def test_arrive_by_at_the_edge_of_the_calendar_is_rejected_not_a_server_error(arrive_by):
    r = client.post("/api/plan", json={
        "origin": "Wrocław Główny", "event_id": "ev_hackyeah2026", "arrive_by": arrive_by,
    })
    assert r.status_code == 422
    assert "out of range" in r.json()["detail"][0]["msg"]


def test_budget_leaves_out_options_without_a_price():
    # By 10:00, so the FlixBus at 07:05 (no price on Koleo) is among the options.
    request = {"origin": "Katowice", "event_id": "ev_hackyeah2026", "arrive_by": "2026-10-04T10:00:00+02:00"}
    assert any(p["price_pln"] is None for p in client.post("/api/plan", json=request).json()["options"])
    options = client.post("/api/plan", json={**request, "budget_pln": 30}).json()["options"]
    assert options and all(p["price_pln"] is not None and p["price_pln"] <= 30 for p in options)


def test_mode_pref_filters_by_mode():
    request = {"origin": "Wrocław Główny", "event_id": "ev_hackyeah2026"}
    for mode in ("train", "bus"):
        options = client.post("/api/plan", json={**request, "mode_pref": mode}).json()["options"]
        assert options and {p["train"]["mode"] for p in options} == {mode}
    assert client.post("/api/plan", json={**request, "mode_pref": "plane"}).status_code == 422


def test_origin_without_diacritics_is_found():
    plain = client.post("/api/plan", json={"origin": "wroclaw glowny", "event_id": "ev_hackyeah2026"}).json()
    assert [p["train"]["id"] for p in plain["options"]] == [p["train"]["id"] for p in make_plans()["options"]]
