import json
import os
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

import httpx
import pytest

from app.providers.gemini_extractor import Extraction, GeminiError, GeminiExtractor, ground
from app.providers.koleo_agent import KoleoAgentProvider
from app.providers.koleo_fetcher import KoleoFetchError
from app.providers.koleo_parser import parse_page

DATA = Path(__file__).parent / "data" / "koleo"
ORIGIN, DEST = "Wrocław Główny", "Kraków Główny"
DAY = date(2026, 10, 4)
KEY = "AIza-test-key-123456789"
NOW = datetime.fromisoformat("2026-10-03T18:00:00+02:00")


def page() -> str:
    return (DATA / "wroclaw_0000.txt").read_text(encoding="utf-8")


def items_for(rows: list[dict]) -> list[dict]:
    """What a faithful model would return for these parser rows."""
    return [{
        "dep_date": r["dep"][:10], "dep_time": r["dep"][11:16], "arr_time": r["arr"][11:16],
        "changes": r["changes"], "categories": r["category"].split("+"),
        "price_text": None if r["price_pln"] is None else f"{r['price_pln']:.2f}".replace(".", ",") + " zł",
    } for r in rows]


REAL_ROWS = parse_page(page(), ORIGIN, DEST, 2026).rows
REAL_ITEMS = items_for(REAL_ROWS)


def gemini_answer(items) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(items)}]}}]}


def extractor(handler, model="m1,m2,m3") -> GeminiExtractor:
    return GeminiExtractor(KEY, model, client=httpx.Client(transport=httpx.MockTransport(handler)))


# ---------- the request ----------

def test_the_request_is_strict_and_keeps_the_key_in_a_header_only():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=gemini_answer(REAL_ITEMS))

    result = extractor(handler, "gemini-x").extract(page(), ORIGIN, DEST, 2026)
    request = seen[0]
    body = json.loads(request.content)
    assert request.url.path.endswith("/models/gemini-x:generateContent")
    assert request.headers["x-goog-api-key"] == KEY and KEY not in str(request.url) and KEY not in request.content.decode()
    config = body["generationConfig"]
    assert config["temperature"] == 0 and config["responseMimeType"] == "application/json" and "responseSchema" in config
    prompt = body["contents"][0]["parts"][0]["text"]
    assert "<page>" in prompt and "</page>" in prompt and "Bezpośrednie" in prompt
    assert "untrusted" in body["systemInstruction"]["parts"][0]["text"]
    assert len(result.rows) == len(REAL_ROWS) and result.dropped == []


def test_faithful_answer_equals_the_code_parser():
    result = extractor(lambda r: httpx.Response(200, json=gemini_answer(REAL_ITEMS))).extract(page(), ORIGIN, DEST, 2026)
    assert result.rows == REAL_ROWS


# ---------- grounding: nothing that is not on the page gets through ----------

def ground_one(**overrides):
    item = dict(REAL_ITEMS[0], **overrides)
    return ground([item], page(), ORIGIN, DEST)


def test_a_row_that_is_on_the_page_passes():
    assert len(ground_one().rows) == 1


@pytest.mark.parametrize("overrides, why", [
    ({"dep_time": "04:44", "arr_time": "05:55"}, "times are not on the page"),
    ({"arr_time": "08:16"}, "times are not on the page"),
    ({"categories": ["XYZ"]}, "category is not on the page"),
    ({"dep_date": "2026-11-20"}, "date header is not on the page"),
    ({"price_text": "1,00 zł"}, "price is not on the page"),
    ({"price_text": "cheap"}, "price is not on the page"),
    ({"changes": 1}, "changes do not match"),
    ({"changes": True}, "bad changes"),
    ({"categories": []}, "bad changes or categories"),
    ({"dep_time": "25:99"}, "malformed"),
    ({"dep_date": "tomorrow"}, "malformed"),
])
def test_an_ungrounded_or_malformed_row_is_dropped_with_a_reason(overrides, why):
    result = ground_one(**overrides)
    assert result.rows == [] and why in result.dropped[0]


def test_missing_field_and_non_object_are_dropped():
    broken = {k: v for k, v in REAL_ITEMS[0].items() if k != "arr_time"}
    result = ground([broken, "IC 05:10", None], page(), ORIGIN, DEST)
    assert result.rows == [] and len(result.dropped) == 3


