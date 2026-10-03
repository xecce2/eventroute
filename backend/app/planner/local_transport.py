"""Local part of the trip: from the venue's railway station to the venue entrance.

Fixture-based for now (data/fixtures/local_routes.json); can be replaced by Kraków GTFS later.
"""
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from app.config import FIXTURES_DIR
from app.models import LocalLeg


@dataclass(frozen=True)
class LegTemplate:
    mode: str
    from_: str
    to: str
    duration_min: int
    std_min: int
    line: str | None


class LocalTransport:
    def __init__(self, path: Path = FIXTURES_DIR / "local_routes.json"):
        self._routes: dict[tuple[str, str], list[LegTemplate]] = {}
        for route in json.loads(path.read_text(encoding="utf-8")):
            self._routes[(route["station"], route["venue"])] = [
                LegTemplate(
                    mode=leg["mode"],
                    from_=leg["from"],
                    to=leg["to"],
                    duration_min=leg["duration_min"],
                    std_min=leg["std_min"],
                    line=leg["line"],
                )
                for leg in route["legs"]
            ]

    def route(self, station: str, venue: str) -> list[LegTemplate]:
        try:
            return self._routes[(station, venue)]
        except KeyError:
            raise ValueError(f"no local route from {station!r} to {venue!r}") from None

    @staticmethod
    def mean_min(legs: list[LegTemplate]) -> float:
        return sum(leg.duration_min for leg in legs)

    @staticmethod
    def std_min(legs: list[LegTemplate]) -> float:
        return math.sqrt(sum(leg.std_min**2 for leg in legs))

    @staticmethod
    def schedule(legs: list[LegTemplate], start: datetime) -> list[LocalLeg]:
        """Expected (no-delay) timetable of the legs, starting at `start`."""
        out = []
        t = start
        for leg in legs:
            arr = t + timedelta(minutes=leg.duration_min)
            out.append(LocalLeg(
                mode=leg.mode, from_=leg.from_, to=leg.to, dep=t, arr=arr,
                duration_min=leg.duration_min, std_min=leg.std_min, line=leg.line,
            ))
            t = arr
        return out
