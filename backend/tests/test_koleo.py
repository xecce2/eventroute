import os
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

import pytest

from app.providers.koleo_agent import KoleoAgentProvider
from app.providers.koleo_fetcher import KoleoFetchError
from app.providers.koleo_parser import WARSAW, merge_rows, parse_page

DATA = Path(__file__).parent / "data" / "koleo"
ORIGIN, DEST = "Wrocław Główny", "Kraków Główny"
DAY = date(2026, 10, 4)
NOW = datetime.fromisoformat("2026-10-03T17:00:00+02:00")


def sample(name: str) -> str:
    return (DATA / name).read_text(encoding="utf-8")


def page_text(origin: str, destination: str, trips: list[tuple]) -> str:
    """A page shaped like Koleo's. trip = (october_day, dep, arr, minutes, [categories], price | None)."""
    lines = [f"PKP {origin} — {destination}", "ROZKŁAD JAZDY I BILETY", "Znajdź połączenie", "Wcześniejsze połączenia"]
    current = None
    for day, dep, arr, minutes, cats, price in trips:
        if day != current:
            lines += ["SOBOTA" if day == 3 else "NIEDZIELA", f"{day} października"]
            current = day
        lines += [dep, arr, f"{minutes // 60}h {minutes % 60}min"]
        lines.append("Bezpośrednie" if len(cats) <= 1 else f"{len(cats) - 1} przesiadka")
        lines += cats
        if price is not None:
            lines += ["Kup bilet", f"{price:.2f}".replace(".", ",") + " zł"]
    lines.append("Późniejsze połączenia")
    return "\n".join(lines)


def parse(name: str, origin: str = ORIGIN):
    return parse_page(sample(name), origin, DEST, 2026)


# ---------- parser on real pages ----------

@pytest.mark.parametrize("name, origin, rows", [
    ("wroclaw_0400.txt", ORIGIN, 26),
    ("wroclaw_0000.txt", ORIGIN, 27),
    ("katowice_0500.txt", "Katowice", 19),
])
def test_real_pages_are_read_completely(name, origin, rows):
    page = parse(name, origin)
    assert (page.origin, page.destination) == (origin, DEST)
    assert len(page.rows) == rows
    assert page.skipped == []


def test_a_direct_trip_with_a_price():
    first = parse("wroclaw_0400.txt").rows[0]
    assert first == {
        "category": "IC", "from": ORIGIN, "to": DEST,
        "dep": "2026-10-04T05:10:00+02:00", "arr": "2026-10-04T08:15:00+02:00",
        "price_pln": 64.0, "changes": 0,
    }


def test_a_trip_with_a_change_has_both_categories():
    row = next(r for r in parse("wroclaw_0000.txt").rows if r["dep"].endswith("03:48:00+02:00"))
    assert (row["category"], row["changes"], row["price_pln"]) == ("IC+KŚ", 1, 73.93)
    assert row["arr"] == "2026-10-04T07:39:00+02:00"


def test_a_trip_without_a_price_keeps_null():
    page = parse("katowice_0500.txt", "Katowice")
    row = next(r for r in page.rows if r["dep"].endswith("07:05:00+02:00"))
    assert (row["category"], row["price_pln"]) == ("FLIX", None)
    assert [r["dep"][11:16] for r in page.rows if r["price_pln"] is None] == ["07:05"]


# ---------- parser edge cases ----------

def test_price_with_a_non_breaking_space_and_thousands():
    text = page_text(ORIGIN, DEST, [(4, "05:10", "08:15", 185, ["IC"], 64.0)])
    assert parse_page(text, ORIGIN, DEST, 2026).rows[0]["price_pln"] == 64.0
    thousands = text.replace("64,00 zł", "1 234,50 zł")
    assert parse_page(thousands, ORIGIN, DEST, 2026).rows[0]["price_pln"] == 1234.5


def test_arrival_after_midnight_is_on_the_next_day():
    text = page_text(ORIGIN, DEST, [(3, "20:01", "00:23", 262, ["FLIX"], 85.98)])
    row = parse_page(text, ORIGIN, DEST, 2026).rows[0]
    assert (row["dep"], row["arr"]) == ("2026-10-03T20:01:00+02:00", "2026-10-04T00:23:00+02:00")


