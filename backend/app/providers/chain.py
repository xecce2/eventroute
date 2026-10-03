"""Live provider -> one retry -> recorded fixtures, with an honest reason for every fallback."""
import logging
import threading
from dataclasses import dataclass
from datetime import date

from app import config
from app.providers.base import LiveProvider, SearchResult, TrainProvider

log = logging.getLogger(__name__)

MAX_REASON_LEN = 300


@dataclass
class ProviderStats:
    requests_total: int = 0
    live_ok: int = 0
    fallback: int = 0
    last_fallback_reason: str | None = None


def _safe_reason(text: str) -> str:
    """Error text goes to the API and the UI: never leak the API key, keep it short."""
    if config.GEMINI_API_KEY:
        text = text.replace(config.GEMINI_API_KEY, "***")
    return text[:MAX_REASON_LEN]


class ChainProvider:
    def __init__(
        self,
        fixtures: TrainProvider,
        live: LiveProvider | None = None,
        unavailable_reason: str | None = None,
        retries: int = 1,
    ):
        """`live=None` with `unavailable_reason` means a live source was configured but cannot run:
        every search then falls back with that reason, so the demo never pretends to be live.
        """
        self.fixtures = fixtures
        self.live = live
        self.unavailable_reason = unavailable_reason
        self.retries = retries
        self.stats = ProviderStats()
        self._lock = threading.Lock()

    def origins(self, destination: str) -> list[str]:
        return self.fixtures.origins(destination)

    def search(self, origin: str, destination: str, day: date) -> SearchResult:
        with self._lock:
            self.stats.requests_total += 1
        if self.live is None:
            if self.unavailable_reason is None:
                return SearchResult(self.fixtures.search(origin, destination, day), "recorded")
            return self._fall_back(origin, destination, day, self.unavailable_reason)

        reason = "live search returned no options"
        for attempt in range(1 + self.retries):
            try:
                result = self.live.fetch(origin, destination, day)
            except Exception as e:  # any failure of the live source -> retry, then fixtures
                reason = f"live search failed: {type(e).__name__}: {e}"
                log.warning("live search attempt %d failed: %s", attempt + 1, type(e).__name__)
                continue
            if result.accepted:
                with self._lock:
                    self.stats.live_ok += 1
                return SearchResult(result.accepted, "live")
            reason = result.fallback_reason() or "live search returned no options"
        return self._fall_back(origin, destination, day, reason)

    def _fall_back(self, origin: str, destination: str, day: date, reason: str) -> SearchResult:
        reason = _safe_reason(reason)
        with self._lock:
            self.stats.fallback += 1
            self.stats.last_fallback_reason = reason
        log.warning("using recorded data: %s", reason)
        return SearchResult(self.fixtures.search(origin, destination, day), "recorded", reason)
