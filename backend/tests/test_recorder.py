import json
from datetime import datetime

import pytest

from app.config import FIXTURES_DIR
from app.models import TrainOption
from app.providers.fixture import FixtureProvider
from app.providers.recorder import RecordError, fixture_path, record_fixtures
from app.providers.validator import ValidationResult, koleo_slug

DEST = "Kraków Główny"
SINCE = datetime.fromisoformat("2026-10-10T16:00:00+02:00")
UNTIL = datetime.fromisoformat("2026-10-11T08:30:00+02:00")


def live_options(origin: str, day_shift: int = 7):
    """Recorded Wrocław options moved a week ahead and tagged as if Playwright had just read them."""
    # The original recording only (3-4 Oct): the folder may hold other dates too, e.g. 10-11 Oct.
    first = koleo_slug(origin).split("-")[0]
    options = [
        TrainOption.model_validate(item)
        for item in json.loads((FIXTURES_DIR / "trains" / f"{first}_krakow.json").read_text(encoding="utf-8"))
    ]
    moved = []
    for option in options:
        delta = day_shift * 24 * 3600
        moved.append(option.model_copy(update={
            "id": option.id.replace("1003", "1010").replace("1004", "1011"),
            "source": "playwright",
            "dep": datetime.fromtimestamp(option.dep.timestamp() + delta, option.dep.tzinfo),
            "arr": datetime.fromtimestamp(option.arr.timestamp() + delta, option.arr.tzinfo),
        }))
    return moved


class FakeFetcher:
    def __init__(self, fail=()):
        self.calls, self.fail = [], set(fail)

    def fetch(self, origin, destination, day, *, since, until):
        self.calls.append((origin, destination, day, since, until))
        if origin in self.fail:
            raise TimeoutError("Koleo did not answer")
        return ValidationResult(accepted=live_options(origin))


def test_file_names_follow_the_existing_ones():
    out = FIXTURES_DIR / "trains"
    assert fixture_path(out, "Wrocław Główny", DEST, "1011").name == "wroclaw_krakow_1011.json"
    assert fixture_path(out, "Warszawa Centralna", DEST, "x").name == "warszawa_krakow_x.json"
    assert fixture_path(out, "Katowice", DEST, "x").name == "katowice_krakow_x.json"


def test_options_are_written_as_recorded_fixtures(tmp_path):
    fetcher = FakeFetcher()
    recording = record_fixtures(["Wrocław Główny"], DEST, SINCE, UNTIL, tmp_path, fetcher)
    assert recording.failed == {} and recording.done[0].path.name == "wroclaw_krakow_1011.json"
    written = [TrainOption.model_validate(item) for item in json.loads(recording.done[0].path.read_text(encoding="utf-8"))]
    assert len(written) == recording.done[0].count > 0
    assert {t.source for t in written} == {"fixture"}          # recorded data is never "live"
    assert [t.dep for t in written] == sorted(t.dep for t in written)
    assert fetcher.calls[0][3:] == (SINCE, UNTIL) and fetcher.calls[0][2] == UNTIL.date()


def test_the_fixture_provider_picks_the_new_file_up_by_itself(tmp_path):
    record_fixtures(["Wrocław Główny"], DEST, SINCE, UNTIL, tmp_path, FakeFetcher())
    found = FixtureProvider(tmp_path).search("Wrocław Główny", DEST, UNTIL.date())
    assert found and all(t.dep.date().day in (10, 11) for t in found)
    assert FixtureProvider(tmp_path).origins(DEST) == ["Wrocław Główny"]


def test_one_failing_origin_does_not_stop_the_others(tmp_path):
    progress = []
    recording = record_fixtures(["Wrocław Główny", "Poznań Główny", "Katowice"], DEST, SINCE, UNTIL, tmp_path,
                                FakeFetcher(fail={"Poznań Główny"}), on_progress=progress.append)
    assert [r.origin for r in recording.done] == ["Wrocław Główny", "Katowice"]
    assert recording.failed == {"Poznań Główny": "TimeoutError: Koleo did not answer"}
    assert not (tmp_path / "poznan_krakow_1011.json").exists()
    assert any("FAILED" in line for line in progress)


def test_an_empty_result_is_a_failure_with_the_reason(tmp_path):
    class Empty:
        def fetch(self, *args, **kwargs):
            return ValidationResult()

    recording = record_fixtures(["Wrocław Główny"], DEST, SINCE, UNTIL, tmp_path, Empty())
    assert "no trips" in recording.failed["Wrocław Główny"] and list(tmp_path.glob("*.json")) == []


def test_overlapping_recorded_dates_are_refused_and_nothing_is_written(tmp_path):
    first = record_fixtures(["Wrocław Główny"], DEST, SINCE, UNTIL, tmp_path, FakeFetcher())
    assert first.done
    again = record_fixtures(["Wrocław Główny"], DEST, SINCE, UNTIL, tmp_path, FakeFetcher(), suffix="other")
    assert "already exist in other fixture files" in again.failed["Wrocław Główny"]
    assert sorted(p.name for p in tmp_path.glob("*.json")) == ["wroclaw_krakow_1011.json"]


def test_recording_the_same_file_again_replaces_it(tmp_path):
    record_fixtures(["Wrocław Główny"], DEST, SINCE, UNTIL, tmp_path, FakeFetcher())
    again = record_fixtures(["Wrocław Główny"], DEST, SINCE, UNTIL, tmp_path, FakeFetcher())
    assert again.failed == {} and len(list(tmp_path.glob("*.json"))) == 1


def test_the_suffix_can_be_chosen(tmp_path):
    recording = record_fixtures(["Katowice"], DEST, SINCE, UNTIL, tmp_path, FakeFetcher(), suffix="demo")
    assert recording.done[0].path.name == "katowice_krakow_demo.json"
