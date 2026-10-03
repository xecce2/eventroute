"""Live provider for the planner (F): reads Koleo and returns the Validator's result.

Plugged in by `services.make_provider` when TRAIN_PROVIDER=koleo (see `LiveProvider` in base.py).
`fetch` raises on a failed fetch; the chain then falls back to the recorded data with the
exception text as the reason. Nothing here ever returns fixtures, and every option is tagged with
the reader that really produced it:

* Playwright opens the pages and `koleo_parser` reads them by fixed rules: source "playwright".
* If the parser finds no trips on a page that did load (Koleo changed its layout), the text of
  that same page goes to Gemini: source "koleo". Gemini's rows are grounded on the page first.
* If the browser cannot load a page at all (network, block, captcha) nothing can read it, Gemini
  included, and the search fails. A block is never worked around.
"""
import logging
import os
import threading
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import date, datetime, time as clock_time, timedelta

from app import config
from app.providers.gemini_extractor import GeminiError, GeminiExtractor
from app.providers.koleo_fetcher import BrowserSession, KoleoFetchError, PageReader
from app.providers.koleo_parser import WARSAW, merge_rows, parse_page
from app.providers.validator import ValidationResult, koleo_slug, koleo_url, validate_options

log = logging.getLogger(__name__)

SEARCH_FROM = clock_time(16, 0)    # the evening before the event, as in the planner
COVER_UNTIL = clock_time(8, 30)    # departures after this cannot reach the entrance by 09:30
MAX_PAGES = 8                      # one results page holds about 12 to 30 trips
CACHE_TTL_SEC = float(os.getenv("KOLEO_CACHE_TTL_SEC", "900"))
# Koleo needs about 10 to 15 s per page and a search reads 3 to 5 pages.
SEARCH_TIMEOUT_SEC = float(os.getenv("KOLEO_TIMEOUT_SEC", "100"))
PAGE_BUDGET_SEC = 30.0
# Tried in this order: the free models are often overloaded (503) or retired (404).
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash,gemini-3.7-flash,gemini-3.5-flash")
GEMINI_ROW = "koleo"               # marks rows read by Gemini inside a row dict (the Validator ignores it)

SessionFactory = Callable[[], AbstractContextManager[PageReader]]


