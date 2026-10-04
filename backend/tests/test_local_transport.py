import json
from datetime import date, datetime, timedelta

from app.models import DelayModel, TrainOption
from app.planner.local_transport import LocalTransport
from app.planner.planner import TRANSFER_MIN
from app.planner.reliability import p_on_time
from app.services import events, local_transport, planner

EVENT = events["ev_hackyeah2026"]
LEGS = local_transport.route(EVENT.venue_station, EVENT.venue)
TRAM = next(leg for leg in LEGS if leg.timetable)


def at(text: str) -> datetime:
    return datetime.fromisoformat(text)


def hhmm(legs) -> list[tuple[str, str]]:
    return [(f"{leg.dep:%H:%M}", f"{leg.arr:%H:%M}") for leg in legs]


def train(arr: str, known_delay_min: int = 0) -> TrainOption:
    return TrainOption(
        id="tr_test", source="fixture", fetched_at="2026-10-03T11:30:00+02:00", mode="train",
        category="IC", train="IC", from_="Wrocław Główny", to="Kraków Główny",
        dep="2026-10-04T05:10:00+02:00", arr=arr, price_pln=64.0, changes=0,
        delay_model=DelayModel(p_on_time=0.7, mean_delay_min=6, p95_delay_min=25),
        known_delay_min=known_delay_min, url="https://koleo.pl/",
    )


def test_day_types():
    tt = TRAM.timetable
    assert tt.day_type(date(2026, 10, 4)) == "sunday"
    assert tt.day_type(date(2026, 10, 3)) == "saturday"
    assert tt.day_type(date(2026, 10, 5)) == "weekday"
    assert tt.day_type(date(2026, 11, 11)) == "sunday"  # Independence Day, a Wednesday


def test_tram_leaves_at_the_next_real_departure():
    # Sunday: at the stop at 08:23, the trams are 08:19 (gone) and 08:37.
    legs = local_transport.schedule(LEGS, at("2026-10-04T08:20:00+02:00"))
    assert hhmm(legs) == [("08:20", "08:23"), ("08:37", "08:44"), ("08:44", "08:56")]
    assert legs[1].line == "15" and legs[1].duration_min == 7
    assert all(leg.dep.utcoffset() == timedelta(hours=2) for leg in legs)


def test_departure_at_the_exact_minute_is_caught():
    legs = local_transport.schedule(LEGS, at("2026-10-04T08:41:00+02:00"))
    assert hhmm(legs)[1] == ("08:44", "08:51")
    assert legs[1].line == "16"


def test_weekday_has_more_trams_than_sunday():
    sunday = local_transport.arrival(LEGS, at("2026-10-04T08:20:00+02:00"))
    monday = local_transport.arrival(LEGS, at("2026-10-05T08:20:00+02:00"))
    assert f"{sunday:%H:%M}" == "08:56"
    assert f"{monday:%H:%M}" == "08:42"  # tram at 08:23


def test_after_the_last_tram_the_first_one_next_day_is_taken():
    legs = local_transport.schedule(LEGS, at("2026-10-03T23:30:00+02:00"))
    assert legs[1].dep == at("2026-10-04T04:49:00+02:00")  # Sunday's first tram


def test_winter_time_offset():
    legs = local_transport.schedule(LEGS, at("2026-10-25T08:20:00+01:00"))  # a Sunday after the clock change
    assert hhmm(legs)[1] == ("08:37", "08:44")
    assert legs[1].dep.utcoffset() == timedelta(hours=1)


def test_leg_without_timetable_keeps_its_fixed_duration(tmp_path):
    routes = [{"station": "A", "venue": "B", "legs": [
        {"mode": "tram", "from": "A", "to": "B", "duration_min": 13, "std_min": 3, "line": "15"},
    ]}]
    path = tmp_path / "local_routes.json"
    path.write_text(json.dumps(routes), encoding="utf-8")
    local = LocalTransport(path)
    legs = local.route("A", "B")
    start = at("2026-10-04T08:23:00+02:00")
    assert hhmm(local.schedule(legs, start)) == [("08:23", "08:36")]
    assert local.min_min(legs) == 13 and local.std_min(legs) == 3


def test_plan_legs_follow_the_timetable():
    result = planner.plan(EVENT, planner_request())
    for plan in result.options:
        walk, tram, last = plan.local_legs
        assert walk.dep == plan.train.expected_arr + timedelta(minutes=TRANSFER_MIN)
        assert tram.dep >= walk.arr and last.dep == tram.arr
        assert f"{tram.dep:%H:%M}" in departures_of(tram.dep.date(), tram.line)
        assert plan.arrival_at_venue == last.arr
        assert plan.buffer_min == round((plan.venue_target - last.arr).total_seconds() / 60)


def test_delay_that_misses_a_tram_costs_the_wait_for_the_next_one():
    # 08:33 -> tram 08:44, at the entrance 09:03. With +25 min -> tram 09:17, at the entrance 09:36.
    target = at("2026-10-04T09:30:00+02:00")
    on_time = train("2026-10-04T08:33:00+02:00")
    delayed = train("2026-10-04T08:33:00+02:00", known_delay_min=25)
    start = lambda t: t.expected_arr + timedelta(minutes=TRANSFER_MIN)  # noqa: E731
    assert f"{local_transport.arrival(LEGS, start(on_time)):%H:%M}" == "09:03"
    assert f"{local_transport.arrival(LEGS, start(delayed)):%H:%M}" == "09:36"
    assert p_on_time(on_time, LEGS, TRANSFER_MIN, target, 1000) > 0.8
    assert p_on_time(delayed, LEGS, TRANSFER_MIN, target, 1000) < 0.05


def test_nine_minutes_later_at_the_station_can_mean_thirteen_at_the_entrance():
    # Leaving the platform at 08:55 catches the 09:04 tram (entrance 09:23);
    # at 09:04 the next tram is 09:17 (entrance 09:36, after the 09:30 target).
    target = at("2026-10-04T09:30:00+02:00")
    fits = local_transport.arrival(LEGS, at("2026-10-04T08:55:00+02:00"))
    late = local_transport.arrival(LEGS, at("2026-10-04T09:04:00+02:00"))
    assert f"{fits:%H:%M}" == "09:23" and f"{late:%H:%M}" == "09:36"
    assert fits <= target < late


def planner_request():
    from app.models import PlanRequest
    return PlanRequest(origin="Wrocław Główny", event_id=EVENT.id)


def departures_of(day: date, line: str) -> set[str]:
    tt = TRAM.timetable
    return {f"{m // 60:02d}:{m % 60:02d}" for m, ln in tt.departures[tt.day_type(day)] if ln == line}
