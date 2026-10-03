import json
from datetime import date
from pathlib import Path

from app.config import FIXTURES_DIR
from app.models import TrainOption
from app.providers.validator import koleo_slug


class FixtureProvider:
    """Recorded responses from data/fixtures/trains/*.json. Works offline, always."""

    def __init__(self, trains_dir: Path = FIXTURES_DIR / "trains"):
        self._trains = [
            TrainOption.model_validate(raw)
            for path in sorted(trains_dir.glob("*.json"))
            for raw in json.loads(path.read_text(encoding="utf-8"))
        ]

    def search(self, origin: str, destination: str, day: date) -> list[TrainOption]:
        # `day` is ignored: every recorded date is returned, the planner keeps what fits its window.
        # Names are compared as the Validator does: case and diacritics do not matter.
        origin, destination = koleo_slug(origin), koleo_slug(destination)
        return [
            t for t in self._trains
            if koleo_slug(t.from_) == origin and koleo_slug(t.to) == destination
        ]

    def origins(self, destination: str) -> list[str]:
        destination = koleo_slug(destination)
        return sorted({t.from_ for t in self._trains if koleo_slug(t.to) == destination})
