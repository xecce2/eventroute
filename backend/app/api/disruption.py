from fastapi import APIRouter, HTTPException

from app import services
from app.models import DisruptionRequest, DisruptionResponse, Plan
from app.notifier import notify

router = APIRouter()


@router.post("/simulate/disruption", response_model=DisruptionResponse)
def simulate_disruption(req: DisruptionRequest) -> DisruptionResponse:
    """The plan's train is reported late: replan and notify the user.

    The delay is assumed to be known at the train's scheduled departure,
    so only options departing from then on are offered as alternatives.
    """
    plan = services.plans.get(req.plan_id)
    if plan is None:
        raise HTTPException(404, f"plan {req.plan_id} not found")
    request_id = services.plan_request[plan.id]
    state = services.requests[request_id]
    event = services.get_event(state.request.event_id)

    state.known_delays[plan.train.id] = req.train_delay_min
    delayed = plan.train.model_copy(update={"known_delay_min": req.train_delay_min})
    affected = services.planner.plan_for_train(event, state.request, delayed, plan.labels)
    plans = services.planner.plan(
        event, state.request, known_delays=state.known_delays, not_before=plan.train.dep
    )
    services.save_plans(request_id, [affected, *plans])

    message = disruption_message(affected, plans, req.train_delay_min)
    return DisruptionResponse(
        affected_plan=affected, plans=plans, notified=notify(message), message=message
    )


def disruption_message(affected: Plan, plans: list[Plan], delay_min: int) -> str:
    t = affected.train
    text = (
        f"{t.train} {t.dep:%H:%M} опаздывает на {delay_min} мин. "
        f"Будешь на месте около {affected.arrival_at_venue:%H:%M}, "
        f"шанс успеть {round(affected.p_on_time * 100)}%."
    )
    better = [p for p in plans if p.train.id != t.id and p.p_on_time > affected.p_on_time]
    if better:
        alt = max(better, key=lambda p: p.p_on_time)
        text += (
            f" Альтернатива: {alt.train.train} {alt.train.dep:%H:%M} → {alt.train.arr:%H:%M}, "
            f"шанс {round(alt.p_on_time * 100)}%."
        )
    return text
