"""Shared singletons and in-memory state. A restart wipes the state, which is fine for the demo."""
import json
from dataclasses import dataclass, field

from fastapi import HTTPException

from app.config import FIXTURES_DIR, MC_RUNS
from app.models import Event, Plan, PlanRequest
from app.planner.local_transport import LocalTransport
from app.planner.planner import Planner
from app.providers.fixture import FixtureProvider

events: dict[str, Event] = {
    e.id: e
    for e in (
        Event.model_validate(raw)
        for raw in json.loads((FIXTURES_DIR / "events.json").read_text(encoding="utf-8"))
    )
}
planner = Planner(FixtureProvider(), LocalTransport(), runs=MC_RUNS)


@dataclass
class RequestState:
    request: PlanRequest
    statuses: list[tuple[str, str]]
    plan_ids: list[str] = field(default_factory=list)
    # train id -> known delay in minutes (set by the disruption simulation)
    known_delays: dict[str, int] = field(default_factory=dict)


requests: dict[str, RequestState] = {}
plans: dict[str, Plan] = {}
plan_request: dict[str, str] = {}


def save_plans(request_id: str, new_plans: list[Plan]) -> None:
    for p in new_plans:
        plans[p.id] = p
        plan_request[p.id] = request_id
        requests[request_id].plan_ids.append(p.id)


def get_event(event_id: str) -> Event:
    if event_id not in events:
        raise HTTPException(404, f"event {event_id} not found")
    return events[event_id]
