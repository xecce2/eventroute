"""Live provider -> one retry -> recorded fixtures, with an honest reason for every fallback."""
import logging
import threading
from dataclasses import dataclass
from datetime import date

from app import config
from app.providers.base import LiveProvider, SearchResult, TrainProvider
from app.timeouts import CallTimeout, call_with_timeout

log = logging.getLogger(__name__)

MAX_REASON_LEN = 300


@dataclass
class ProviderStats:
    requests_total: int = 0
    live_ok: int = 0
    live_partial: int = 0  # live searches that succeeded with some options rejected
    fallback: int = 0
    last_fallback_reason: str | None = None
    last_rejection_reason: str | None = None


def _safe_reason(text: str) -> str:
    """Error text goes to the API and the UI: never leak the API key, keep it short and on one line
    (an exception may quote a piece of somebody else's page)."""
    if config.GEMINI_API_KEY:
        text = text.replace(config.GEMINI_API_KEY, "***")
    return " ".join(text.split())[:MAX_REASON_LEN]


class ChainProvider:
    def __init__(
        self,
        fixtures: TrainProvider,
        live: LiveProvider | None = None,
        unavailable_reason: str | None = None,
        retries: int = 1,
        timeout_sec: float | None = None,
    ):
        """`live=None` with `unavailable_reason` means a live source was configured but cannot run:
        every search then falls back with that reason, so the demo never pretends to be live.
        `timeout_sec` limits one live attempt (default: LIVE_TIMEOUT_SEC).
        """
        self.fixtures = fixtures
        self.live = live
        self.unavailable_reason = unavailable_reason
        self.retries = retries
        self.timeout_sec = config.LIVE_TIMEOUT_SEC if timeout_sec is None else timeout_sec
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
                result = call_with_timeout(
                    lambda: self.live.fetch(origin, destination, day), self.timeout_sec
                )
            except CallTimeout as e:
                # The hung attempt is still running; a retry would only start a second one.
                reason = f"live search failed: {e}"
                log.warning("live search attempt %d timed out", attempt + 1)
                break
            except Exception as e:  # any failure of the live source -> retry, then fixtures
                reason = f"live search failed: {type(e).__name__}: {e}"
                log.warning("live search attempt %d failed: %s", attempt + 1, type(e).__name__)
                continue
            if result.accepted:
                # Partly rejected is still live data (so no fallback_reason), but it is counted
                # and the reason is kept for /api/providers/status.
                rejection = result.fallback_reason()
                with self._lock:
                    self.stats.live_ok += 1
                    if rejection:
                        self.stats.live_partial += 1
                        self.stats.last_rejection_reason = _safe_reason(rejection)
                if rejection:
                    log.warning("live search ok, but %s", rejection)
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
