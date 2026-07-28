"""Duty status constants and segment dataclasses (pure Python, no Django)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class DutyStatus(str, Enum):
    OFF = "OFF"
    SB = "SB"
    D = "D"
    ON = "ON"


ON_DUTY_STATUSES = {DutyStatus.D, DutyStatus.ON}


@dataclass
class DutySegment:
    status: DutyStatus
    start_at: datetime
    end_at: datetime
    location_label: str = ""
    lat: float | None = None
    lng: float | None = None
    remark: str = ""
    is_34h_restart_segment: bool = False

    @property
    def duration_hours(self) -> float:
        return (self.end_at - self.start_at).total_seconds() / 3600.0


@dataclass
class TripStopEvent:
    stop_type: str  # origin|pickup|fuel|rest|dropoff
    label: str
    lat: float
    lng: float
    arrive_at: datetime
    depart_at: datetime
    duration_hours: float
    duty_status: str


@dataclass
class CycleRecalcEvent:
    at: datetime
    dropped_date: str
    dropped_hours: float
    new_remaining: float


@dataclass
class Restart34Event:
    at: datetime
    duration_hours: float


@dataclass
class DailyLogSheet:
    date: str
    from_location: str
    to_location: str
    total_miles_driving: float
    segments: list[dict[str, Any]]
    totals: dict[str, float]
    remarks: list[dict[str, str]]
    recap: dict[str, float]


@dataclass
class SimulationResult:
    segments: list[DutySegment] = field(default_factory=list)
    stops: list[TripStopEvent] = field(default_factory=list)
    daily_logs: list[DailyLogSheet] = field(default_factory=list)
    midnight_recaps: list[CycleRecalcEvent] = field(default_factory=list)
    restarts_34h: list[Restart34Event] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    approximate_routing: bool = False
