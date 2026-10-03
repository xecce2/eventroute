from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Protocol

from app.models import DataSource, TrainOption

if TYPE_CHECKING:
    from app.providers.validator import ValidationResult


class TrainProvider(Protocol):
    """A source of options that always answers (fixtures)."""

    def search(self, origin: str, destination: str, day: date) -> list[TrainOption]:
        """Options from `origin` to `destination` for the event on `day`, including the evening before."""
        ...

    def origins(self, destination: str) -> list[str]:
        """Stations this provider can search from to `destination`, sorted by name."""
        ...


class LiveProvider(Protocol):
    """A live source (F: Playwright + Gemini on Koleo). May be slow and may fail.

    `fetch` returns the Validator's result for everything it read. It raises on a failed fetch
    (network, captcha, Gemini error); the exception text becomes `fallback_reason`.
    """

    def fetch(self, origin: str, destination: str, day: date) -> "ValidationResult": ...


@dataclass
class SearchResult:
    options: list[TrainOption]
    data_source: DataSource
    fallback_reason: str | None = None  # set when a live search was expected but fixtures were used


class SearchProvider(Protocol):
    """What the planner sees (CLAUDE.md, section 3): options plus where they came from."""

    def search(self, origin: str, destination: str, day: date) -> SearchResult: ...

    def origins(self, destination: str) -> list[str]: ...
