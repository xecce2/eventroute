"""Contracts from CLAUDE.md section 4. Change here => update CLAUDE.md in the same commit."""
from datetime import datetime, timedelta
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


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
    budget_pln: float | None = None
    mode_pref: str | None = None


class PlanResponse(Contract):
    request_id: str
    plans: list[Plan]
    status: Literal["ok", "no_options"]


class DisruptionRequest(Contract):
    plan_id: str
    train_delay_min: int = Field(ge=0, le=600)


class DisruptionResponse(Contract):
    affected_plan: Plan
    plans: list[Plan]
    notified: bool
    message: str
