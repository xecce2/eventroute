import asyncio
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app import config, services
from app.models import PlanRequest, PlanResponse
from app.planner.planner import new_id

router = APIRouter()


@router.post("/plan", response_model=PlanResponse)
def create_plan(req: PlanRequest) -> PlanResponse:
    event = services.get_event(req.event_id)
    request_id = new_id("rq")
    statuses: list[tuple[str, str]] = []
    services.requests[request_id] = services.RequestState(request=req, statuses=statuses)
    result = services.planner.plan(event, req, on_status=lambda step, msg: statuses.append((step, msg)))
    # Options include the cards, so a delay can be simulated on any listed option.
    services.save_plans(request_id, result.options)
    return PlanResponse(
        request_id=request_id,
        plans=result.plans,
        options=result.options,
        status="ok" if result.plans else "no_options",
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/plan/{request_id}/stream")
async def stream_status(request_id: str) -> StreamingResponse:
    """Replays the search statuses of a request.

    Planning on fixtures is instant, so this is a replay. With a slow live provider,
    move planning into a background task and stream statuses as they come.
    """
    state = services.requests.get(request_id)
    if state is None:
        raise HTTPException(404, f"request {request_id} not found")

    async def events():
        for step, message in state.statuses:
            yield _sse("status", {"step": step, "message": message})
            await asyncio.sleep(config.SSE_STEP_SEC)
        yield _sse("done", {"request_id": request_id})

    return StreamingResponse(events(), media_type="text/event-stream")
