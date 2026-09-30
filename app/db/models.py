"""SQLAlchemy models for the 14 tables in the design doc.

Conventions:
- All datetimes are stored as UTC.
- Mastery, node states, and due counts are computed on view, never stored.
- Secrets (session cookie, LLM key) never go in the database.
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON, datetime: DateTime()}


# --- LeetCode data ----------------------------------------------------------


class Problem(Base):
    """A problem the user solved or attempted, or one considered as a suggestion."""

    __tablename__ = "problems"

    slug: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str]
    difficulty: Mapped[str]  # Easy / Medium / Hard
    ac_rate: Mapped[float | None]
    topic_tags: Mapped[list[Any]] = mapped_column(default=list)
    similar_questions: Mapped[list[Any]] = mapped_column(default=list)
    statement: Mapped[str | None] = mapped_column(Text)  # HTML; None for paid-only
    fetched_at: Mapped[datetime | None]  # when question details were fetched
    frontend_id: Mapped[str | None]
    is_paid_only: Mapped[bool] = mapped_column(default=False, server_default="0")

    # Sync markers from LeetCode's progress list. A problem whose stored markers equal the
    # remote ones is fully synced; they are written in the same transaction as its submissions.
    question_status: Mapped[str | None]  # SOLVED / ATTEMPTED
    last_result: Mapped[str | None]  # AC / WA / TLE / ...
    last_submitted_at: Mapped[datetime | None]
    num_submitted: Mapped[int | None]


class Submission(Base):
    """One LeetCode submission, accepted or failed."""

    __tablename__ = "submissions"

    submission_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    slug: Mapped[str] = mapped_column(ForeignKey("problems.slug"), index=True)
    status: Mapped[str]  # e.g. Accepted, Wrong Answer, Time Limit Exceeded
    lang: Mapped[str]
    timestamp: Mapped[datetime] = mapped_column(index=True)
    runtime_ms: Mapped[int | None]
    code: Mapped[str | None] = mapped_column(Text)
    code_hash: Mapped[str | None] = mapped_column(String, index=True)


class Solve(Base):
    """An accepted submission grouped with the failed attempts before it."""

    __tablename__ = "solves"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(ForeignKey("problems.slug"), index=True)
    accepted_submission_id: Mapped[int] = mapped_column(
        ForeignKey("submissions.submission_id"), unique=True
    )
    wrong_before_ac: Mapped[int] = mapped_column(default=0)
    accepted_at: Mapped[datetime]
    rating: Mapped[int | None]  # effective FSRS rating 1-4; null until scheduled
    # history: from the first backfill, inferred silently
    # inferred: default applied, awaiting the user's confirmation ("Rate your new solves")
    # user: chosen by the user
    rating_source: Mapped[str] = mapped_column(default="inferred", server_default="inferred")
    # "Saw solution": learned from the solution; scheduled as Again but kept distinct.
    used_solution: Mapped[bool] = mapped_column(default=False, server_default="0")


# --- Spaced repetition -------------------------------------------------------


class Card(Base):
    """FSRS card for a solved problem: a cache rebuilt by replaying its review_log rows."""

    __tablename__ = "cards"

    slug: Mapped[str] = mapped_column(ForeignKey("problems.slug"), primary_key=True)
    due: Mapped[datetime] = mapped_column(index=True)
    stability: Mapped[float | None] = mapped_column(Float)
    difficulty: Mapped[float | None] = mapped_column(Float)
    reps: Mapped[int] = mapped_column(default=0)
    lapses: Mapped[int] = mapped_column(default=0)
    state: Mapped[int] = mapped_column(default=1)  # fsrs.State value
    last_review: Mapped[datetime | None]
    suspended: Mapped[bool] = mapped_column(default=False)


class ReviewLog(Base):
    """One review event and the source of truth for scheduling.

    One row per solve, plus manual "Mark reviewed" rows. Kept forever so FSRS parameters
    can be tuned to the user's history later.
    """

    __tablename__ = "review_log"
    __table_args__ = (Index("ux_review_log_solve_id", "solve_id", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(ForeignKey("problems.slug"), index=True)
    # At most one row per solve; null for manual "Mark reviewed" events.
    solve_id: Mapped[int | None] = mapped_column(ForeignKey("solves.id"))
    rating: Mapped[int]
    reviewed_at: Mapped[datetime]


# --- Skill tree ----------------------------------------------------------------


class Skill(Base):
    """A skill tree node built by the LLM taxonomy step."""

    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    description: Mapped[str | None] = mapped_column(Text)
    aliases: Mapped[list[Any]] = mapped_column(default=list)
    created_at: Mapped[datetime] = mapped_column(server_default=func.current_timestamp())
    merged_into: Mapped[int | None] = mapped_column(ForeignKey("skills.id"))


class SkillEdge(Base):
    __tablename__ = "skill_edges"

    from_skill: Mapped[int] = mapped_column(ForeignKey("skills.id"), primary_key=True)
    to_skill: Mapped[int] = mapped_column(ForeignKey("skills.id"), primary_key=True)
    type: Mapped[str] = mapped_column(primary_key=True)  # prerequisite / related


class ProblemSkill(Base):
    __tablename__ = "problem_skills"

    slug: Mapped[str] = mapped_column(ForeignKey("problems.slug"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), primary_key=True, index=True)
    confidence: Mapped[float | None]


# --- LLM outputs ------------------------------------------------------------------


class ProblemAnalysis(Base):
    __tablename__ = "problem_analysis"

    slug: Mapped[str] = mapped_column(ForeignKey("problems.slug"), primary_key=True)
    techniques: Mapped[list[Any]] = mapped_column(default=list)
    key_insight: Mapped[str | None] = mapped_column(Text)
    what_makes_it_hard: Mapped[str | None] = mapped_column(Text)
    optimal_time: Mapped[str | None]
    optimal_space: Mapped[str | None]
    model: Mapped[str]
    prompt_version: Mapped[str]


class SolutionAnalysis(Base):
    __tablename__ = "solution_analysis"

    submission_id: Mapped[int] = mapped_column(
        ForeignKey("submissions.submission_id"), primary_key=True, autoincrement=False
    )
    approach: Mapped[str | None] = mapped_column(Text)
    time_complexity: Mapped[str | None]
    space_complexity: Mapped[str | None]
    is_optimal: Mapped[bool | None]
    mistakes: Mapped[list[Any]] = mapped_column(default=list)
    model: Mapped[str]
    prompt_version: Mapped[str]


class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.current_timestamp())
    text: Mapped[str] = mapped_column(Text)
    stats_snapshot: Mapped[dict[str, Any]] = mapped_column(default=dict)


class Suggestion(Base):
    __tablename__ = "suggestions"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    slug: Mapped[str] = mapped_column(ForeignKey("problems.slug"), primary_key=True)
    skill_id: Mapped[int | None] = mapped_column(ForeignKey("skills.id"))
    reason: Mapped[str | None] = mapped_column(Text)
    rank: Mapped[int]


# --- Key-value state ----------------------------------------------------------------


class Setting(Base):
    """Key-value settings: target_mode, daily_target, desired_retention, ..."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)


class SyncState(Base):
    """Key-value sync state: last_sync_at, backfill_done, per-problem backfill progress."""

    __tablename__ = "sync_state"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
