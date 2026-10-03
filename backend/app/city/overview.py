"""City / organizer view: participants -> their plans -> arrival wave, node load, recommendations."""
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from app.config import FIXTURES_DIR
from app.models import (
    ArrivalSlot, CityNode, CityOverview, Event, Load, OriginCount, Participant, Plan, PlanRequest,
    Recommendation,
)
from app.planner.planner import Planner

NODES_FILE = FIXTURES_DIR / "city_nodes.json"
SLOT_MIN = 15
# Peak arrivals per slot as a share of node capacity per slot.
LOAD_MEDIUM = 0.6
LOAD_HIGH = 1.0
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def slot_of(t: datetime) -> datetime:
    return t.replace(minute=t.minute - t.minute % SLOT_MIN, second=0, microsecond=0)


def load_of(peak: int, capacity: int) -> Load:
    ratio = peak / capacity
    if ratio >= LOAD_HIGH:
        return "high"
    if ratio >= LOAD_MEDIUM:
        return "medium"
    return "low"


def choose_plan(plans: list[Plan], pref: str) -> Plan | None:
    """The participant takes the plan with their preferred label, else the safest one."""
    for label in (pref, "safest"):
        for plan in plans:
            if label in plan.labels:
                return plan
    return plans[0] if plans else None


def _fill(counts: Counter) -> list[ArrivalSlot]:
    """Every slot from the first to the last arrival, zeros included, so the chart has no gaps."""
    if not counts:
        return []
    out = []
    t, last = min(counts), max(counts)
    while t <= last:
        out.append(ArrivalSlot(slot=t, count=counts[t]))
        t += timedelta(minutes=SLOT_MIN)
    return out


def _peak(counts: Counter) -> tuple[datetime | None, int]:
    if not counts:
        return None, 0
    slot = max(counts, key=lambda s: (counts[s], -s.timestamp()))  # earliest of equal peaks
    return slot, counts[slot]


def build_overview(
    event: Event, participants: list[Participant], planner: Planner, nodes_file: Path = NODES_FILE
) -> CityOverview:
    """Participants with an overnight plan or with no plan at all are not in the arrival wave:
    when someone who slept in Kraków reaches the venue is unknown.
    """
    plans_by_origin = {
        origin: planner.plan(event, PlanRequest(origin=origin, event_id=event.id))
        for origin in sorted({p.origin for p in participants})
    }
    venue_counts: Counter = Counter()
    station_counts: dict[str, Counter] = {}
    for participant in participants:
        plan = choose_plan(plans_by_origin[participant.origin], participant.pref)
        if plan is None or plan.overnight_stay:
            continue
        venue_counts[slot_of(plan.arrival_at_venue)] += 1
        station_counts.setdefault(plan.train.to, Counter())[slot_of(plan.train.expected_arr)] += 1

    nodes: list[CityNode] = []
    recommendations: list[Recommendation] = []
    for cfg in json.loads(nodes_file.read_text(encoding="utf-8")):
        capacity = cfg["capacity_per_slot"]
        if cfg["kind"] == "venue":
            name, lat, lon, counts = event.venue, event.lat, event.lon, venue_counts
        else:
            name, lat, lon = cfg["name"], cfg["lat"], cfg["lon"]
            counts = station_counts.get(name, Counter())
        peak_slot, peak_count = _peak(counts)
        load = load_of(peak_count, capacity)
        nodes.append(CityNode(
            name=name, lat=lat, lon=lon, peak_count=peak_count, peak_slot=peak_slot, load=load,
        ))
        if load != "low":
            recommendations.append(_recommend(cfg["kind"], name, event, peak_slot, peak_count, capacity, load))

    recommendations.sort(key=lambda r: SEVERITY_ORDER[r.severity])
    origins = Counter(p.origin for p in participants)
    return CityOverview(
        event_id=event.id,
        participants_total=len(participants),
        arrivals_by_slot=_fill(venue_counts),
        nodes=nodes,
        origins=[OriginCount(station=s, count=c) for s, c in origins.most_common()],
        recommendations=recommendations,
    )


def _recommend(
    kind: str, name: str, event: Event, peak_slot: datetime, peak_count: int, capacity: int, load: Load
) -> Recommendation:
    slot_end = peak_slot + timedelta(minutes=SLOT_MIN)
    if kind == "venue":
        return Recommendation(
            type="stagger_checkin",
            severity=load,
            text=(
                f"Peak of {peak_count} arrivals at the entrance at {peak_slot:%H:%M}–{slot_end:%H:%M}, "
                f"while check-in handles about {capacity} per {SLOT_MIN} min. "
                f"Open more desks for this slot or split check-in into waves by arrival train."
            ),
        )
    return Recommendation(
        type="add_trams",
        severity=load,
        text=(
            f"{peak_count} participants arrive at {name} at {peak_slot:%H:%M}–{slot_end:%H:%M}. "
            f"Add trams towards {event.venue} from {peak_slot:%H:%M} "
            f"to {peak_slot + timedelta(minutes=2 * SLOT_MIN):%H:%M}."
        ),
    )
