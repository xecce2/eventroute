from fastapi import APIRouter

from app import config, services
from app.models import ProviderStatus

router = APIRouter()


@router.get("/providers/status", response_model=ProviderStatus)
def providers_status() -> ProviderStatus:
    """Counters since server start. Before the pitch: say only what these numbers show."""
    provider = services.planner.provider
    stats = provider.stats
    return ProviderStatus(
        provider=config.TRAIN_PROVIDER,
        live_available=provider.live is not None,
        requests_total=stats.requests_total,
        live_ok=stats.live_ok,
        live_partial=stats.live_partial,
        fallback=stats.fallback,
        last_fallback_reason=stats.last_fallback_reason,
        last_rejection_reason=stats.last_rejection_reason,
    )
