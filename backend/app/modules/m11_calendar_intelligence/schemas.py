"""API schemas for the Calendar Intelligence module (module 11)."""

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class CalendarProvider(str, Enum):
    GOOGLE = "google"
    CALDAV = "caldav"  # Outlook, Apple, Fastmail, any CalDAV server


class WindowSchema(BaseModel):
    start: str = Field(pattern=r"^\d{2}:\d{2}$")  # "HH:MM"
    end: str = Field(pattern=r"^\d{2}:\d{2}$")


class SchedulingPrefsSchema(BaseModel):
    working_hours: dict[int, list[WindowSchema]] = Field(default_factory=dict)
    energy_curve: dict[int, int] = Field(default_factory=dict)  # hour -> 1..5
    focus_blocks: dict[int, list[WindowSchema]] = Field(default_factory=dict)
    travel_minutes_default: int = Field(default=0, ge=0, le=180)
    travel_overrides: dict[str, int] = Field(default_factory=dict)  # "locA|locB" (sorted) -> minutes


class GoogleSourceCreate(BaseModel):
    account_email: str = Field(min_length=3, max_length=320)
    calendar_id: str = Field(default="primary", max_length=320)
    refresh_token: str = Field(min_length=1)


class CalDAVSourceCreate(BaseModel):
    account_email: str = Field(min_length=3, max_length=320)
    calendar_url: str = Field(min_length=8)
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class CalendarSourceView(BaseModel):
    id: str
    provider: CalendarProvider
    account_email: str
    calendar_ref: str
    watch_expiration: datetime | None = None
    has_sync_token: bool = False
    created_at: datetime


class CalendarEventView(BaseModel):
    id: str
    uid: str
    source_id: str
    summary: str
    start: datetime | None
    end: datetime | None
    location: str | None = None
    status: str = "confirmed"


class SchedulingTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    duration_minutes: int = Field(ge=15, le=24 * 60)
    deadline: datetime
    priority: int = Field(default=3, ge=1, le=5)
    location: str | None = Field(default=None, max_length=300)
    prep_minutes: int = Field(default=0, ge=0, le=24 * 60)
    splittable: bool = False
    min_block_minutes: int = Field(default=30, ge=15)


class SchedulingTaskView(SchedulingTaskCreate):
    id: str
    status: str = "pending"
    created_at: datetime


class PlannedBlock(BaseModel):
    task_id: str
    kind: Literal["task", "prep"]
    start: datetime
    end: datetime
    location: str | None = None


class WeeklyPlanView(BaseModel):
    id: str
    week_start: str  # ISO date
    status: str  # draft | proposed | applied
    approval_id: str | None = None
    blocks: list[PlannedBlock] = []


class ConflictAlternative(BaseModel):
    kind: Literal["split_task", "extend_hours", "reschedule_lowest_priority"]
    summary: str
    blocks: list[PlannedBlock] = []
    displaced_task_ids: list[str] = []


class ConflictReport(BaseModel):
    task_id: str
    reason: str
    alternatives: list[ConflictAlternative] = []


class ProposedAction(BaseModel):
    approval_id: str
    action_type: Literal["apply_calendar_plan", "apply_reschedule"]
    status: Literal["pending"] = "pending"
    payload: dict[str, Any]


class DayLoad(BaseModel):
    date: str
    meeting_minutes: int
    meeting_count: int
    longest_meeting_minutes: int
    short_gaps: int  # free gaps < 30 min between meetings (fragmentation)


class MeetingLoadReport(BaseModel):
    week_start: str
    days: list[DayLoad]
    total_meeting_minutes: int


class SyncResult(BaseModel):
    source_id: str
    fetched: int = 0
    upserted: int = 0
    cancelled: int = 0
    full_resync: bool = False


class EventConflictView(BaseModel):
    id: str
    left_event_id: str
    right_event_id: str
    left_source_id: str
    right_source_id: str
    overlap_start: datetime
    overlap_end: datetime
    overlap_minutes: int = Field(ge=1)
    severity: Literal["hard", "soft"]


class SchedulingProposalRequest(BaseModel):
    earliest: datetime
    latest: datetime
    duration_minutes: int = Field(ge=15, le=24 * 60)
    limit: int = Field(default=5, ge=1, le=50)
    buffer_before_minutes: int = Field(default=0, ge=0, le=24 * 60)
    buffer_after_minutes: int = Field(default=0, ge=0, le=24 * 60)
    granularity_minutes: Literal[5, 10, 15, 30, 60] = 15
    source_ids: list[str] = Field(default_factory=list)


class SchedulingCandidateView(BaseModel):
    start: datetime
    end: datetime
    score: float
    reasons: list[str]


class SchedulingProposalView(BaseModel):
    candidates: list[SchedulingCandidateView]
    considered_event_count: int = Field(ge=0)
