"""Response and request models for the UI API. Timestamps are ISO 8601 UTC; the frontend
formats durations ("3 days ago") itself."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.engines.reviews import Choice


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Today ------------------------------------------------------------------------------------


class PendingItem(Out):
    solve_id: int
    slug: str
    title: str
    difficulty: str
    accepted_at: datetime
    wrong_before_ac: int
    default: Choice | None


class DueItem(Out):
    slug: str
    title: str
    difficulty: str
    due: datetime
    recall: float
    priority: float


class DueSection(BaseModel):
    items: list[DueItem]  # every due card, highest priority first
    shown: int  # how many fit in today's target (the rest roll over)
    total_due: int
    done_today: int
    target: int


class AttemptedItem(BaseModel):
    slug: str
    title: str
    difficulty: str
    last_status: str | None
    last_submitted_at: datetime | None


class StudyModeOut(BaseModel):
    enabled: bool
    until: date | None
    active: bool  # enabled and not past `until`


class TargetOut(Out):
    mode: str
    daily_target: int
    retention: float
    interview_end_date: date | None
    previous_mode: str | None


class TodayOut(BaseModel):
    pending: list[PendingItem]
    due: DueSection
    attempted: list[AttemptedItem]
    study_mode: StudyModeOut
    target: TargetOut
    backfill_done: bool


# --- Problem detail ---------------------------------------------------------------------------


class TopicTag(BaseModel):
    name: str
    slug: str


class ProblemOut(Out):
    slug: str
    title: str
    difficulty: str
    frontend_id: str | None
    topic_tags: list[TopicTag]
    ac_rate: float | None
    is_paid_only: bool
    url: str


class CardOut(Out):
    due: datetime
    recall: float
    reps: int
    lapses: int
    suspended: bool
    last_review: datetime | None


class TimelineSubmissionOut(Out):
    id: int
    status: str
    lang: str
    runtime_ms: int | None
    at: datetime


class TimelineEntryOut(Out):
    kind: Literal["solve", "review", "attempts"]
    at: datetime
    solve_id: int | None
    wrong_before_ac: int | None
    choice: Choice | None
    rating_source: str | None
    submissions: list[TimelineSubmissionOut]


class ProblemDetailOut(BaseModel):
    problem: ProblemOut
    card: CardOut | None
    timeline: list[TimelineEntryOut]


# --- Requests ---------------------------------------------------------------------------------


class ChoiceIn(BaseModel):
    choice: Choice


class ConfirmIn(BaseModel):
    solve_ids: list[int] = Field(min_length=1)


class TargetIn(BaseModel):
    mode: Literal["casual", "steady", "interview", "custom"]
    daily_target: int | None = Field(default=None, ge=1, le=100)
    retention: float | None = Field(default=None, ge=0.70, le=0.97)
    interview_end_date: date | None = None


class StudyModeIn(BaseModel):
    enabled: bool
    until: date | None = None
