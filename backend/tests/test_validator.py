import json
from datetime import datetime

import pytest

from app.config import FIXTURES_DIR
from app.models import TrainOption
from app.providers.validator import koleo_slug, koleo_url, validate_options

ORIGIN, DEST = "Wrocław Główny", "Kraków Główny"
WINDOW = (
    datetime.fromisoformat("2026-10-03T00:00:00+02:00"),
    datetime.fromisoformat("2026-10-04T23:59:00+02:00"),
)
FETCHED_AT = datetime.fromisoformat("2026-10-03T12:00:00+02:00")


def raw(**overrides) -> dict:
    item = {
        "category": "IC", "from": ORIGIN, "to": DEST,
        "dep": "2026-10-04T05:10:00+02:00", "arr": "2026-10-04T08:15:00+02:00",
        "price_pln": 64.0, "changes": 0,
    }
    item.update(overrides)
    return item


def check(items, source="koleo"):
    return validate_options(
        items, origin=ORIGIN, destination=DEST, window=WINDOW, source=source, fetched_at=FETCHED_AT
    )


def only_reason(items) -> str:
    result = check(items)
    assert result.accepted == []
    assert len(result.rejected) == 1
    return result.rejected[0].reason


def test_good_option_becomes_train_option():
    result = check([raw()])
    assert result.rejected == [] and result.fallback_reason() is None
    t = result.accepted[0]
    assert (t.id, t.source, t.mode, t.category, t.train) == ("tr_wro_1004_0510", "koleo", "train", "IC", "IC")
    assert t.from_ == ORIGIN and t.to == DEST and t.known_delay_min == 0
    assert (t.delay_model.p_on_time, t.delay_model.mean_delay_min, t.delay_model.p95_delay_min) == (0.7, 6, 25)
    assert t.url == "https://koleo.pl/rozklad-pkp/wroclaw-glowny/krakow-glowny/04-10-2026_05:10/all/all"


def test_agent_cannot_set_source_url_id_or_delay_model():
    result = check([raw(
        source="fixture", id="x", url="https://evil.example/pay",
        delay_model={"p_on_time": 1, "mean_delay_min": 0, "p95_delay_min": 0},
    )])
    t = result.accepted[0]
    assert t.source == "koleo" and t.id == "tr_wro_1004_0510"
    assert t.url.startswith("https://koleo.pl/")
    assert t.delay_model.p_on_time == 0.7


def test_source_is_the_one_given_by_the_provider():
    assert check([raw()], source="playwright").accepted[0].source == "playwright"


def test_time_without_timezone_is_rejected():
    assert "dep" in only_reason([raw(dep="2026-10-04T05:10:00")])


@pytest.mark.parametrize("overrides, reason", [
    ({"arr": "2026-10-04T05:10:00+02:00"}, "arrival is not after departure"),
    ({"arr": "2026-10-04T05:20:00+02:00"}, "implausible trip duration"),
    ({"arr": "2026-10-05T23:00:00+02:00"}, "implausible trip duration"),
    ({"dep": "2025-10-04T05:10:00+02:00", "arr": "2025-10-04T08:15:00+02:00"}, "departure outside the search window"),
    ({"price_pln": -5}, "implausible price"),
    ({"price_pln": 0}, "implausible price"),
    ({"price_pln": 5000}, "implausible price"),
    ({"changes": 9}, "implausible number of changes"),
    ({"category": "XYZ"}, "unknown category XYZ"),
    ({"category": "IC+XYZ"}, "unknown category XYZ"),
    ({"category": " "}, "empty category"),
    ({"from": "Gdańsk Główny"}, "route does not match the request"),
    ({"to": "Warszawa Centralna"}, "route does not match the request"),
])
def test_bad_option_is_rejected_with_reason(overrides, reason):
    assert only_reason([raw(**overrides)]) == reason


def test_unknown_price_is_allowed():
    assert check([raw(price_pln=None)]).accepted[0].price_pln is None


def test_station_names_match_without_diacritics_and_use_the_requested_spelling():
    t = check([raw(**{"from": "wroclaw glowny", "to": "KRAKOW GLOWNY"})]).accepted[0]
    assert (t.from_, t.to) == (ORIGIN, DEST)


@pytest.mark.parametrize("dep, arr", [
    ("2026-10-04T05:10:00+00:00", "2026-10-04T08:15:00+00:00"),  # local time labelled as UTC
    ("2026-10-04T03:10:00Z", "2026-10-04T06:15:00Z"),            # a correct instant, still not local
    ("2026-10-04T05:10:00+01:00", "2026-10-04T08:15:00+01:00"),  # winter offset in the summer-time period
    ("2026-10-04T05:10:00+02:00", "2026-10-04T08:15:00+00:00"),  # arrival only
])
def test_offset_other_than_warsaw_is_rejected(dep, arr):
    assert only_reason([raw(dep=dep, arr=arr)]) == "time zone offset is not Europe/Warsaw"


