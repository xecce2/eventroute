"""Local part of the trip: from the venue's railway station to the venue entrance.

Routes come from data/fixtures/local_routes.json. A leg with a `timetable` (real departures
taken from the Kraków GTFS feed) is boarded at the next departure after you reach the stop;
a leg without one takes its fixed `duration_min`.
"""
import json
import math
from bisect import bisect_left
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.config import FIXTURES_DIR
from app.models import LatLon, LocalLeg

LOOKAHEAD_DAYS = 2  # after the last departure of the day, the next one is tomorrow's first


@dataclass(frozen=True)
class Timetable:
    tz: ZoneInfo
    ride_min: int
    ride_std_min: int
    # Day type ("weekday" | "saturday" | "sunday") -> (minutes after local midnight, line), sorted.
    departures: dict[str, list[tuple[int, str]]]
    holidays: frozenset[date]  # dates that run the Sunday timetable

    @classmethod
    def from_json(cls, raw: dict) -> "Timetable":
        def minutes(hhmm: str) -> int:
            # GTFS hours may go past 24 for trips after midnight.
            hours, mins = hhmm.split(":")
            return int(hours) * 60 + int(mins)

        return cls(
            tz=ZoneInfo(raw["timezone"]),
            ride_min=raw["ride_min"],
            ride_std_min=raw["ride_std_min"],
            departures={
                day_type: sorted((minutes(t), line) for line, times in by_line.items() for t in times)
                for day_type, by_line in raw["departures"].items()
            },
            holidays=frozenset(date.fromisoformat(d) for d in raw.get("holidays", [])),
        )

    def day_type(self, day: date) -> str:
        if day in self.holidays or day.weekday() == 6:
            return "sunday"
        return "saturday" if day.weekday() == 5 else "weekday"

    def upcoming(self, start: datetime) -> list[tuple[datetime, str]]:
        """Departures at or after `start`, in order, for the next LOOKAHEAD_DAYS days."""
        first_day = start.astimezone(self.tz).date()
        out = []
        for offset in range(LOOKAHEAD_DAYS):
            day = first_day + timedelta(days=offset)
            midnight = datetime.combine(day, time(), tzinfo=self.tz)
            for minute, line in self.departures.get(self.day_type(day), []):
                dep = midnight + timedelta(minutes=minute)
                if dep >= start:
                    out.append((dep, line))
        return out

    def next_departure(self, start: datetime) -> tuple[datetime, str] | None:
        upcoming = self.upcoming(start)
        return upcoming[0] if upcoming else None

    def offsets_min(self, start: datetime) -> list[float]:
        """Upcoming departures as minutes after `start`, for fast lookups in the simulation."""
        return [(dep - start).total_seconds() / 60 for dep, _ in self.upcoming(start)]


@dataclass(frozen=True)
class LegTemplate:
    mode: str
    from_: str
    to: str
    duration_min: int  # with a timetable: the fallback (ride plus average wait)
    std_min: int
    line: str | None
    path: list[LatLon] | None = None
    timetable: Timetable | None = None

    @property
    def ride_min(self) -> int:
        """Time in motion, without waiting for a departure."""
        return self.timetable.ride_min if self.timetable else self.duration_min

    @property
    def ride_std_min(self) -> int:
        return self.timetable.ride_std_min if self.timetable else self.std_min


def board(deps: list[float], t: float) -> float | None:
    """First departure in `deps` (sorted minutes) not earlier than `t`."""
    i = bisect_left(deps, t)
    return deps[i] if i < len(deps) else None


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
                    path=leg.get("path"),
                    timetable=Timetable.from_json(leg["timetable"]) if leg.get("timetable") else None,
                )
                for leg in route["legs"]
            ]

    def route(self, station: str, venue: str) -> list[LegTemplate]:
        try:
            return self._routes[(station, venue)]
        except KeyError:
            raise ValueError(f"no local route from {station!r} to {venue!r}") from None

    @staticmethod
    def min_min(legs: list[LegTemplate]) -> float:
        """Shortest possible time: every departure leaves the moment you reach the stop."""
        return sum(leg.ride_min for leg in legs)

    @staticmethod
    def std_min(legs: list[LegTemplate]) -> float:
        return math.sqrt(sum(leg.ride_std_min**2 for leg in legs))

    @staticmethod
    def schedule(legs: list[LegTemplate], start: datetime) -> list[LocalLeg]:
        """Expected (no-delay) timetable of the legs, starting at `start`.

        A timetabled leg departs at its next real departure, so there may be a wait
        between the previous leg's `arr` and its `dep`.
        """
        out = []
        t = start
        for leg in legs:
            nxt = leg.timetable.next_departure(t) if leg.timetable else None
            if nxt:
                dep, line = nxt[0].astimezone(start.tzinfo), nxt[1]
                duration, std = leg.timetable.ride_min, leg.timetable.ride_std_min
            else:
                dep, line, duration, std = t, leg.line, leg.duration_min, leg.std_min
            arr = dep + timedelta(minutes=duration)
            out.append(LocalLeg(
                mode=leg.mode, from_=leg.from_, to=leg.to, dep=dep, arr=arr,
                duration_min=duration, std_min=std, line=line,
                path=leg.path,
            ))
            t = arr
        return out

    @classmethod
    def arrival(cls, legs: list[LegTemplate], start: datetime) -> datetime:
        """Expected arrival at the venue when the local part starts at `start`."""
        timed = cls.schedule(legs, start)
        return timed[-1].arr if timed else start
