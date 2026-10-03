"""Reads the text of a Koleo search results page (CLAUDE.md, sections 3 and 9).

Deterministic code, no LLM. It turns the page text into raw facts (category, times, price,
changes) that go through the Validator like any other live result. It is also the reference the
Gemini agent can be cross-checked against.

A row of the page text looks like this (one value per line):

    16:10            departure
    19:27            arrival
    3h 17min         duration
    Bezpośrednie     or "1 przesiadka" / "2 przesiadki"
    IC               one category line per vehicle: "IC", then "KŚ" for a trip with a change
    Kup bilet        missing when the price is unknown
    63,00 zł         missing when the price is unknown

Dates come from headers such as "SOBOTA" / "3 października" between the rows.
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

WARSAW = ZoneInfo("Europe/Warsaw")

MONTHS = {
    "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5, "czerwca": 6,
    "lipca": 7, "sierpnia": 8, "września": 9, "października": 10, "listopada": 11, "grudnia": 12,
}
WEEKDAYS = {"PONIEDZIAŁEK", "WTOREK", "ŚRODA", "CZWARTEK", "PIĄTEK", "SOBOTA", "NIEDZIELA"}
NOT_CATEGORIES = {"Kup bilet", "Wcześniejsze połączenia", "Późniejsze połączenia", "Znajdź połączenie"}

TIME = re.compile(r"^(\d{1,2}):(\d{2})$")
DURATION = re.compile(r"^(?:(\d+)h)?\s*(?:(\d+)min)?$")
DATE_HEADER = re.compile(r"^(\d{1,2}) ([^\W\d_]+)$")
TRANSFERS = re.compile(r"^(?:Bezpośrednie|(\d+) przesiadk\w*)$")
# Koleo puts a non-breaking space (U+00A0) before "zł"; `\s` matches it as well as a plain space.
PRICE = re.compile(r"^(\d[\d\s]*),(\d{2})\s*zł$")
HEADER = re.compile(r"^PKP (.+?) — (.+)$")


@dataclass
class ParsedPage:
    origin: str | None = None       # station names as the page header spells them
    destination: str | None = None
    rows: list[dict] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # rows that looked like options but were inconsistent


def _is_category(line: str) -> bool:
    return (
        line not in NOT_CATEGORIES
        and line not in WEEKDAYS
        and 1 <= len(line) <= 6
        and line.isalpha()
        and line.isupper()
    )


def _duration(line: str) -> timedelta | None:
    match = DURATION.match(line)
    if not line or not match or not (match.group(1) or match.group(2)):
        return None
    return timedelta(hours=int(match.group(1) or 0), minutes=int(match.group(2) or 0))


def _time(line: str) -> time | None:
    match = TIME.match(line)
    if not match or int(match.group(1)) > 23 or int(match.group(2)) > 59:
        return None
    return time(int(match.group(1)), int(match.group(2)))


def parse_page(text: str, origin: str, destination: str, year: int) -> ParsedPage:
    """Parse one results page. `origin`/`destination` are the requested stations (the page text
    does not repeat them in every row); the header is returned so the caller can check it.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    page = ParsedPage()
    current: date | None = None
    i = 0
    while i < len(lines):
        line = lines[i]
        header = HEADER.match(line)
        if header and page.origin is None:
            page.origin, page.destination = header.group(1), header.group(2)
        match = DATE_HEADER.match(line)
        if match and match.group(2) in MONTHS:
            current = date(year, MONTHS[match.group(2)], int(match.group(1)))
            i += 1
            continue

        dep_t = _time(line)
        arr_t = _time(lines[i + 1]) if i + 1 < len(lines) else None
        duration = _duration(lines[i + 2]) if i + 2 < len(lines) else None
        transfers = TRANSFERS.match(lines[i + 3]) if i + 3 < len(lines) else None
        if dep_t is None or arr_t is None or duration is None or transfers is None or current is None:
            i += 1
            continue

        j = i + 4
        categories = []
        while j < len(lines) and _is_category(lines[j]):
            categories.append(lines[j])
            j += 1
        if j < len(lines) and lines[j] == "Kup bilet":
            j += 1
        price = None
        if j < len(lines) and PRICE.match(lines[j]):
            amount = PRICE.match(lines[j])
            price = float(re.sub(r"\s", "", amount.group(1)) + "." + amount.group(2))
            j += 1

        changes = int(transfers.group(1) or 0)
        label = f"{dep_t:%H:%M}->{arr_t:%H:%M} {'+'.join(categories) or '?'}"
        dep = datetime.combine(current, dep_t, tzinfo=WARSAW)
        arr = datetime.combine(current, arr_t, tzinfo=WARSAW)
        if arr <= dep:
            arr += timedelta(days=1)
        if not categories:
            page.skipped.append(f"{label}: no category")
        elif changes != len(categories) - 1:
            page.skipped.append(f"{label}: {changes} changes but {len(categories)} categories")
        elif abs((arr - dep) - duration) > timedelta(minutes=1):
            page.skipped.append(f"{label}: duration {duration} does not match the times")
        else:
            page.rows.append({
                "category": "+".join(categories),
                "from": origin,
                "to": destination,
                "dep": dep.isoformat(),
                "arr": arr.isoformat(),
                "price_pln": price,
                "changes": changes,
            })
        i = j
    return page


def merge_rows(pages: list[list[dict]]) -> list[dict]:
    """Pages overlap by design. Keep one row per trip; a row with a price beats one without."""
    merged: dict[tuple, dict] = {}
    for rows in pages:
        for row in rows:
            key = (row["dep"], row["arr"], row["category"])
            if key not in merged or (merged[key]["price_pln"] is None and row["price_pln"] is not None):
                merged[key] = row
    return sorted(merged.values(), key=lambda r: (r["dep"], r["arr"], r["category"]))