def test_winter_offset_is_accepted_after_the_clock_change():
    # DST ends on 2026-10-25: +01:00 is the correct local offset from then on.
    window = (datetime.fromisoformat("2026-10-20T00:00:00+02:00"), datetime.fromisoformat("2026-11-01T00:00:00+01:00"))
    result = validate_options(
        [raw(dep="2026-10-26T05:10:00+01:00", arr="2026-10-26T08:15:00+01:00")],
        origin=ORIGIN, destination=DEST, window=window, source="koleo", fetched_at=FETCHED_AT,
    )
    assert len(result.accepted) == 1 and "26-10-2026_05:10" in result.accepted[0].url


@pytest.mark.parametrize("overrides", [
    {"category": "IC+KŚ", "changes": 0},   # two vehicles, no change
    {"category": "IC", "changes": 1},      # one vehicle, one change
    {"category": "KM+KM+FLIX", "changes": 1},
])
def test_number_of_changes_must_match_the_category(overrides):
    assert only_reason([raw(**overrides)]) == "number of changes does not match the category"


@pytest.mark.parametrize("overrides, field", [
    ({"price_pln": True}, "price_pln"),
    ({"changes": True}, "changes"),
])
def test_boolean_is_not_a_number(overrides, field):
    assert only_reason([raw(**overrides)]).startswith(f"invalid field {field}")


def test_integer_price_is_fine():
    assert check([raw(price_pln=64)]).accepted[0].price_pln == 64.0


def test_ids_stay_unique_for_same_departure_and_category_with_another_arrival():
    result = check([raw(), raw(arr="2026-10-04T08:45:00+02:00"), raw(arr="2026-10-04T09:00:00+02:00")])
    ids = [t.id for t in result.accepted]
    assert len(ids) == 3 and len(set(ids)) == 3


def test_duplicates_are_dropped():
    result = check([raw(), raw()])
    assert len(result.accepted) == 1
    assert result.rejected[0].reason == "duplicate option"


def test_same_departure_different_category_gets_distinct_ids():
    result = check([raw(), raw(category="FLIX", arr="2026-10-04T09:00:00+02:00")])
    assert sorted(t.id for t in result.accepted) == ["tr_wro_1004_0510_flix", "tr_wro_1004_0510_ic"]
    assert {t.mode for t in result.accepted} == {"train", "bus"}


def test_change_makes_the_delay_model_worse():
    plain = check([raw()]).accepted[0].delay_model
    with_change = check([raw(category="IC+EIP", changes=1)]).accepted[0]
    assert with_change.category == "IC+EIP" and with_change.changes == 1
    assert with_change.delay_model.p_on_time < plain.p_on_time
    assert with_change.delay_model.p95_delay_min > plain.p95_delay_min


@pytest.mark.parametrize("response", [{"options": []}, "oops", None, 5])
def test_response_that_is_not_a_list_is_rejected(response):
    result = check(response)
    assert result.accepted == [] and result.rejected[0].reason == "response is not a list"


def test_item_that_is_not_an_object_is_rejected():
    assert check(["IC 05:10"]).rejected[0].reason.startswith("invalid field")


def test_good_items_survive_next_to_bad_ones():
    result = check([raw(), raw(price_pln=-1), raw(dep="2026-10-04T06:10:00+02:00", arr="2026-10-04T09:23:00+02:00")])
    assert len(result.accepted) == 2 and len(result.rejected) == 1
    assert result.rejected[0].index == 1


def test_fallback_reason_summarizes_rejections():
    result = check([raw(), raw(price_pln=-1), raw(category="XYZ")])
    reason = result.fallback_reason()
    assert reason.startswith("validator rejected 2/3 options")
    assert "implausible price" in reason and "unknown category XYZ" in reason


def test_koleo_slug_and_url():
    assert koleo_slug("Wrocław Główny") == "wroclaw-glowny"
    assert koleo_slug("Poznań Główny") == "poznan-glowny"
    assert koleo_slug("Katowice") == "katowice"
    dep = datetime.fromisoformat("2026-10-03T16:10:00+02:00")
    assert koleo_url(ORIGIN, DEST, dep).endswith("/03-10-2026_16:10/all/all")


@pytest.mark.parametrize("path", sorted((FIXTURES_DIR / "trains").glob("*.json")), ids=lambda p: p.stem)
def test_recorded_fixtures_are_what_the_validator_would_build_from_the_same_facts(path):
    """A live result must look like a recorded one: same ids, urls and delay models."""
    recorded = [TrainOption.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))]
    origin = recorded[0].from_
    facts = [
        {"category": t.category, "from": t.from_, "to": t.to, "dep": t.dep.isoformat(),
         "arr": t.arr.isoformat(), "price_pln": t.price_pln, "changes": t.changes}
        for t in recorded
    ]
    result = validate_options(
        facts, origin=origin, destination=DEST, window=WINDOW, source="koleo", fetched_at=FETCHED_AT
    )
    assert result.rejected == []
    built = {t.id: t for t in result.accepted}
    assert set(built) == {t.id for t in recorded}
    for t in recorded:
        expected = t.model_copy(update={"source": "koleo", "fetched_at": FETCHED_AT})
        assert built[t.id] == expected
