"""Synthetic participants for the city dashboard.

If data/fixtures/participants.json exists (F's data), it is used as is.
Otherwise participants are generated here: deterministic, no personal data.
"""
import json
import random
from pathlib import Path

from app.config import FIXTURES_DIR
from app.models import Participant

PARTICIPANTS_FILE = FIXTURES_DIR / "participants.json"
DEFAULT_COUNT = 420
SEED = 2026

# Share of participants per origin; a station not listed here gets weight 1/N (N = number of origins).
ORIGIN_WEIGHTS = {
    "Warszawa Centralna": 0.35,
    "Katowice": 0.25,
    "Wrocław Główny": 0.20,
    "Poznań Główny": 0.20,
}
PREF_WEIGHTS = {"safest": 0.5, "fastest": 0.3, "cheapest": 0.2}


def generate(origins: list[str], count: int = DEFAULT_COUNT, seed: int = SEED) -> list[Participant]:
    rng = random.Random(seed)
    weights = [ORIGIN_WEIGHTS.get(o, 1 / len(origins)) for o in origins]
    picked_origins = rng.choices(origins, weights=weights, k=count)
    picked_prefs = rng.choices(list(PREF_WEIGHTS), weights=list(PREF_WEIGHTS.values()), k=count)
    return [
        Participant(id=f"u_{i:04d}", origin=o, pref=p)
        for i, (o, p) in enumerate(zip(picked_origins, picked_prefs), start=1)
    ]


def load_participants(origins: list[str], path: Path = PARTICIPANTS_FILE) -> list[Participant]:
    if path.exists():
        return [Participant.model_validate(raw) for raw in json.loads(path.read_text(encoding="utf-8"))]
    return generate(origins)
