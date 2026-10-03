import json
from datetime import date
from pathlib import Path

from app.config import FIXTURES_DIR
from app.models import TrainOption


class FixtureProvider:
    """Recorded responses from data/fixtures/trains/*.json. Works offline, always."""

    def __init__(self, trains_dir: Path = FIXTURES_DIR / "trains"):
        self._trains = [
            TrainOption.model_validate(raw)
            for path in sorted(trains_dir.glob("*.json"))
            for raw in json.loads(path.read_text(encoding="utf-8"))
        ]

    def search(self, origin: str, destination: str, day: date) -> list[TrainOption]:
        # `day` is ignored: fixtures are recorded for the event day already.
        origin, destination = origin.casefold(), destination.casefold()
        return [
            t for t in self._trains
            if t.from_.casefold() == origin and t.to.casefold() == destination
        ]

    def origins(self, destination: str) -> list[str]:
        destination = destination.casefold()
        return sorted({t.from_ for t in self._trains if t.to.casefold() == destination})
