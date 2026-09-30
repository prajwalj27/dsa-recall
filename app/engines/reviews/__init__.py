"""Spaced repetition over solves with FSRS.

`review_log` is the source of truth: one row per solve plus manual "Mark reviewed" rows.
`cards` is a cache: each problem's card is rebuilt by replaying its review rows in order,
so changing any rating is just "update one row, rebuild one card".

The scheduler has no learning steps (minute-level steps suit flashcards, not re-solving a
problem) and no fuzzing (so replays are deterministic).
"""

from bisect import bisect_left
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal

import fsrs
from fsrs import Rating, Scheduler, State
from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.db.models import Card, Problem, ReviewLog, Solve, Submission
from app.settings_store import (
    DEFAULT_RETENTION,
    Target,
    desired_retention,
    get_study_mode,
    get_target,
    revert_expired_interview,
    set_target,
)
from app.sync.solves import MERGE_WINDOW
from app.timeutil import as_utc, utc_naive, utc_now

HISTORY = "history"  # from the first backfill; inferred silently
INFERRED = "inferred"  # default applied, awaiting the user's confirmation
USER = "user"  # chosen by the user


class Choice(StrEnum):
    """What the user can pick when rating a solve."""

    AGAIN = "again"
    HARD = "hard"
    GOOD = "good"
    EASY = "easy"
    SAW_SOLUTION = "saw_solution"  # learned from the solution; scheduled as Again


RATING_OF = {
    Choice.AGAIN: Rating.Again,
    Choice.HARD: Rating.Hard,
    Choice.GOOD: Rating.Good,
    Choice.EASY: Rating.Easy,
    Choice.SAW_SOLUTION: Rating.Again,
}


def make_scheduler(retention: float = DEFAULT_RETENTION) -> Scheduler:
    return Scheduler(
        desired_retention=retention,
        learning_steps=(),
        relearning_steps=(),
        enable_fuzzing=False,
    )


def infer_rating(wrong_before_ac: int) -> Rating:
    if wrong_before_ac >= 3:
        return Rating.Again
    if wrong_before_ac >= 1:
        return Rating.Hard
    return Rating.Good


def choice_of(solve: Solve) -> Choice | None:
    if solve.rating is None:
        return None
    if solve.used_solution:
        return Choice.SAW_SOLUTION
    return Choice(Rating(solve.rating).name.lower())


# --- Replay ------------------------------------------------------------------------------


@dataclass(frozen=True)
class ReplayResult:
    card: fsrs.Card
    reps: int
    lapses: int


def replay(scheduler: Scheduler, reviews: list[tuple[int, datetime]]) -> ReplayResult:
    """Run (rating, reviewed_at) pairs, oldest first, through FSRS from a new card."""
    card, lapses = fsrs.Card(), 0
    for rating, reviewed_at in reviews:
        if card.state == State.Review and rating == Rating.Again:
            lapses += 1
        card, _ = scheduler.review_card(card, Rating(rating), as_utc(reviewed_at))
    return ReplayResult(card, len(reviews), lapses)


def rebuild_card(session: Session, slug: str, scheduler: Scheduler | None = None) -> Card | None:
    """Recompute one problem's card from its review rows (deleting it if there are none)."""
    scheduler = scheduler or make_scheduler(desired_retention(session))
    reviews = session.execute(
        select(ReviewLog.rating, ReviewLog.reviewed_at)
        .where(ReviewLog.slug == slug)
        .order_by(ReviewLog.reviewed_at, ReviewLog.id)
    ).all()
    card = session.get(Card, slug)
    if not reviews:
        if card is not None:
            session.delete(card)
        return None

    result = replay(scheduler, [(r.rating, r.reviewed_at) for r in reviews])
    if card is None:
        card = Card(slug=slug, suspended=False)
        session.add(card)
    card.due = utc_naive(result.card.due)
    card.stability = result.card.stability
    card.difficulty = result.card.difficulty
    card.state = int(result.card.state)
    card.last_review = utc_naive(result.card.last_review) if result.card.last_review else None
    card.reps = result.reps
    card.lapses = result.lapses
    return card


def rebuild_all(session: Session) -> int:
    """Rebuild every card, e.g. after changing desired retention."""
    scheduler = make_scheduler(desired_retention(session))
    slugs = set(session.scalars(select(ReviewLog.slug).distinct()))
    slugs |= set(session.scalars(select(Card.slug)))
    for slug in slugs:
        rebuild_card(session, slug, scheduler)
    return len(slugs)


def change_target(session: Session, mode: str, **kwargs: Any) -> Target:
    """`settings_store.set_target`, rebuilding cards if retention changed."""
    if set_target(session, mode, **kwargs):
        rebuild_all(session)
    return get_target(session)


def current_target(session: Session, today: date) -> Target:
    """The daily target, first ending Interview prep if its end date has passed."""
    if revert_expired_interview(session, today):
        rebuild_all(session)
    return get_target(session)


# --- Scheduling solves -------------------------------------------------------------------