def test_an_invented_trip_is_dropped_next_to_real_ones():
    invented = dict(REAL_ITEMS[0], dep_time="04:04", arr_time="05:05")
    result = ground([REAL_ITEMS[1], invented, REAL_ITEMS[2]], page(), ORIGIN, DEST)
    assert len(result.rows) == 2 and len(result.dropped) == 1


def test_the_code_decides_the_arrival_date_and_the_price_number():
    text = "PKP A — B\n3 października\n20:01\n00:23\n4h 22min\nBezpośrednie\nFLIX\nKup bilet\n1 234,50 zł"
    item = {"dep_date": "2026-10-03", "dep_time": "20:01", "arr_time": "00:23", "changes": 0,
            "categories": ["FLIX"], "price_text": "1 234,50 zł", "arr_date": "1999-01-01"}
    row = ground([item], text, "A", "B").rows[0]
    assert row["arr"] == "2026-10-04T00:23:00+02:00" and row["price_pln"] == 1234.5


def test_a_trip_without_a_price_stays_null():
    item = next(i for i in items_for(parse_page((DATA / "katowice_0500.txt").read_text(encoding="utf-8"), "Katowice", DEST, 2026).rows)
                if i["price_text"] is None)
    text = (DATA / "katowice_0500.txt").read_text(encoding="utf-8")
    assert ground([item], text, "Katowice", DEST).rows[0]["price_pln"] is None


# ---------- models that fail ----------

def calls_and_handler(*statuses):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path.split("/models/")[1].split(":")[0])
        status = statuses[min(len(calls), len(statuses)) - 1]
        if status == 200:
            return httpx.Response(200, json=gemini_answer(REAL_ITEMS))
        return httpx.Response(status, json={"error": {"message": f"detail {status} for key {KEY}"}})

    return calls, handler


@pytest.mark.parametrize("failing", [503, 429, 404, 500])
def test_the_next_model_is_tried_when_one_is_overloaded_limited_or_retired(failing):
    calls, handler = calls_and_handler(failing, failing, 200)
    ex = extractor(handler)
    assert len(ex.extract(page(), ORIGIN, DEST, 2026).rows) == len(REAL_ROWS)
    assert calls == ["m1", "m2", "m3"] and ex.last_model == "m3"


def test_all_models_failing_is_one_clear_error_without_the_key():
    calls, handler = calls_and_handler(503)
    with pytest.raises(GeminiError) as error:
        extractor(handler).extract(page(), ORIGIN, DEST, 2026)
    assert calls == ["m1", "m2", "m3"]
    assert "m1: HTTP 503" in str(error.value) and KEY not in str(error.value)


@pytest.mark.parametrize("status", [400, 401, 403])
def test_a_wrong_key_stops_at_once_and_never_echoes_it(status):
    calls, handler = calls_and_handler(status)
    with pytest.raises(GeminiError) as error:
        extractor(handler).extract(page(), ORIGIN, DEST, 2026)
    assert calls == ["m1"]  # the same key would fail on every model
    assert str(status) in str(error.value)


def test_an_answer_that_is_not_json_moves_on_to_the_next_model():
    bad = {"candidates": [{"content": {"parts": [{"text": "Sure! Here are the trips: ..."}]}}]}
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json=bad if len(calls) == 1 else gemini_answer(REAL_ITEMS))

    assert len(extractor(handler).extract(page(), ORIGIN, DEST, 2026).rows) == len(REAL_ROWS)
    assert len(calls) == 2


def test_a_network_error_moves_on_and_hides_the_url():
    def handler(request):
        raise httpx.ConnectError(f"cannot reach {request.url}")

    with pytest.raises(GeminiError) as error:
        extractor(handler).extract(page(), ORIGIN, DEST, 2026)
    assert "ConnectError" in str(error.value) and "generativelanguage" not in str(error.value) and KEY not in str(error.value)


def test_models_can_be_given_as_a_list_or_a_comma_string_and_not_empty():
    assert GeminiExtractor(KEY, "a, b ,,c").models == ["a", "b", "c"]
    assert GeminiExtractor(KEY, ["a", "b"]).models == ["a", "b"]
    with pytest.raises(ValueError):
        GeminiExtractor(KEY, " , ")


# ---------- the provider: Gemini is only the backup reader ----------

class FakeSession:
    def __init__(self, *pages):
        self.pages, self.calls = pages, 0

    def text(self, url, timeout_sec=30.0):
        self.calls += 1
        return self.pages[min(self.calls, len(self.pages)) - 1]


