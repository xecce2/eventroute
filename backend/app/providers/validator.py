"""Validator for what a live agent returns (CLAUDE.md, sections 3 and 9).

The agent only reports facts it read on the page: category, stations, times, price, changes.
Everything else is added here by code and never taken from the agent: id, source, fetched_at,
url (built from the Koleo template, so a page cannot send the user to another site), mode and
delay_model. Anything that fails a check is rejected with a reason; nothing is silently fixed.
"""
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError

from app.models import TrainOption
from app.providers.delay_models import DELAY_BY_CATEGORY, delay_model_for, split_category

MIN_TRIP_MIN = 15
MAX_TRIP_MIN = 16 * 60
MAX_PRICE_PLN = 1000.0
MAX_CHANGES = 3
WARSAW = ZoneInfo("Europe/Warsaw")


class RawOption(BaseModel):
    """What the agent may return for one option. Unknown fields (url, id, source, ...) are ignored."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    category: str
    from_: str = Field(alias="from")
    to: str
    dep: AwareDatetime  # no timezone -> rejected, so the agent has to return the offset
    arr: AwareDatetime
    price_pln: float | None = None
    changes: int = 0


@dataclass
class Rejection:
    index: int
    reason: str
    raw: Any


@dataclass
class ValidationResult:
    accepted: list[TrainOption] = field(default_factory=list)
    rejected: list[Rejection] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.accepted) + len(self.rejected)

    def fallback_reason(self) -> str | None:
        """Text for `fallback_reason` when anything was rejected, else None."""
        if not self.rejected:
            return None
        top = Counter(r.reason for r in self.rejected).most_common(3)
        details = "; ".join(f"{reason} (x{n})" for reason, n in top)
        return f"validator rejected {len(self.rejected)}/{self.total} options: {details}"


def koleo_slug(station: str) -> str:
    """`Wrocław Główny` -> `wroclaw-glowny` (also used to compare names without diacritics)."""
    text = unicodedata.normalize("NFKD", station.casefold().replace("ł", "l"))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return "-".join(text.split())


def koleo_url(origin: str, destination: str, dep: datetime) -> str:
    local = dep.astimezone(WARSAW)
    return (
        f"https://koleo.pl/rozklad-pkp/{koleo_slug(origin)}/{koleo_slug(destination)}"
        f"/{local:%d-%m-%Y_%H:%M}/all/all"
    )


def _problem(
    raw: RawOption, origin: str, destination: str, window: tuple[datetime, datetime]
) -> str | None:
    if koleo_slug(raw.from_) != koleo_slug(origin) or koleo_slug(raw.to) != koleo_slug(destination):
        return "route does not match the request"
    legs = split_category(raw.category)
    if not legs:
        return "empty category"
    unknown = [leg for leg in legs if leg not in DELAY_BY_CATEGORY]
    if unknown:
        return f"unknown category {'+'.join(unknown)}"
    if raw.arr <= raw.dep:
        return "arrival is not after departure"
    minutes = (raw.arr - raw.dep) / timedelta(minutes=1)
    if not MIN_TRIP_MIN <= minutes <= MAX_TRIP_MIN:
        return "implausible trip duration"
    if not window[0] <= raw.dep <= window[1]:
        return "departure outside the search window"
    if raw.price_pln is not None and not 0 < raw.price_pln <= MAX_PRICE_PLN:
        return "implausible price"
    if not 0 <= raw.changes <= MAX_CHANGES:
        return "implausible number of changes"
    return None


def _error_reason(error: ValidationError) -> str:
    first = error.errors()[0]
    field_name = ".".join(str(part) for part in first["loc"]) or "item"
    return f"invalid field {field_name}: {first['msg']}"


def validate_options(
    raw_items: Any,
    *,
    origin: str,
    destination: str,
    window: tuple[datetime, datetime],
    source: Literal["koleo", "playwright"],
    fetched_at: datetime,
) -> ValidationResult:
    """Check a list of raw options and turn the good ones into `TrainOption`.

    `window` is the sanity range for departures (not the planner's filter): it catches
    hallucinated dates. `source` is set by the provider that actually fetched the data.
    """
    result = ValidationResult()
    if not isinstance(raw_items, list):
        result.rejected.append(Rejection(0, "response is not a list", raw_items))
        return result

    seen: set[tuple] = set()
    accepted: list[tuple[RawOption, str]] = []
    for index, item in enumerate(raw_items):
        try:
            raw = RawOption.model_validate(item)
        except ValidationError as error:
            result.rejected.append(Rejection(index, _error_reason(error), item))
            continue
        problem = _problem(raw, origin, destination, window)
        if problem is None:
            category = "+".join(split_category(raw.category))
            key = (raw.dep, raw.arr, category)
            if key in seen:
                problem = "duplicate option"
            seen.add(key)
        if problem is not None:
            result.rejected.append(Rejection(index, problem, item))
            continue
        accepted.append((raw, category))

    origin_key = koleo_slug(origin)[:3]
    base_ids = Counter(f"tr_{origin_key}_{raw.dep.astimezone(WARSAW):%m%d_%H%M}" for raw, _ in accepted)
    for raw, category in accepted:
        train_id = f"tr_{origin_key}_{raw.dep.astimezone(WARSAW):%m%d_%H%M}"
        if base_ids[train_id] > 1:
            train_id += "_" + category.lower().replace("+", "")
        legs = split_category(category)
        result.accepted.append(TrainOption(
            id=train_id,
            source=source,
            fetched_at=fetched_at,
            mode="bus" if set(legs) == {"FLIX"} else "train",
            category=category,
            train=category,
            from_=origin,
            to=destination,
            dep=raw.dep,
            arr=raw.arr,
            price_pln=raw.price_pln,
            changes=raw.changes,
            delay_model=delay_model_for(legs, raw.changes),
            known_delay_min=0,
            url=koleo_url(origin, destination, raw.dep),
        ))
    return result