def schedule_new_solves(session: Session, now: datetime | None = None) -> int:
    """Give every solve without a review row its default rating, and rebuild those cards.

    Called after each sync. Idempotent: solves already in review_log are left alone.
    """
    now = now or utc_now()
    study_mode_on = get_study_mode(session).active(now.date())
    unscheduled = session.scalars(
        select(Solve)
        .outerjoin(ReviewLog, ReviewLog.solve_id == Solve.id)
        .where(ReviewLog.id.is_(None))
        .order_by(Solve.accepted_at)
    ).all()

    for solve in unscheduled:
        if solve.rating is None:
            if (
                solve.rating_source == INFERRED
                and study_mode_on
                and _is_first_solve(session, solve)
            ):
                solve.rating = int(Rating.Again)
                solve.used_solution = True
            else:
                solve.rating = int(infer_rating(solve.wrong_before_ac))
        session.add(
            ReviewLog(
                slug=solve.slug,
                solve_id=solve.id,
                rating=solve.rating,
                reviewed_at=solve.accepted_at,
            )
        )
    session.flush()

    scheduler = make_scheduler(desired_retention(session))
    for slug in {solve.slug for solve in unscheduled}:
        rebuild_card(session, slug, scheduler)
    return len(unscheduled)


def _is_first_solve(session: Session, solve: Solve) -> bool:
    earlier = session.scalar(
        select(func.count())
        .select_from(Solve)
        .where(Solve.slug == solve.slug, Solve.accepted_at < solve.accepted_at)
    )
    return earlier == 0


def set_rating(session: Session, solve_id: int, choice: Choice) -> Card | None:
    """The user rates (or re-rates) a solve."""
    solve = session.get(Solve, solve_id)
    if solve is None:
        raise LookupError(f"No solve with id {solve_id}")
    solve.rating = int(RATING_OF[choice])
    solve.used_solution = choice is Choice.SAW_SOLUTION
    solve.rating_source = USER

    row = session.scalar(select(ReviewLog).where(ReviewLog.solve_id == solve_id))
    if row is None:
        row = ReviewLog(slug=solve.slug, solve_id=solve.id, reviewed_at=solve.accepted_at)
        session.add(row)
    row.rating = solve.rating
    session.flush()
    return rebuild_card(session, solve.slug)


def confirm_defaults(session: Session, solve_ids: list[int]) -> int:
    """Accept the pre-selected rating of pending solves ("Confirm all"). Others are skipped."""
    confirmed = 0
    for solve_id in solve_ids:
        solve = session.get(Solve, solve_id)
        if solve is None or solve.rating_source != INFERRED:
            continue
        default = choice_of(solve) or Choice(infer_rating(solve.wrong_before_ac).name.lower())
        set_rating(session, solve_id, default)
        confirmed += 1
    return confirmed


def mark_reviewed(
    session: Session, slug: str, choice: Choice, at: datetime | None = None
) -> Card | None:
    """A manual review, for a re-solve LeetCode won't show us (e.g. done elsewhere)."""
    if session.get(Card, slug) is None:
        raise LookupError(f"'{slug}' has no card; only solved problems can be reviewed")
    session.add(
        ReviewLog(slug=slug, rating=int(RATING_OF[choice]), reviewed_at=utc_naive(at or utc_now()))
    )
    session.flush()
    return rebuild_card(session, slug)


# --- Queries for the UI ----------------------------------------------------------------------


def recall(card: Card, now: datetime | None = None, scheduler: Scheduler | None = None) -> float:
    """Current probability of recalling the problem (FSRS retrievability), 0-1."""
    scheduler = scheduler or make_scheduler()
    fsrs_card = fsrs.Card(
        state=State(card.state),
        stability=card.stability,
        difficulty=card.difficulty,
        due=as_utc(card.due),
        last_review=as_utc(card.last_review) if card.last_review else None,
    )
    return scheduler.get_card_retrievability(fsrs_card, now or utc_now())


# Also the mastery formula's difficulty weights (design doc), so queue and skills agree.
DIFFICULTY_WEIGHT = {"Easy": 1.0, "Medium": 1.5, "Hard": 2.0}


def priority(recall_probability: float, difficulty: str) -> float:
    """Queue priority: how forgotten, weighted by difficulty. Higher comes first.

    Harder problems win among equally forgotten cards, but a nearly forgotten Easy
    still beats a well-remembered Medium.
    """
    return (1.0 - recall_probability) * DIFFICULTY_WEIGHT.get(difficulty, 1.0)


@dataclass(frozen=True)
class DueReview:
    slug: str
    title: str
    difficulty: str
    due: datetime
    recall: float
    priority: float
    frontend_id: str | None = None  # LeetCode's problem number
    last_review: datetime | None = None  # last solved (re-solve or manual review)


