"""Shared singletons and in-memory state. A restart wipes the state, which is fine for the demo."""
import json
import logging
from dataclasses import dataclass, field

from fastapi import HTTPException

from app import config
from app.config import FIXTURES_DIR, MC_RUNS
from app.models import Event, Plan, PlanRequest
from app.planner.local_transport import LocalTransport
from app.planner.planner import Planner
from app.providers.chain import ChainProvider
from app.providers.fixture import FixtureProvider

log = logging.getLogger(__name__)

events: dict[str, Event] = {
    e.id: e
    for e in (
        Event.model_validate(raw)
        for raw in json.loads((FIXTURES_DIR / "events.json").read_text(encoding="utf-8"))
    )
}


def make_provider(fixtures: FixtureProvider) -> ChainProvider:
    """TRAIN_PROVIDER=koleo plugs in F's live provider (app/providers/koleo_agent.py).
    If it cannot run, every search falls back to fixtures with the reason, never silently.
    """
    if config.TRAIN_PROVIDER == "fixture":
        return ChainProvider(fixtures)
    if not config.GEMINI_API_KEY:
        return ChainProvider(fixtures, unavailable_reason="GEMINI_API_KEY is not set")
    try:
        from app.providers.koleo_agent import KoleoAgentProvider
    except ImportError as e:
        if isinstance(e, ModuleNotFoundError) and e.name == "app.providers.koleo_agent":
            reason = "live Koleo provider is not implemented yet"
        else:  # the module exists but cannot load, e.g. a missing package
            reason = f"live Koleo provider failed to load: {e}"
        log.warning("live provider unavailable: %s", reason)
        return ChainProvider(fixtures, unavailable_reason=reason)
    return ChainProvider(fixtures, live=KoleoAgentProvider(api_key=config.GEMINI_API_KEY))


fixtures = FixtureProvider()
local_transport = LocalTransport()
planner = Planner(make_provider(fixtures), local_transport, runs=MC_RUNS)
# The city dashboard is a forecast over synthetic participants: always recorded data,
# so it neither waits for live searches nor counts in the provider status.
city_planner = Planner(ChainProvider(fixtures), local_transport, runs=MC_RUNS)


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
