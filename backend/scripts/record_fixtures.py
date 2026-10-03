"""Record Koleo timetables as fixture files for a chosen date.

Run from the backend folder, with the virtual environment active and Chrome installed:

    python scripts/record_fixtures.py --since 2026-10-10T16:00 --until 2026-10-11T08:30

Times without a zone are read as Europe/Warsaw. By default every origin the fixtures already
know is recorded; use --origin (repeatable) for some of them. Files are written to
data/fixtures/trains/<origin>_<destination>_<MMDD>.json. A window that overlaps trips already
recorded in another file is refused (ids would clash): choose another window or remove the old file.
Takes about 30 to 60 seconds per origin, because Koleo needs 10 to 15 seconds per page.
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import FIXTURES_DIR  # noqa: E402
from app.providers.fixture import FixtureProvider  # noqa: E402
from app.providers.koleo_agent import KoleoAgentProvider  # noqa: E402
from app.providers.koleo_parser import WARSAW  # noqa: E402
from app.providers.recorder import record_fixtures  # noqa: E402


def moment(text: str) -> datetime:
    value = datetime.fromisoformat(text)
    return value if value.tzinfo else value.replace(tzinfo=WARSAW)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--since", type=moment, required=True, help="first departure to read, e.g. 2026-10-10T16:00")
    parser.add_argument("--until", type=moment, required=True, help="last departure worth reading, e.g. 2026-10-11T08:30")
    parser.add_argument("--origin", action="append", help="station as on Koleo; repeat for several (default: all known)")
    parser.add_argument("--destination", default="Kraków Główny")
    parser.add_argument("--out", type=Path, default=FIXTURES_DIR / "trains")
    parser.add_argument("--suffix", help="file name suffix (default: month and day of --until, e.g. 1011)")
    args = parser.parse_args()

    origins = args.origin or FixtureProvider().origins(args.destination)
    print(f"recording {len(origins)} origin(s) to {args.out}: {', '.join(origins)}")
    recording = record_fixtures(
        origins, args.destination, args.since, args.until, args.out,
        KoleoAgentProvider(api_key="", cache_ttl_sec=0),  # no key: the code parser only, no Gemini
        suffix=args.suffix, on_progress=print,
    )
    print(f"\n{len(recording.done)} recorded, {len(recording.failed)} failed")
    return 1 if recording.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
