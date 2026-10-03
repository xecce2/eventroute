from fastapi import APIRouter, HTTPException

from app import services
from app.city.overview import build_overview
from app.city.participants import load_participants
from app.models import CityOverview

router = APIRouter()

# Fixture data never changes while the server runs, so each overview is built once.
_cache: dict[str, CityOverview] = {}


@router.get("/city/overview", response_model=CityOverview)
def city_overview(event_id: str | None = None) -> CityOverview:
    """`event_id` may be omitted while there is only one event (the demo)."""
    if event_id is None:
        if len(services.events) != 1:
            raise HTTPException(400, "event_id is required when there are several events")
        event_id = next(iter(services.events))
    event = services.get_event(event_id)
    if event_id not in _cache:
        participants = load_participants(services.planner.provider.origins(event.venue_station))
        _cache[event_id] = build_overview(event, participants, services.planner)
    return _cache[event_id]
