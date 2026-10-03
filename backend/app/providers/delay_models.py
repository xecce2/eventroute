"""Delay model per Koleo category (CLAUDE.md, section 4).

Koleo gives no delay statistics, so these numbers are our own estimates, not measurements.
IC, TLK and FLIX match the recorded Wrocław fixture; the rest are estimates of the same kind.
"""
from app.models import DelayModel

# category -> (p_on_time, mean_delay_min, p95_delay_min)
DELAY_BY_CATEGORY: dict[str, tuple[float, int, int]] = {
    "IC": (0.70, 6, 25),
    "TLK": (0.65, 8, 30),
    "FLIX": (0.60, 10, 35),
    "EIP": (0.75, 5, 20),
    "EIC": (0.75, 5, 20),
    "LEO": (0.70, 6, 25),
    "KŚ": (0.80, 3, 12),
    "PR": (0.80, 3, 12),
    "KM": (0.80, 3, 12),
    "REG": (0.80, 3, 12),
    "KD": (0.80, 3, 12),
}

# Each change adds the risk of a missed connection.
CHANGE_P_PENALTY = 0.10
CHANGE_MEAN_MIN = 3
CHANGE_P95_MIN = 5
MIN_P_ON_TIME = 0.30


def split_category(category: str) -> list[str]:
    """`"IC+EIP"` -> `["IC", "EIP"]`; upper-cased, blanks dropped."""
    return [part.strip().upper() for part in category.split("+") if part.strip()]


def delay_model_for(legs: list[str], changes: int) -> DelayModel:
    """Worst leg decides; every change makes it worse. All `legs` must be known categories."""
    models = [DELAY_BY_CATEGORY[leg] for leg in legs]
    return DelayModel(
        p_on_time=round(max(min(m[0] for m in models) - CHANGE_P_PENALTY * changes, MIN_P_ON_TIME), 2),
        mean_delay_min=max(m[1] for m in models) + CHANGE_MEAN_MIN * changes,
        p95_delay_min=max(m[2] for m in models) + CHANGE_P95_MIN * changes,
    )