def due_reviews(
    session: Session, now: datetime | None = None, limit: int | None = None
) -> list[DueReview]:
    """Cards due now (not suspended), highest priority first."""
    now = now or utc_now()
    scheduler = make_scheduler(desired_retention(session))
    rows = session.execute(
        select(Card, Problem.title, Problem.difficulty, Problem.frontend_id)
        .join(Problem, Problem.slug == Card.slug)
        .where(Card.suspended.is_(False), Card.due <= utc_naive(now))
    ).all()
    items = []
    for card, title, difficulty, frontend_id in rows:
        r = recall(card, now, scheduler)
        items.append(
            DueReview(
                slug=card.slug,
                title=title,
                difficulty=difficulty,
                due=as_utc(card.due),
                recall=r,
                priority=priority(r, difficulty),
                frontend_id=frontend_id,
                last_review=as_utc(card.last_review) if card.last_review else None,
            )
        )
    items.sort(key=lambda item: (-item.priority, item.slug))
    return items[:limit] if limit is not None else items


def reviews_done_today(session: Session, day_start: datetime) -> int:
    """Problems reviewed since `day_start` that already had a card (re-solves, manual reviews).

    First solves don't count: the daily target counts reviews only.
    """
    earlier = aliased(ReviewLog)
    had_card_before = (
        select(earlier.id)
        .where(earlier.slug == ReviewLog.slug, earlier.reviewed_at < ReviewLog.reviewed_at)
        .exists()
    )
    return session.scalar(
        select(func.count(ReviewLog.slug.distinct())).where(
            ReviewLog.reviewed_at >= utc_naive(day_start), had_card_before
        )
    )


@dataclass(frozen=True)
class TimelineSubmission:
    id: int
    status: str
    lang: str
    runtime_ms: int | None
    at: datetime


@dataclass(frozen=True)
class TimelineEntry:
    """One event in a problem's history, newest first in `problem_timeline`."""

    kind: Literal["solve", "review", "attempts"]  # attempts = failures since the last solve
    at: datetime
    solve_id: int | None = None
    wrong_before_ac: int | None = None
    choice: Choice | None = None
    rating_source: str | None = None  # solves only
    # Solves: the attempts leading up to the accept, the accept, and any merged follow-up
    # accepts. Attempts: the failures since the last solve.
    submissions: tuple[TimelineSubmission, ...] = ()


def problem_timeline(session: Session, slug: str) -> list[TimelineEntry]:
    solves = session.scalars(
        select(Solve).where(Solve.slug == slug).order_by(Solve.accepted_at)
    ).all()
    submissions = session.scalars(
        select(Submission).where(Submission.slug == slug).order_by(Submission.timestamp)
    ).all()
    accepted = [s.accepted_at for s in solves]

    # Each submission belongs to the solve it led up to, or (within the merge window)
    # the solve it followed; failures after the last solve are open attempts.
    groups: list[list[TimelineSubmission]] = [[] for _ in solves]
    trailing: list[TimelineSubmission] = []
    for sub in submissions:
        item = TimelineSubmission(
            sub.submission_id, sub.status, sub.lang, sub.runtime_ms, as_utc(sub.timestamp)
        )
        j = bisect_left(accepted, sub.timestamp)
        if j > 0 and sub.timestamp < accepted[j - 1] + MERGE_WINDOW:
            groups[j - 1].append(item)
        elif j < len(solves):
            groups[j].append(item)
        else:
            trailing.append(item)

    entries = [
        TimelineEntry(
            kind="solve",
            at=as_utc(solve.accepted_at),
            solve_id=solve.id,
            wrong_before_ac=solve.wrong_before_ac,
            choice=choice_of(solve),
            rating_source=solve.rating_source,
            submissions=tuple(group),
        )
        for solve, group in zip(solves, groups, strict=True)
    ]
    manual = session.scalars(
        select(ReviewLog).where(ReviewLog.slug == slug, ReviewLog.solve_id.is_(None))
    ).all()
    entries += [
        TimelineEntry(kind="review", at=as_utc(row.reviewed_at), choice=_choice_of_rating(row))
        for row in manual
    ]
    if trailing:
        entries.append(
            TimelineEntry(kind="attempts", at=trailing[-1].at, submissions=tuple(trailing))
        )
    entries.sort(key=lambda e: e.at, reverse=True)
    return entries


def _choice_of_rating(row: ReviewLog) -> Choice:
    return Choice(Rating(row.rating).name.lower())


@dataclass(frozen=True)
class PendingRating:
    solve_id: int
    slug: str
    title: str
    difficulty: str
    accepted_at: datetime
    wrong_before_ac: int
    default: Choice | None  # pre-selected in "Rate your new solves"
    frontend_id: str | None = None


def pending_ratings(session: Session) -> list[PendingRating]:
    """Solves found by recent syncs, awaiting the user's rating (newest first)."""
    rows = session.execute(
        select(Solve, Problem.title, Problem.difficulty, Problem.frontend_id)
        .join(Problem, Problem.slug == Solve.slug)
        .where(Solve.rating_source == INFERRED)
        .order_by(Solve.accepted_at.desc())
    ).all()
    return [
        PendingRating(
            solve_id=solve.id,
            slug=solve.slug,
            title=title,
            difficulty=difficulty,
            accepted_at=as_utc(solve.accepted_at),
            wrong_before_ac=solve.wrong_before_ac,
            default=choice_of(solve),
            frontend_id=frontend_id,
        )
        for solve, title, difficulty, frontend_id in rows
    ]
