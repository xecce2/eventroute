"""Monte Carlo estimate of the chance to reach the venue on time."""
import math
import random
import zlib
from datetime import datetime

from app.models import DelayModel, TrainOption
from app.planner.local_transport import LegTemplate

# PKP counts a train as on time if it is at most 5 minutes late.
ON_TIME_MAX_MIN = 5.0


def _tail_scale(model: DelayModel) -> float:
    """Scale of the exponential tail of delays beyond ON_TIME_MAX_MIN.

    Fitted so that P(delay > p95_delay_min) = 5%; falls back to mean_delay_min
    when p95 cannot be fitted (e.g. p_on_time >= 0.95).
    """
    p_late = 1 - model.p_on_time
    if p_late > 0.05 and model.p95_delay_min > ON_TIME_MAX_MIN:
        return (model.p95_delay_min - ON_TIME_MAX_MIN) / math.log(p_late / 0.05)
    mean_late = (model.mean_delay_min - model.p_on_time * ON_TIME_MAX_MIN / 2) / max(p_late, 1e-6)
    return max(mean_late - ON_TIME_MAX_MIN, 1.0)


def sample_delay(model: DelayModel, rng: random.Random) -> float:
    if rng.random() < model.p_on_time:
        return rng.uniform(0, ON_TIME_MAX_MIN)
    return ON_TIME_MAX_MIN + rng.expovariate(1 / _tail_scale(model))


def p_on_time(
    train: TrainOption,
    legs: list[LegTemplate],
    transfer_min: float,
    venue_target: datetime,
    runs: int,
) -> float:
    """Share of runs in which train delay + transfer + local legs still fit before venue_target.

    A known delay is already in `expected_arr`; on top of it the usual random delay is sampled.
    Seeded by train id, so the same input always gives the same number (stable demo).
    """
    rng = random.Random(zlib.crc32(train.id.encode()))
    slack_min = (venue_target - train.expected_arr).total_seconds() / 60 - transfer_min
    hits = 0
    for _ in range(runs):
        t = sample_delay(train.delay_model, rng)
        for leg in legs:
            t += max(rng.gauss(leg.duration_min, leg.std_min), leg.duration_min * 0.5)
        if t <= slack_min:
            hits += 1
    return hits / runs
