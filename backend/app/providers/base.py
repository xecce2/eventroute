from datetime import date
from typing import Protocol

from app.models import TrainOption


class TrainProvider(Protocol):
    """The planner only sees this interface, never the concrete source (CLAUDE.md, section 3)."""

    def search(self, origin: str, destination: str, day: date) -> list[TrainOption]:
        """Options from `origin` to `destination` for the event on `day`, including the evening before."""
        ...

    def origins(self, destination: str) -> list[str]:
        """Stations this provider can search from to `destination`, sorted by name."""
        ...
