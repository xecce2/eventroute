import random
from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from app.models import DelayModel, PlanRequest, TrainOption
from app.planner.planner import Candidate, Planner, select
from app.planner.reliability import ON_TIME_MAX_MIN, p_on_time, sample_delay
from app.providers.base import SearchResult
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
    plans = planner.plan(EVENT, WROCLAW).plans
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
    found = planner.provider.search("Wrocław Główny", "Kraków Główny", EVENT.start.date())
    trains = {t.id: t for t in found.options}
    legs = planner.local.route(EVENT.venue_station, EVENT.venue)
    assert planner._score(trains["tr_wro_1004_0021"], legs, EVENT.venue_target).overnight  # arr 04:38
    assert not planner._score(trains["tr_wro_1004_0146"], legs, EVENT.venue_target).overnight  # arr 06:08


class StubProvider:
    """Returns the given trains and remembers the window the planner asked for."""

    def __init__(self, *trains: TrainOption):
        self.trains = list(trains)
        self.window = None

    def search(self, origin, destination, day, *, since=None, until=None):
        self.window = (since, until)
        return SearchResult(self.trains, "recorded")


def test_search_window_is_12_hours_before_arrive_by_and_not_before_now():
    stub = StubProvider()
    p = Planner(stub, planner.local, runs=10)
    arrive_by = datetime.fromisoformat("2026-10-11T13:00:00+02:00")
    req = PlanRequest(origin="Wrocław Główny", event_id=EVENT.id, arrive_by=arrive_by)

    p.plan(EVENT, req, not_before=datetime.fromisoformat("2026-10-03T12:00:00+02:00"))
    since, until = stub.window
    assert since == datetime.fromisoformat("2026-10-11T01:00:00+02:00")
    assert until < arrive_by and arrive_by - until < timedelta(hours=1)  # the station deadline

    now = datetime.fromisoformat("2026-10-11T06:40:00+02:00")
    p.plan(EVENT, req, not_before=now)
    assert stub.window[0] == now  # departed trips are not searched for


def test_winter_time_date_keeps_its_offset_and_a_real_12_hour_window():
    # Clocks go back on 2026-10-25 at 03:00: the evening before is +02:00, the morning is +01:00.
    def t(id: str, dep: str, arr: str) -> TrainOption:
        return train(id, "05:10", "08:15").model_copy(update={
            "dep": datetime.fromisoformat(dep), "arr": datetime.fromisoformat(arr),
        })

    stub = StubProvider(
        t("too_early", "2026-10-24T22:00:00+02:00", "2026-10-25T01:00:00+02:00"),
        t("night", "2026-10-24T23:00:00+02:00", "2026-10-25T02:00:00+02:00"),
        t("morning", "2026-10-25T05:10:00+01:00", "2026-10-25T08:15:00+01:00"),
    )
    req = PlanRequest(origin="Wrocław Główny", event_id=EVENT.id, arrive_by="2026-10-25T09:30:00+01:00")
    options = {o.train.id: o for o in Planner(stub, planner.local, runs=10).plan(EVENT, req).options}

    # 09:30+01:00 minus 12 real hours is 22:30+02:00 the evening before.
    assert stub.window[0] == datetime.fromisoformat("2026-10-24T22:30:00+02:00")
    assert set(options) == {"night", "morning"}
    assert options["night"].overnight_stay and not options["morning"].overnight_stay
    assert options["morning"].venue_target.isoformat() == "2026-10-25T09:30:00+01:00"
    assert options["morning"].arrival_at_venue.isoformat().endswith("+01:00")


def test_overnight_follows_the_arrive_by_day_not_the_event_day():
    def t(id: str, dep: str, arr: str) -> TrainOption:
        return train(id, "05:10", "08:15").model_copy(update={
            "dep": datetime.fromisoformat(dep), "arr": datetime.fromisoformat(arr),
        })

    stub = StubProvider(
        t("evening", "2026-10-10T23:00:00+02:00", "2026-10-10T23:50:00+02:00"),
        t("before_six", "2026-10-11T02:00:00+02:00", "2026-10-11T05:30:00+02:00"),
        t("morning", "2026-10-11T05:10:00+02:00", "2026-10-11T08:15:00+02:00"),
    )
    req = PlanRequest(origin="Wrocław Główny", event_id=EVENT.id, arrive_by="2026-10-11T09:30:00+02:00")
    options = {o.train.id: o.overnight_stay for o in Planner(stub, planner.local, runs=10).plan(EVENT, req).options}
    assert options == {"evening": True, "before_six": True, "morning": False}


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


def test_options_list_all_suitable_cheapest_first():
    result = planner.plan(EVENT, PlanRequest(origin="Katowice", event_id=EVENT.id))
    options = result.options
    assert len(options) > len(result.plans)
    assert {p.id for p in result.plans} <= {p.id for p in options}  # cards are in the list
    known = [p.price_pln for p in options if p.price_pln is not None]
    assert known == sorted(known)
    # Unknown price goes last.
    first_unknown = next((i for i, p in enumerate(options) if p.price_pln is None), len(options))
    assert all(p.price_pln is None for p in options[first_unknown:])
    # Options that are not cards have no labels.
    card_ids = {p.id for p in result.plans}
    assert all(p.labels == [] for p in options if p.id not in card_ids)


def test_options_include_overnight():
    options = planner.plan(EVENT, WROCLAW).options
    assert any(p.overnight_stay for p in options)


def test_equal_price_cheapest_goes_to_later_departure():
    early = Candidate(train("early", "01:30", "06:34", price=77.0), p=1.0, overnight=False)
    late = Candidate(train("late", "02:53", "08:15", price=77.0), p=0.97, overnight=False)
    picks = dict((c.train.id, labels) for c, labels in select([early, late]))
    assert picks["early"] == ["safest", "fastest"]
    assert picks["late"] == ["cheapest"]


def test_poznan_has_two_cards():
    plans = planner.plan(EVENT, PlanRequest(origin="Poznań Główny", event_id=EVENT.id)).plans
    labels = {p.train.id: p.labels for p in plans}
    assert labels == {"tr_poz_1004_0130": ["safest", "fastest"], "tr_poz_1004_0253": ["cheapest"]}


def test_known_delay_lowers_p_on_time():
    legs = planner.local.route(EVENT.venue_station, EVENT.venue)
    t = train("ic", "05:10", "08:15")
    on_time = p_on_time(t, legs, 5, EVENT.venue_target, 1000)
    late = p_on_time(t.model_copy(update={"known_delay_min": 40}), legs, 5, EVENT.venue_target, 1000)
    assert late < on_time
    assert on_time == p_on_time(t, legs, 5, EVENT.venue_target, 1000)  # deterministic


def test_known_delay_is_a_lower_bound_not_a_second_delay():
    model = DelayModel(p_on_time=0.7, mean_delay_min=6, p95_delay_min=25)
    rng = random.Random(1)
    assert all(sample_delay(model, rng, at_least=25) >= 25 for _ in range(200))
    assert all(sample_delay(model, rng, at_least=3) >= 3 for _ in range(200))
    # Past the known delay the tail looks the same as past the on-time limit.
    extra = [sample_delay(model, rng, at_least=25) - 25 for _ in range(5000)]
    tail = [d - ON_TIME_MAX_MIN for d in (sample_delay(model, rng) for _ in range(20000)) if d > ON_TIME_MAX_MIN]
    assert abs(sum(extra) / len(extra) - sum(tail) / len(tail)) < 1.0
