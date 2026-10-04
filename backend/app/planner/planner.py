"""Backward planner: from the time you must be at the venue back to the train (CLAUDE.md, section 5)."""
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models import DataSource, Event, Label, Plan, PlanRequest, TrainOption
from app.planner.local_transport import LegTemplate, LocalTransport
from app.planner.reliability import p_on_time
from app.providers.base import SearchProvider, SearchResult

TRANSFER_MIN = 5            # platform -> first local leg
SEARCH_WINDOW_HOURS = 12    # search window opens this long before the time to be at the venue
EARLIEST_ARRIVAL_HOUR = 6   # arriving before 06:00 on the arrival day still means a night to spend
VIABLE_P = 0.5              # fastest/cheapest are picked only among plans at least this likely
SAFE_ENOUGH_P = 0.8         # below this on the arrival day, an overnight option may become safest
SAFEST_TIE_P = 0.02         # near-equal p_on_time -> prefer the later departure

# The overnight boundary and the day sent to the provider are local to the event,
# whatever offset the request used for `arrive_by` (e.g. "...Z").
LOCAL_TZ = ZoneInfo("Europe/Warsaw")

LABEL_TEXT = {"safest": "most reliable", "fastest": "fastest", "cheapest": "cheapest"}

StatusFn = Callable[[str, str], None]


@dataclass
class Candidate:
    train: TrainOption
    p: float
    overnight: bool

    @property
    def duration(self) -> timedelta:
        return self.train.expected_arr - self.train.dep


@dataclass
class PlanResult:
    plans: list[Plan]    # the cards: labeled plans, in label order
    options: list[Plan]  # every suitable option, cheapest first; same objects as in `plans`
    # Passed through from the provider; the planner does not decide anything on them.
    data_source: DataSource = "recorded"
    fallback_reason: str | None = None
    search: SearchResult | None = None  # what the provider returned, to replan without a new search


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def venue_target_for(event: Event, req: PlanRequest) -> datetime:
    return (req.arrive_by or event.venue_target).astimezone(LOCAL_TZ)


def price_order(plan: Plan) -> tuple:
    """Cheapest first, unknown price last, then by departure."""
    return (plan.price_pln is None, plan.price_pln or 0.0, plan.train.dep)


class Planner:
    def __init__(self, provider: SearchProvider, local: LocalTransport, runs: int):
        self.provider = provider
        self.local = local
        self.runs = runs

    def plan(
        self,
        event: Event,
        req: PlanRequest,
        known_delays: dict[str, int] | None = None,
        not_before: datetime | None = None,
        on_status: StatusFn | None = None,
        found: SearchResult | None = None,
    ) -> PlanResult:
        """Up to 3 cards (one per label, merged when one option wins several labels)
        plus the full list of suitable options sorted by price.

        `found` is an earlier search result to plan from; without it the provider is asked.
        """
        status = on_status or (lambda step, msg: None)
        known_delays = known_delays or {}
        venue_target = venue_target_for(event, req)
        legs = self.local.route(event.venue_station, event.venue)
        # A margin for the uncertainty of the local part: expected arrival must leave this much.
        margin = timedelta(minutes=self.local.std_min(legs))
        # No train arriving later can make it, even if every tram leaves the moment you reach the stop.
        station_deadline = venue_target - margin - timedelta(minutes=TRANSFER_MIN + self.local.min_min(legs))
        # In UTC, so the window is 12 real hours even across a clock change.
        window_start = (
            venue_target.astimezone(timezone.utc) - timedelta(hours=SEARCH_WINDOW_HOURS)
        ).astimezone(LOCAL_TZ)

        status("search", "Searching for trains…")
        found_trains = found or self.provider.search(
            req.origin,
            event.venue_station,
            venue_target.date(),
            # Nothing that has already left is needed, and nothing arriving after the deadline.
            since=max(window_start, not_before) if not_before else window_start,
            until=station_deadline,
        )
        if found_trains.fallback_reason:
            status("fallback", f"Live search failed, using recorded data: {found_trains.fallback_reason}")
        trains = [
            t.model_copy(update={"known_delay_min": known_delays.get(t.id, t.known_delay_min)})
            for t in found_trains.options
        ]
        trains = [
            t for t in trains
            if t.dep >= window_start
            and t.expected_arr <= station_deadline
            # With the real tram departures, including the wait at the stop.
            and self._venue_arrival(t, legs) + margin <= venue_target
            # With a budget, an unknown price cannot be promised to fit, so it is left out.
            and (req.budget_pln is None or (t.price_pln is not None and t.price_pln <= req.budget_pln))
            and (req.mode_pref is None or t.mode == req.mode_pref)
        ]
        # Options that would fit but have already left (`not_before` is "now").
        departed = 0
        if not_before is not None:
            departed = sum(t.dep < not_before for t in trains)
            trains = [t for t in trains if t.dep >= not_before]
        found = f"Found {len(trains)} suitable options"
        status("found", found + (f" ({departed} already departed)" if departed else ""))

        status("local", "Checking transfers and local transport")
        status("reliability", f"Calculating the chance of arriving on time ({self.runs} simulations)")
        candidates = [self._score(t, legs, venue_target) for t in trains]
        labels_by_id = {c.train.id: labels for c, labels in select(candidates)}
        built = {
            c.train.id: self._build(c, labels_by_id.get(c.train.id, []), legs, venue_target)
            for c in candidates
        }
        status("done", "Done")
        return PlanResult(
            plans=[built[train_id] for train_id in labels_by_id],
            options=sorted(built.values(), key=price_order),
            data_source=found_trains.data_source,
            fallback_reason=found_trains.fallback_reason,
            search=found_trains,
        )

    def plan_for_train(
        self, event: Event, req: PlanRequest, train: TrainOption, labels: list[Label]
    ) -> Plan:
        """Plan for one given train, even if it no longer makes the cut (e.g. after a delay)."""
        venue_target = venue_target_for(event, req)
        legs = self.local.route(event.venue_station, event.venue)
        return self._build(self._score(train, legs, venue_target), labels, legs, venue_target)

    def _venue_arrival(self, train: TrainOption, legs: list[LegTemplate]) -> datetime:
        return self.local.arrival(legs, train.expected_arr + timedelta(minutes=TRANSFER_MIN))

    def _score(self, train: TrainOption, legs: list[LegTemplate], venue_target: datetime) -> Candidate:
        earliest_ok = venue_target.replace(hour=EARLIEST_ARRIVAL_HOUR, minute=0, second=0, microsecond=0)
        return Candidate(
            train=train,
            p=p_on_time(train, legs, TRANSFER_MIN, venue_target, self.runs),
            overnight=train.expected_arr < earliest_ok,
        )

    def _build(
        self, c: Candidate, labels: list[Label], legs: list[LegTemplate], venue_target: datetime
    ) -> Plan:
        local_legs = self.local.schedule(legs, c.train.expected_arr + timedelta(minutes=TRANSFER_MIN))
        arrival = local_legs[-1].arr if local_legs else c.train.expected_arr
        buffer_min = round((venue_target - arrival).total_seconds() / 60)
        return Plan(
            id=new_id("pl"),
            labels=labels,
            train=c.train,
            local_legs=local_legs,
            venue_target=venue_target,
            arrival_at_venue=arrival,
            buffer_min=buffer_min,
            p_on_time=round(c.p, 3),
            price_pln=c.train.price_pln,
            overnight_stay=c.overnight,
            explanation=explain(c, labels, buffer_min),
            buy_url=c.train.url,
        )