def test_a_weekday_header_after_a_trip_without_a_price_is_not_a_category():
    text = page_text(ORIGIN, DEST, [
        (3, "23:21", "04:08", 287, ["FLIX"], None),   # no price: the next line is the weekday header
        (4, "00:21", "04:38", 257, ["FLIX"], 85.98),
    ])
    rows = parse_page(text, ORIGIN, DEST, 2026).rows
    assert [(r["dep"][8:16], r["category"]) for r in rows] == [("03T23:21", "FLIX"), ("04T00:21", "FLIX")]


@pytest.mark.parametrize("trip, why", [
    ((4, "05:10", "08:15", 90, ["IC"], 64.0), "duration"),            # 3h 5min on the page would be 185
    ((4, "05:10", "08:15", 185, [], 64.0), "no category"),
])
def test_inconsistent_rows_are_skipped_not_guessed(trip, why):
    page = parse_page(page_text(ORIGIN, DEST, [trip]), ORIGIN, DEST, 2026)
    assert page.rows == [] and len(page.skipped) == 1 and why in page.skipped[0]


def test_changes_must_match_the_categories():
    text = page_text(ORIGIN, DEST, [(4, "05:10", "08:15", 185, ["IC"], 64.0)]).replace("Bezpośrednie", "1 przesiadka")
    page = parse_page(text, ORIGIN, DEST, 2026)
    assert page.rows == [] and "changes" in page.skipped[0]


@pytest.mark.parametrize("text", ["", "Captcha: confirm you are not a robot", "Rozkład jazdy\nBrak połączeń"])
def test_a_page_without_a_timetable_has_no_header_and_no_rows(text):
    page = parse_page(text, ORIGIN, DEST, 2026)
    assert page.origin is None and page.rows == []


def test_merge_keeps_one_row_per_trip_and_prefers_the_one_with_a_price():
    a = {"category": "IC", "dep": "2026-10-04T05:10:00+02:00", "arr": "2026-10-04T08:15:00+02:00", "price_pln": None}
    b = dict(a, price_pln=64.0)
    c = dict(a, dep="2026-10-04T03:10:00+02:00", arr="2026-10-04T06:34:00+02:00")
    merged = merge_rows([[a, c], [b]])
    assert [(r["dep"][11:16], r["price_pln"]) for r in merged] == [("03:10", None), ("05:10", 64.0)]


# ---------- provider on a fake browser ----------

class FakeSession:
    def __init__(self, pages):
        self.pages, self.urls = pages, []

    def text(self, url, timeout_sec=30.0):
        self.urls.append(url)
        return self.pages[min(len(self.urls), len(self.pages)) - 1]


def provider(pages, ttl=900.0, timeout=100.0):
    session = FakeSession(pages)
    opened = []

    @contextmanager
    def factory():
        opened.append(1)
        yield session

    return KoleoAgentProvider(session_factory=factory, cache_ttl_sec=ttl, timeout_sec=timeout,
                              clock=lambda: NOW), session, opened


def test_one_page_that_reaches_the_morning_is_enough():
    p, session, _ = provider([sample("wroclaw_0000.txt")])
    result = p.fetch(ORIGIN, DEST, DAY)
    assert result.rejected == [] and len(result.accepted) == 27
    assert len(session.urls) == 1 and "03-10-2026_16:00" in session.urls[0]
    assert {t.source for t in result.accepted} == {"playwright"}
    assert all(t.url.startswith("https://koleo.pl/") for t in result.accepted)
    assert result.accepted[0].fetched_at == NOW