class KoleoAgentProvider:  # satisfies the `LiveProvider` protocol (base.py)
    def __init__(
        self,
        api_key: str = "",
        session_factory: SessionFactory = BrowserSession,
        cache_ttl_sec: float = CACHE_TTL_SEC,
        timeout_sec: float = SEARCH_TIMEOUT_SEC,
        clock: Callable[[], datetime] = lambda: datetime.now(WARSAW),
        gemini: GeminiExtractor | None = None,
    ):
        self.session_factory = session_factory
        self.cache_ttl_sec = cache_ttl_sec
        self.timeout_sec = timeout_sec
        self.clock = clock
        # No key, no backup reader: the code parser alone.
        self.gemini = gemini if gemini is not None else (GeminiExtractor(api_key, GEMINI_MODEL) if api_key else None)
        self.pages_by_parser = 0
        self.pages_by_gemini = 0
        self._cache: dict[tuple, tuple[float, ValidationResult]] = {}
        self._lock = threading.Lock()

    def fetch(self, origin: str, destination: str, day: date) -> ValidationResult:
        key = (koleo_slug(origin), koleo_slug(destination), day)
        with self._lock:
            hit = self._cache.get(key)
            if hit and time.monotonic() - hit[0] < self.cache_ttl_sec:
                return hit[1]

        rows = self._collect(origin, destination, day)
        window = (
            datetime.combine(day - timedelta(days=1), clock_time(0, 0), tzinfo=WARSAW),
            datetime.combine(day, clock_time(23, 59), tzinfo=WARSAW),
        )
        fetched_at = self.clock()
        by_gemini = [row for row in rows if row.get("_reader") == GEMINI_ROW]
        by_parser = [row for row in rows if row.get("_reader") != GEMINI_ROW]
        result = ValidationResult()
        for batch, source in ((by_parser, "playwright"), (by_gemini, "koleo")):
            if batch:
                part = validate_options(batch, origin=origin, destination=destination, window=window,
                                        source=source, fetched_at=fetched_at)
                result.accepted += part.accepted
                result.rejected += part.rejected
        _make_ids_unique(result)

        if result.accepted:
            with self._lock:
                self._cache[key] = (time.monotonic(), result)
        return result

    def _collect(self, origin: str, destination: str, day: date) -> list[dict]:
        """Read result pages one after another until the departures reach COVER_UNTIL.

        Each next page starts at the last departure of the previous one, so no trip falls into
        a gap however dense the route is (Katowice has about 20 trips per page, Wrocław 12).
        """
        start = datetime.combine(day - timedelta(days=1), SEARCH_FROM, tzinfo=WARSAW)
        until = datetime.combine(day, COVER_UNTIL, tzinfo=WARSAW)
        deadline = time.monotonic() + self.timeout_sec
        pages: list[list[dict]] = []
        with self.session_factory() as session:
            cursor = start
            for _ in range(MAX_PAGES):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"search took longer than {self.timeout_sec:.0f} s")
                text = session.text(koleo_url(origin, destination, cursor), min(remaining, PAGE_BUDGET_SEC))
                rows = self._read_page(text, origin, destination, cursor.year)
                if not rows:
                    break
                pages.append(rows)
                last_dep = max(datetime.fromisoformat(row["dep"]) for row in rows)
                if last_dep >= until or last_dep <= cursor:
                    break
                cursor = last_dep
        if not pages:
            raise KoleoFetchError("Koleo returned no trips")
        return merge_rows(pages)

    def _read_page(self, text: str, origin: str, destination: str, year: int) -> list[dict]:
        page = parse_page(text, origin, destination, year)
        if page.origin is not None and (
            koleo_slug(page.origin) != koleo_slug(origin)
            or koleo_slug(page.destination or "") != koleo_slug(destination)
        ):
            # A page of another route is never read by anyone.
            raise KoleoFetchError(f"unexpected page header {page.origin!r} -> {page.destination!r}")
        if page.skipped:
            log.warning("koleo parser skipped %d rows: %s", len(page.skipped), page.skipped[:3])
        if page.rows:
            self.pages_by_parser += 1
            return page.rows

        # The page loaded but the parser found no trips: the layout may have changed.
        if self.gemini is None:
            if page.origin is None:
                raise KoleoFetchError("no timetable on the page (blocked or the layout changed)")
            return []  # a real page with no trips: the end of the timetable
        try:
            extraction = self.gemini.extract(text, origin, destination, year)
        except GeminiError as e:
            raise KoleoFetchError(f"the parser found no trips and Gemini failed: {e}") from None
        if extraction.dropped:
            log.warning("gemini rows dropped (%d): %s", len(extraction.dropped), extraction.dropped[:3])
        if not extraction.rows:
            if page.origin is None:
                raise KoleoFetchError("no timetable on the page (blocked or the layout changed)")
            return []
        log.warning("koleo layout fallback: the page was read by Gemini (%d trips)", len(extraction.rows))
        self.pages_by_gemini += 1
        return [dict(row, _reader=GEMINI_ROW) for row in extraction.rows]


def _make_ids_unique(result: ValidationResult) -> None:
    """Ids are unique inside each reader's batch; keep them unique across the two batches too."""
    seen: set[str] = set()
    for i, option in enumerate(result.accepted):
        new_id, n = option.id, 2
        while new_id in seen:
            new_id, n = f"{option.id}_{n}", n + 1
        seen.add(new_id)
        if new_id != option.id:
            result.accepted[i] = option.model_copy(update={"id": new_id})
