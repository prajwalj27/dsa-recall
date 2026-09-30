"""Response and request models for the UI API. Timestamps are ISO 8601 UTC; the frontend
formats durations ("3 days ago") itself."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    frontend_id: str | None


class DueItem(Out):
    slug: str
    title: str
    difficulty: str
    due: datetime
    recall: float
    priority: float
    frontend_id: str | None
    last_review: datetime | None  # last solved: latest re-solve or manual review


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
    frontend_id: str | None
    last_status: str | None
    last_submitted_at: datetime | None


class StudyModeOut(BaseModel):
    enabled: bool


class TargetOut(Out):
    mode: str
    daily_target: int
    retention: float
    interview_target: int  # Interview's saved values (to pre-fill the form)
    interview_retention: float


class TodayOut(BaseModel):
    pending: list[PendingItem]
    due: DueSection
    attempted: list[AttemptedItem]
    study_mode: StudyModeOut
    target: TargetOut
    paused: list[DueItem]  # most recently solved first
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
    paused: bool  # out of the review queue until resumed or re-solved
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


class PauseIn(BaseModel):
    slugs: list[str] = Field(min_length=1)


class ResumeIn(BaseModel):
    """Either specific problems, or `all: true` for every paused problem."""

    slugs: list[str] = []
    all: bool = False

    @model_validator(mode="after")
    def _one_of(self) -> "ResumeIn":
        if not self.all and not self.slugs:
            raise ValueError("give slugs, or all: true")
        return self


class ChangedOut(BaseModel):
    changed: int


class ConfirmIn(BaseModel):
    solve_ids: list[int] = Field(min_length=1)


class TargetIn(BaseModel):
    """Casual and Steady take no values; Interview takes a number and/or a retention."""

    mode: Literal["casual", "steady", "interview"]
    daily_target: int | None = Field(default=None, ge=1, le=100)
    retention: float | None = Field(default=None, ge=0.70, le=0.97)


class StudyModeIn(BaseModel):
    enabled: bool
