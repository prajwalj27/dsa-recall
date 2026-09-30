"""Spaced repetition over solves with FSRS.

`review_log` is the source of truth: one row per solve plus manual "Mark reviewed" rows.
`cards` is a cache: each problem's card is rebuilt by replaying its review rows in order,
so changing any rating is just "update one row, rebuild one card".

The scheduler has no learning steps (minute-level steps suit flashcards, not re-solving a
problem) and no fuzzing (so replays are deterministic).
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

import fsrs
from fsrs import Rating, Scheduler, State
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Card, Problem, ReviewLog, Solve
from app.settings_store import DEFAULT_RETENTION, desired_retention, get_study_mode
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


@dataclass(frozen=True)
class DueReview:
    slug: str
    title: str
    difficulty: str
    due: datetime
    recall: float
    days_overdue: int


def due_reviews(
    session: Session, now: datetime | None = None, limit: int | None = None
) -> list[DueReview]:
    """Cards due now (not suspended), lowest recall first."""
    now = now or utc_now()
    scheduler = make_scheduler(desired_retention(session))
    rows = session.execute(
        select(Card, Problem.title, Problem.difficulty)
        .join(Problem, Problem.slug == Card.slug)
        .where(Card.suspended.is_(False), Card.due <= utc_naive(now))
    ).all()
    items = [
        DueReview(
            slug=card.slug,
            title=title,
            difficulty=difficulty,
            due=as_utc(card.due),
            recall=recall(card, now, scheduler),
            days_overdue=(now - as_utc(card.due)).days,
        )
        for card, title, difficulty in rows
    ]
    items.sort(key=lambda item: (item.recall, item.slug))
    return items[:limit] if limit is not None else items


@dataclass(frozen=True)
class PendingRating:
    solve_id: int
    slug: str
    title: str
    difficulty: str
    accepted_at: datetime
    wrong_before_ac: int
    default: Choice | None  # pre-selected in "Rate your new solves"


def pending_ratings(session: Session) -> list[PendingRating]:
    """Solves found by recent syncs, awaiting the user's rating (newest first)."""
    rows = session.execute(
        select(Solve, Problem.title, Problem.difficulty)
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
        )
        for solve, title, difficulty in rows
    ]
