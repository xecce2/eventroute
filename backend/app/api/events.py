from fastapi import APIRouter

from app import services
from app.models import Event

router = APIRouter()


@router.get("/events/{event_id}", response_model=Event)
def get_event(event_id: str) -> Event:
    return services.get_event(event_id)
