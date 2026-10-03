"""Current time for planning. DEMO_NOW freezes it, so the demo works on any day."""
from datetime import datetime, timezone

from app import config


def now() -> datetime:
    return config.DEMO_NOW or datetime.now(timezone.utc)
