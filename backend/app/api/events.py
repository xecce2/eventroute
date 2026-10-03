from fastapi import APIRouter

from app import services
from app.models import Event

router = APIRouter()


@router.get("/events/{event_id}", response_model=Event)
def get_event(event_id: str) -> Event:
    return services.get_event(event_id)


@router.get("/events/{event_id}/stations", response_model=list[str])
def get_stations(event_id: str) -> list[str]:
    """Origin stations for the registration form: those we can plan from to this event."""
    event = services.get_event(event_id)
    return services.planner.provider.origins(event.venue_station)
