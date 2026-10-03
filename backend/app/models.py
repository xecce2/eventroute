"""Contracts from CLAUDE.md section 4. Change here => update CLAUDE.md in the same commit."""
from datetime import datetime, timedelta
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

# A map point, serialized as [lat, lon].
LatLon = tuple[Annotated[float, Field(ge=-90, le=90)], Annotated[float, Field(ge=-180, le=180)]]


class Contract(BaseModel):
    # "from" is a Python keyword: the field is `from_`, (de)serialized as "from".
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class DelayModel(Contract):
    p_on_time: float = Field(ge=0, le=1)
    mean_delay_min: int = Field(ge=0)
    p95_delay_min: int = Field(ge=0)


class TrainOption(Contract):
    id: str
    source: Literal["koleo", "fixture", "playwright"]
    fetched_at: AwareDatetime
    mode: Literal["train", "bus"]
    category: str
    train: str
    from_: str = Field(alias="from")
    to: str
    dep: AwareDatetime
    arr: AwareDatetime
    price_pln: float | None = Field(default=None, ge=0)
    changes: int = Field(ge=0)
    delay_model: DelayModel
    known_delay_min: int = Field(default=0, ge=0)
    url: str

    @property
    def expected_arr(self) -> datetime:
        return self.arr + timedelta(minutes=self.known_delay_min)


class LocalLeg(Contract):
    mode: Literal["tram", "walk", "bus"]
    from_: str = Field(alias="from")
    to: str
    dep: AwareDatetime
    arr: AwareDatetime
    duration_min: int
    std_min: int
    line: str | None = None
    # Points of the leg in order, for the map line. None -> the map draws a straight line.
    path: list[LatLon] | None = None


Label = Literal["safest", "fastest", "cheapest"]


class Plan(Contract):
    id: str
    labels: list[Label]
    train: TrainOption
    local_legs: list[LocalLeg]
    venue_target: AwareDatetime
    arrival_at_venue: AwareDatetime
    buffer_min: int
    p_on_time: float
    price_pln: float | None
    overnight_stay: bool
    explanation: str
    buy_url: str


class Event(Contract):
    id: str
    name: str
    venue: str
    venue_station: str
    city: str
    start: AwareDatetime
    checkin_buffer_min: int
    lat: float
    lon: float

    @property
    def venue_target(self) -> datetime:
        return self.start - timedelta(minutes=self.checkin_buffer_min)


class PlanRequest(Contract):
    origin: str
    event_id: str
    arrive_by: AwareDatetime | None = None
    budget_pln: float | None = Field(default=None, gt=0)
    mode_pref: Literal["train", "bus"] | None = None  # None -> both


DataSource = Literal["live", "recorded", "mixed"]


class PlanResponse(Contract):
    request_id: str
    plans: list[Plan]
    options: list[Plan]  # every suitable option, cheapest first (unknown price last)
    status: Literal["ok", "no_options"]
    data_source: DataSource
    fallback_reason: str | None  # set when a live search was expected but recorded data was used


class DisruptionRequest(Contract):
    plan_id: str
    train_delay_min: int = Field(ge=0, le=600)


class DisruptionResponse(Contract):
    affected_plan: Plan
    plans: list[Plan]
    options: list[Plan]
    notified: bool
    message: str
    data_source: DataSource
    fallback_reason: str | None


class ProviderStatus(Contract):
    provider: Literal["fixture", "koleo"]  # what TRAIN_PROVIDER asks for
    live_available: bool  # False when the live provider is configured but cannot run
    requests_total: int
    live_ok: int
    live_partial: int  # live searches where the Validator rejected some (not all) options
    fallback: int
    last_fallback_reason: str | None
    last_rejection_reason: str | None


class Participant(Contract):
    """Synthetic participant (data/fixtures/participants.json or the generator). No personal data."""
    id: str
    origin: str
    pref: Label


Load = Literal["low", "medium", "high"]


class ArrivalSlot(Contract):
    slot: AwareDatetime
    count: int


class CityNode(Contract):
    name: str
    lat: float
    lon: float
    peak_count: int
    peak_slot: AwareDatetime | None
    load: Load


class OriginCount(Contract):
    station: str
    count: int


class Recommendation(Contract):
    type: Literal["stagger_checkin", "add_trams"]
    text: str
    severity: Load


class CityOverview(Contract):
    event_id: str
    participants_total: int
    arrivals_by_slot: list[ArrivalSlot]
    nodes: list[CityNode]
    origins: list[OriginCount]
    recommendations: list[Recommendation]