class FakeGemini:
    def __init__(self, rows=None, error=None):
        self.rows, self.error, self.calls = rows or [], error, 0
        self.last_model = "fake"

    def extract(self, page_text, origin, destination, year):
        self.calls += 1
        if self.error:
            raise self.error
        return Extraction(rows=[dict(r) for r in self.rows], dropped=[])


def provider(session, gemini):
    @contextmanager
    def factory():
        yield session

    return KoleoAgentProvider(session_factory=factory, cache_ttl_sec=0, clock=lambda: NOW, gemini=gemini)


CHANGED_LAYOUT = page().replace("Bezpośrednie", "Direct").replace("przesiadka", "change")


def test_when_the_parser_reads_the_page_gemini_is_never_called():
    gemini = FakeGemini()
    p = provider(FakeSession(page()), gemini)
    result = p.fetch(ORIGIN, DEST, DAY)
    assert gemini.calls == 0 and p.pages_by_parser == 1 and p.pages_by_gemini == 0
    assert {t.source for t in result.accepted} == {"playwright"}


def test_when_the_layout_changed_gemini_reads_the_same_page_and_the_source_says_so():
    gemini = FakeGemini(rows=REAL_ROWS)
    p = provider(FakeSession(CHANGED_LAYOUT), gemini)
    result = p.fetch(ORIGIN, DEST, DAY)
    assert gemini.calls == 1 and p.pages_by_gemini == 1 and p.pages_by_parser == 0
    assert len(result.accepted) == len(REAL_ROWS) and result.rejected == []
    assert {t.source for t in result.accepted} == {"koleo"}
    assert all(t.url.startswith("https://koleo.pl/") for t in result.accepted)  # built by code, as always


def test_gemini_rows_still_go_through_the_validator():
    bad = dict(REAL_ROWS[0], category="XYZ", price_pln=-5.0)
    result = provider(FakeSession(CHANGED_LAYOUT), FakeGemini(rows=[REAL_ROWS[1], bad])).fetch(ORIGIN, DEST, DAY)
    assert len(result.accepted) == 1 and result.rejected[0].reason in ("unknown category XYZ", "implausible price")


def test_a_failed_gemini_is_a_failed_search_with_a_reason():
    p = provider(FakeSession(CHANGED_LAYOUT), FakeGemini(error=GeminiError("no Gemini model answered (m1: HTTP 503)")))
    with pytest.raises(KoleoFetchError, match="parser found no trips and Gemini failed"):
        p.fetch(ORIGIN, DEST, DAY)


@pytest.mark.parametrize("text", ["", "Captcha: confirm you are not a robot"])
def test_a_blocked_page_is_not_worked_around_with_or_without_gemini(text):
    for gemini in (None, FakeGemini(rows=[])):
        with pytest.raises(KoleoFetchError, match="no timetable"):
            provider(FakeSession(text), gemini).fetch(ORIGIN, DEST, DAY)


def test_without_a_key_there_is_no_backup_reader():
    assert KoleoAgentProvider().gemini is None
    assert KoleoAgentProvider(api_key=KEY).gemini.models[0].startswith("gemini")


def test_pages_may_be_read_by_different_readers_and_ids_stay_unique():
    second_page = CHANGED_LAYOUT
    p = provider(FakeSession(
        "PKP Wrocław Główny — Kraków Główny\n3 października\n16:10\n19:27\n3h 17min\nBezpośrednie\nIC\nKup bilet\n63,00 zł",
        second_page,
    ), FakeGemini(rows=REAL_ROWS))
    result = p.fetch(ORIGIN, DEST, DAY)
    assert {t.source for t in result.accepted} == {"playwright", "koleo"}
    ids = [t.id for t in result.accepted]
    assert len(ids) == len(set(ids))


# ---------- real Gemini, only on request ----------

@pytest.mark.skipif(not os.getenv("LIVE_TESTS"), reason="calls the Gemini API: set LIVE_TESTS=1 (needs GEMINI_API_KEY)")
def test_live_gemini_reads_a_real_page_like_the_parser():
    from app import config
    from app.providers.koleo_agent import GEMINI_MODEL

    result = GeminiExtractor(config.GEMINI_API_KEY, GEMINI_MODEL).extract(page(), ORIGIN, DEST, 2026)
    assert result.rows == REAL_ROWS
