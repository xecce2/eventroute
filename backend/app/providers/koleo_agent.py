"""Live provider for the planner (F): reads Koleo and returns the Validator's result.

Plugged in by `services.make_provider` when TRAIN_PROVIDER=koleo (see `LiveProvider` in base.py).
`fetch` raises on a failed fetch; the chain then retries once and falls back to the recorded data
with the exception text as the reason. Nothing here ever returns fixtures or claims `koleo` for
data it did not read: options are tagged with the source that really produced them.

Current extraction: Playwright opens the pages and `koleo_parser` reads them by fixed rules
(source "playwright"). The Gemini step is added on top of the same pages.
"""
import logging
import os
import threading
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import date, datetime, time as clock_time, timedelta

from app import config  # noqa: F401  (loads .env before the settings below are read)
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

SessionFactory = Callable[[], AbstractContextManager[PageReader]]


class KoleoAgentProvider:  # satisfies the `LiveProvider` protocol (base.py)
    def __init__(
        self,
        api_key: str = "",
        session_factory: SessionFactory = BrowserSession,
        cache_ttl_sec: float = CACHE_TTL_SEC,
        timeout_sec: float = SEARCH_TIMEOUT_SEC,
        clock: Callable[[], datetime] = lambda: datetime.now(WARSAW),
    ):
        self.api_key = api_key  # reserved for the Gemini step
        self.session_factory = session_factory
        self.cache_ttl_sec = cache_ttl_sec
        self.timeout_sec = timeout_sec
        self.clock = clock
        self._cache: dict[tuple, tuple[float, ValidationResult]] = {}
        self._lock = threading.Lock()

    def fetch(self, origin: str, destination: str, day: date) -> ValidationResult:
        key = (koleo_slug(origin), koleo_slug(destination), day)
        with self._lock:
            hit = self._cache.get(key)
            if hit and time.monotonic() - hit[0] < self.cache_ttl_sec:
                return hit[1]

        rows = self._collect(origin, destination, day)
        result = validate_options(
            rows,
            origin=origin,
            destination=destination,
            window=(
                datetime.combine(day - timedelta(days=1), clock_time(0, 0), tzinfo=WARSAW),
                datetime.combine(day, clock_time(23, 59), tzinfo=WARSAW),
            ),
            source="playwright",
            fetched_at=self.clock(),
        )
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
                page = parse_page(text, origin, destination, year=cursor.year)
                if page.origin is None or koleo_slug(page.origin) != koleo_slug(origin) \
                        or koleo_slug(page.destination or "") != koleo_slug(destination):
                    raise KoleoFetchError(
                        f"unexpected page header {page.origin!r} -> {page.destination!r}: "
                        "no timetable (blocked or the layout changed)"
                    )
                if page.skipped:
                    log.warning("koleo parser skipped %d rows: %s", len(page.skipped), page.skipped[:3])
                if not page.rows:
                    break
                pages.append(page.rows)
                last_dep = max(datetime.fromisoformat(row["dep"]) for row in page.rows)
                if last_dep >= until or last_dep <= cursor:
                    break
                cursor = last_dep
        if not pages:
            raise KoleoFetchError("Koleo returned no trips")
        return merge_rows(pages)
