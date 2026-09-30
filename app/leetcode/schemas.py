"""Pydantic models for LeetCode responses, normalized at the boundary.

LeetCode is inconsistent across queries (e.g. difficulty "MEDIUM" vs "Medium", timestamps as
epoch strings, epoch ints, or ISO strings, runtime as "39 ms", 39, or "N/A"). Everything past
this module sees one shape: UTC datetimes, int IDs, "Easy"/"Medium"/"Hard", runtime in ms.
"""

import json
import re
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import AliasChoices, BaseModel, BeforeValidator, ConfigDict, Field
from pydantic.alias_generators import to_camel

ACCEPTED = 10  # submission status code for "Accepted"


def _to_datetime(value: Any) -> Any:
    """Epoch seconds (int or digit string) -> UTC datetime; ISO strings pass through."""
    if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
        return datetime.fromtimestamp(int(value), tz=UTC)
    return value


def _to_difficulty(value: Any) -> Any:
    return value.capitalize() if isinstance(value, str) else value


def _to_runtime_ms(value: Any) -> Any:
    """39 or "39 ms" -> 39; "N/A" (failed runs) -> None."""
    if isinstance(value, str):
        match = re.fullmatch(r"\s*(\d+)\s*ms\s*", value)
        return int(match.group(1)) if match else None
    return value


def _parse_json_string(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


UtcDatetime = Annotated[datetime, BeforeValidator(_to_datetime)]
Difficulty = Annotated[Literal["Easy", "Medium", "Hard"], BeforeValidator(_to_difficulty)]
RuntimeMs = Annotated[int | None, BeforeValidator(_to_runtime_ms)]


class LeetCodeModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")


class TopicTag(LeetCodeModel):
    name: str
    slug: str


class UserStatus(LeetCodeModel):
    user_id: int | None = None
    is_signed_in: bool
    username: str | None = None


class ProgressQuestion(LeetCodeModel):
    """A problem the user has touched, from the progress list."""

    frontend_id: str
    title: str
    title_slug: str
    difficulty: Difficulty
    last_submitted_at: UtcDatetime
    num_submitted: int
    question_status: str  # SOLVED / ATTEMPTED
    last_result: str | None = None  # AC / WA / TLE / ...
    topic_tags: list[TopicTag] = []

    @property
    def solved(self) -> bool:
        return self.question_status == "SOLVED"


class ProgressPage(LeetCodeModel):
    total_num: int
    questions: list[ProgressQuestion]


class SubmissionSummary(LeetCodeModel):
    """One submission in a problem's submission list (no code)."""

    id: int
    title_slug: str
    status: int
    status_display: str
    lang: str
    runtime_ms: RuntimeMs = Field(default=None, validation_alias="runtime")
    timestamp: UtcDatetime

    @property
    def accepted(self) -> bool:
        return self.status == ACCEPTED


class SubmissionPage(LeetCodeModel):
    last_key: str | None = None
    has_next: bool
    submissions: list[SubmissionSummary]


class Lang(LeetCodeModel):
    name: str
    verbose_name: str | None = None


class QuestionRef(LeetCodeModel):
    question_id: str
    title_slug: str


class SubmissionDetail(LeetCodeModel):
    """Full detail of one submission, including its code."""

    runtime_ms: RuntimeMs = Field(default=None, validation_alias="runtime")
    memory_bytes: int | None = Field(default=None, validation_alias="memory")
    code: str
    timestamp: UtcDatetime
    status_code: int
    lang: Lang
    question: QuestionRef


class SimilarQuestion(LeetCodeModel):
    title: str
    title_slug: str
    difficulty: Difficulty


class QuestionDetail(LeetCodeModel):
    question_id: str
    frontend_id: str = Field(validation_alias=AliasChoices("questionFrontendId", "frontend_id"))
    title: str
    title_slug: str
    # HTML; None for paid-only problems without Premium.
    statement: str | None = Field(
        default=None, validation_alias=AliasChoices("content", "statement")
    )
    difficulty: Difficulty
    is_paid_only: bool = False
    ac_rate: float | None = None  # percent, e.g. 59.5
    similar_questions: Annotated[list[SimilarQuestion], BeforeValidator(_parse_json_string)] = []
    topic_tags: list[TopicTag] = []


class RecentAc(LeetCodeModel):
    id: int
    title: str
    title_slug: str
    timestamp: UtcDatetime