def test_pages_are_read_until_the_morning_and_overlaps_are_merged():
    evening = page_text(ORIGIN, DEST, [(3, "16:10", "19:27", 197, ["IC"], 63.0), (3, "20:53", "23:43", 170, ["IC"], 64.0)])
    night = page_text(ORIGIN, DEST, [(3, "20:53", "23:43", 170, ["IC"], 64.0), (4, "03:10", "06:34", 204, ["IC"], 64.0)])
    morning = page_text(ORIGIN, DEST, [(4, "03:10", "06:34", 204, ["IC"], 64.0), (4, "08:40", "11:30", 170, ["IC"], 63.0)])
    p, session, _ = provider([evening, night, morning])
    result = p.fetch(ORIGIN, DEST, DAY)
    assert len(session.urls) == 3
    assert "03-10-2026_20:53" in session.urls[1] and "04-10-2026_03:10" in session.urls[2]  # each starts at the last departure
    assert [t.dep.isoformat()[5:16] for t in result.accepted] == ["10-03T16:10", "10-03T20:53", "10-04T03:10", "10-04T08:40"]
    assert result.rejected == []


def test_the_page_of_another_route_is_refused():
    p, _, _ = provider([page_text("Poznań Główny", DEST, [(4, "05:10", "08:15", 185, ["IC"], 64.0)])])
    with pytest.raises(KoleoFetchError, match="unexpected page header"):
        p.fetch(ORIGIN, DEST, DAY)


@pytest.mark.parametrize("text", ["", "Captcha: confirm you are not a robot"])
def test_a_page_without_a_timetable_raises_and_is_never_worked_around(text):
    p, _, _ = provider([text])
    with pytest.raises(KoleoFetchError):
        p.fetch(ORIGIN, DEST, DAY)


def test_a_page_with_a_header_but_no_trips_raises():
    p, _, _ = provider([page_text(ORIGIN, DEST, [])])
    with pytest.raises(KoleoFetchError, match="no trips"):
        p.fetch(ORIGIN, DEST, DAY)


def test_the_search_has_an_overall_time_limit():
    p, _, _ = provider([sample("wroclaw_0000.txt")], timeout=0.0)
    with pytest.raises(TimeoutError):
        p.fetch(ORIGIN, DEST, DAY)


def test_bad_options_are_rejected_by_the_validator_and_the_rest_survive():
    text = page_text(ORIGIN, DEST, [(4, "05:10", "08:15", 185, ["IC"], 64.0), (4, "06:10", "09:23", 193, ["XYZ"], 63.0)])
    result = provider([text])[0].fetch(ORIGIN, DEST, DAY)
    assert len(result.accepted) == 1 and result.rejected[0].reason == "unknown category XYZ"
    assert "validator rejected 1/2" in result.fallback_reason()


def test_results_are_cached_for_the_ttl():
    p, session, opened = provider([sample("wroclaw_0000.txt")])
    first = p.fetch(ORIGIN, DEST, DAY)
    second = p.fetch("wroclaw glowny", "krakow glowny", DAY)  # same trip without diacritics: same key
    assert second is first and len(opened) == 1 and len(session.urls) == 1


def test_a_zero_ttl_means_every_call_reads_again():
    p, session, opened = provider([sample("wroclaw_0000.txt")], ttl=0.0)
    p.fetch(ORIGIN, DEST, DAY)
    p.fetch(ORIGIN, DEST, DAY)
    assert len(opened) == 2 and len(session.urls) == 2


def test_a_failed_search_is_not_cached():
    p, _, opened = provider([""])
    for _ in range(2):
        with pytest.raises(KoleoFetchError):
            p.fetch(ORIGIN, DEST, DAY)
    assert len(opened) == 2


def test_parsed_times_use_the_warsaw_offset():
    t = provider([sample("wroclaw_0000.txt")])[0].fetch(ORIGIN, DEST, DAY).accepted[0]
    assert t.dep.utcoffset() == datetime(2026, 10, 4, tzinfo=WARSAW).utcoffset()


# ---------- real browser, only on request ----------

@pytest.mark.skipif(not os.getenv("LIVE_TESTS"), reason="opens a real browser on koleo.pl: set LIVE_TESTS=1")
def test_live_koleo_search_returns_options_with_prices():
    result = KoleoAgentProvider().fetch(ORIGIN, DEST, date(2026, 10, 4))
    assert result.accepted
    assert all(t.source == "playwright" for t in result.accepted)
    assert any(t.price_pln is not None for t in result.accepted)
