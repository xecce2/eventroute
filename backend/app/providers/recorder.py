"""Records Koleo into fixture files (F).

Fixtures are what the demo falls back to when the live search fails, and what the city screen is
built from, so a chosen demo date needs them as well. One call reads every origin with the live
provider and writes `data/fixtures/trains/<origin>_<destination>_<MMDD>.json`: a list of
`TrainOption` with `source: "fixture"` (recorded data, never live). `FixtureProvider` loads every
`*.json` in that folder, and the planner picks the right date by its own time window.

Recording uses the code parser only (no Gemini): a recording must be exactly what the page shows.
"""
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Protocol

from app.models import TrainOption
from app.providers.validator import ValidationResult, koleo_slug


class Fetcher(Protocol):
    def fetch(self, origin: str, destination: str, day, *, since: datetime, until: datetime) -> ValidationResult: ...


class RecordError(RuntimeError):
    """Nothing was written for this origin."""


@dataclass
class Recorded:
    origin: str
    path: Path
    count: int
    rejected: int = 0


@dataclass
class Recording:
    done: list[Recorded] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)  # origin -> why


def fixture_path(out_dir: Path, origin: str, destination: str, suffix: str) -> Path:
    first = lambda station: koleo_slug(station).split("-")[0]  # noqa: E731  ("Wrocław Główny" -> "wroclaw")
    return out_dir / f"{first(origin)}_{first(destination)}_{suffix}.json"


def _ids_elsewhere(out_dir: Path, target: Path) -> set[str]:
    ids: set[str] = set()
    for other in out_dir.glob("*.json"):
        if other != target:
            ids.update(item["id"] for item in json.loads(other.read_text(encoding="utf-8")))
    return ids


def record_one(
    origin: str, destination: str, since: datetime, until: datetime, out_dir: Path, fetcher: Fetcher, suffix: str
) -> Recorded:
    result = fetcher.fetch(origin, destination, until.date(), since=since, until=until)
    if not result.accepted:
        raise RecordError(result.fallback_reason() or "Koleo returned no trips")
    options = [
        TrainOption.model_validate(option.model_copy(update={"source": "fixture"}).model_dump(by_alias=True))
        for option in sorted(result.accepted, key=lambda o: (o.dep, o.arr, o.category))
    ]
    target = fixture_path(out_dir, origin, destination, suffix)
    clash = _ids_elsewhere(out_dir, target) & {option.id for option in options}
    if clash:
        raise RecordError(
            f"{len(clash)} trip ids already exist in other fixture files (for example {sorted(clash)[0]}): "
            "the dates overlap recorded data, choose another window or remove the old file"
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps([json.loads(option.model_dump_json(by_alias=True)) for option in options], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return Recorded(origin, target, len(options), len(result.rejected))


def record_fixtures(
    origins: list[str],
    destination: str,
    since: datetime,
    until: datetime,
    out_dir: Path,
    fetcher: Fetcher,
    suffix: str | None = None,
    on_progress=lambda message: None,
) -> Recording:
    """Record every origin; one origin failing does not stop the others."""
    suffix = suffix or f"{until:%m%d}"
    recording = Recording()
    for origin in origins:
        on_progress(f"{origin}: reading Koleo from {since:%d.%m %H:%M} to {until:%d.%m %H:%M} ...")
        try:
            done = record_one(origin, destination, since, until, out_dir, fetcher, suffix)
        except Exception as e:  # a failed origin is reported, the rest still run
            recording.failed[origin] = f"{type(e).__name__}: {e}"
            on_progress(f"{origin}: FAILED, {recording.failed[origin]}")
            continue
        recording.done.append(done)
        on_progress(f"{origin}: {done.count} trips -> {done.path.name}" + (f" ({done.rejected} rejected by the validator)" if done.rejected else ""))
    return recording