def _safest(candidates: list[Candidate]) -> Candidate | None:
    if not candidates:
        return None
    best_p = max(c.p for c in candidates)
    return max((c for c in candidates if c.p >= best_p - SAFEST_TIE_P), key=lambda c: c.train.dep)


def select(candidates: list[Candidate]) -> list[tuple[Candidate, list[Label]]]:
    """Pick safest/fastest/cheapest; one option winning several labels becomes one plan.

    Overnight options never win fastest/cheapest: their time and price ignore the night stay.
    They can be safest only if nothing on the arrival day is safe enough.
    """
    same_day = [c for c in candidates if not c.overnight]
    viable = [c for c in same_day if c.p >= VIABLE_P] or same_day
    picks: dict[str, tuple[Candidate, list[Label]]] = {}

    def add(c: Candidate, label: Label) -> None:
        picks.setdefault(c.train.id, (c, []))[1].append(label)

    safest = _safest(same_day)
    if safest is None or safest.p < SAFE_ENOUGH_P:
        overnight = _safest([c for c in candidates if c.overnight])
        if overnight is not None and (safest is None or overnight.p > safest.p):
            safest = overnight
    if safest is not None:
        add(safest, "safest")
    if viable:
        add(min(viable, key=lambda c: c.duration), "fastest")
        priced = [c for c in viable if c.train.price_pln is not None]
        if priced:
            # Equal price -> the later departure: same money, more sleep.
            add(min(priced, key=lambda c: (c.train.price_pln, -c.train.dep.timestamp())), "cheapest")
    return list(picks.values())


def explain(c: Candidate, labels: list[Label], buffer_min: int) -> str:
    """Template text; to be replaced by an LLM that rephrases these same numbers."""
    parts = []
    if labels:
        parts.append(", ".join(LABEL_TEXT[label] for label in labels).capitalize() + ".")
    if buffer_min >= 0:
        parts.append(f"{buffer_min} min to spare, {round(c.p * 100)}% chance of arriving on time.")
    else:
        parts.append(f"{-buffer_min} min late, {round(c.p * 100)}% chance of arriving on time.")
    if c.overnight:
        parts.append("Arrives the day before or overnight, so you will need a place to stay.")
    if c.train.mode == "bus":
        parts.append("This is a bus, not a train.")
    return " ".join(parts)
