from datetime import datetime

import pytest
from pydantic import ValidationError

from app.models import DelayModel, PlanRequest, TrainOption
from app.planner.planner import Candidate, select
from app.planner.reliability import p_on_time
from app.services import events, planner

EVENT = events["ev_hackyeah2026"]
WROCLAW = PlanRequest(origin="Wrocław Główny", event_id=EVENT.id)


def train(id: str, dep: str, arr: str, price: float | None = 64.0, mode: str = "train") -> TrainOption:
    return TrainOption(
        id=id, source="fixture", fetched_at="2026-10-03T11:30:00+02:00", mode=mode,
        category="IC", train="IC", from_="Wrocław Główny", to="Kraków Główny",
        dep=f"2026-10-04T{dep}:00+02:00", arr=f"2026-10-04T{arr}:00+02:00",
        price_pln=price, changes=0,
        delay_model=DelayModel(p_on_time=0.7, mean_delay_min=6, p95_delay_min=25),
        url="https://koleo.pl/",
    )


def test_time_without_timezone_is_rejected():
    raw = train("x", "05:10", "08:15").model_dump()
    raw["dep"] = "2026-10-04T05:10:00"
    with pytest.raises(ValidationError):
        TrainOption.model_validate(raw)


def test_wroclaw_plans_respect_rules():
    plans = planner.plan(EVENT, WROCLAW)
    assert 1 <= len(plans) <= 3
    labels = [label for p in plans for label in p.labels]
    assert sorted(labels) == ["cheapest", "fastest", "safest"]  # each label exactly once
    for p in plans:
        assert p.train.expected_arr <= p.venue_target
        assert p.venue_target == datetime.fromisoformat("2026-10-04T09:30:00+02:00")
        if p.overnight_stay:
            assert p.labels == ["safest"]
    # Only IC 05:10 -> 08:15 makes it by train on the event day (checked on Koleo).
    fastest = next(p for p in plans if "fastest" in p.labels)
    assert fastest.train.id == "tr_wro_1004_0510"


def test_night_arrivals_are_overnight():
    trains = {t.id: t for t in planner.provider.search("Wrocław Główny", "Kraków Główny", EVENT.start.date())}
    legs = planner.local.route(EVENT.venue_station, EVENT.venue)
    assert planner._score(trains["tr_wro_1004_0021"], legs, EVENT.venue_target).overnight  # arr 04:38
    assert not planner._score(trains["tr_wro_1004_0146"], legs, EVENT.venue_target).overnight  # arr 06:08


def test_one_option_winning_several_labels_is_one_plan():
    c = Candidate(train("a", "05:10", "08:15"), p=0.95, overnight=False)
    picks = select([c])
    assert len(picks) == 1
    assert picks[0][1] == ["safest", "fastest", "cheapest"]


def test_overnight_never_fastest_or_cheapest():
    night = Candidate(train("night", "05:00", "05:30", price=10.0), p=1.0, overnight=True)
    day = Candidate(train("day", "05:10", "08:15"), p=0.9, overnight=False)
    picks = dict((c.train.id, labels) for c, labels in select([night, day]))
    assert "night" not in picks
    assert picks["day"] == ["safest", "fastest", "cheapest"]


def test_overnight_becomes_safest_when_event_day_is_risky():
    night = Candidate(train("night", "05:00", "05:30"), p=0.99, overnight=True)
    day = Candidate(train("day", "05:10", "08:15"), p=0.4, overnight=False)
    picks = dict((c.train.id, labels) for c, labels in select([night, day]))
    assert picks["night"] == ["safest"]
    assert picks["day"] == ["fastest", "cheapest"]


def test_price_unknown_not_cheapest():
    no_price = Candidate(train("np", "05:10", "08:00", price=None), p=0.95, overnight=False)
    priced = Candidate(train("pr", "05:20", "08:20", price=90.0), p=0.95, overnight=False)
    picks = dict((c.train.id, labels) for c, labels in select([no_price, priced]))
    assert "cheapest" not in picks["np"]
    assert "cheapest" in picks["pr"]


def test_known_delay_lowers_p_on_time():
    legs = planner.local.route(EVENT.venue_station, EVENT.venue)
    t = train("ic", "05:10", "08:15")
    on_time = p_on_time(t, legs, 5, EVENT.venue_target, 1000)
    late = p_on_time(t.model_copy(update={"known_delay_min": 40}), legs, 5, EVENT.venue_target, 1000)
    assert late < on_time
    assert on_time == p_on_time(t, legs, 5, EVENT.venue_target, 1000)  # deterministic
