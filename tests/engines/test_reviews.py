from datetime import timedelta

import fsrs
import pytest
from fsrs import Rating
from sqlalchemy import func, select

from app.db.models import Card, ReviewLog, Solve
from app.engines.reviews import (
    HISTORY,
    USER,
    Choice,
    due_reviews,
    infer_rating,
    make_scheduler,
    mark_reviewed,
    pending_ratings,
    replay,
    schedule_new_solves,
    set_rating,
)
from app.settings_store import set_study_mode
from app.timeutil import as_utc, utc_naive
from tests.factories import NOW, add_problem, add_solve, at

# --- Ratings and replay ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("wrong", "rating"),
    [(0, Rating.Good), (1, Rating.Hard), (2, Rating.Hard), (3, Rating.Again), (7, Rating.Again)],
)
def test_infer_rating(wrong: int, rating: Rating) -> None:
    assert infer_rating(wrong) == rating


def test_replay_matches_fsrs_and_is_deterministic() -> None:
    reviews = [(3, at(0)), (2, at(3)), (1, at(20)), (3, at(25))]
    scheduler = make_scheduler()

    card = fsrs.Card()
    for rating, when in reviews:
        card, _ = scheduler.review_card(card, Rating(rating), when)

    first, second = replay(scheduler, reviews), replay(make_scheduler(), reviews)
    assert first.card.due == card.due == second.card.due
    assert first.card.stability == card.stability
    assert (first.reps, first.lapses) == (4, 1)  # the Again at day 20 was a lapse


def test_intervals_are_whole_days_not_learning_steps() -> None:
    scheduler = make_scheduler()
    for rating in Rating:
        result = replay(scheduler, [(rating, at(0))])
        assert result.card.due - at(0) >= timedelta(days=1)
    lapsed = replay(scheduler, [(3, at(0)), (1, at(10))])
    assert lapsed.card.due - at(10) >= timedelta(days=1)


# --- Scheduling new solves ----------------------------------------------------------------


def test_history_solves_are_inferred_silently(session) -> None:
    add_problem(session, "two-sum")
    add_solve(session, "two-sum", at(0), wrong=1, source=HISTORY)
    add_solve(session, "two-sum", at(30), wrong=0, source=HISTORY)

    assert schedule_new_solves(session, NOW) == 2

    ratings = session.scalars(select(Solve.rating).order_by(Solve.accepted_at)).all()
    assert ratings == [Rating.Hard, Rating.Good]
    assert pending_ratings(session) == []
    card = session.get(Card, "two-sum")
    assert card.reps == 2 and card.last_review == utc_naive(at(30))


def test_scheduling_is_idempotent(session) -> None:
    add_problem(session, "two-sum")
    add_solve(session, "two-sum", at(0), source=HISTORY)
    schedule_new_solves(session, NOW)

    assert schedule_new_solves(session, NOW) == 0
    assert session.scalar(select(func.count()).select_from(ReviewLog)) == 1


def test_inferred_solves_await_rating_with_default(session) -> None:
    add_problem(session, "two-sum")
    solve = add_solve(session, "two-sum", at(0), wrong=2)

    schedule_new_solves(session, NOW)

    [pending] = pending_ratings(session)
    assert (pending.solve_id, pending.default) == (solve.id, Choice.HARD)
    assert session.get(Card, "two-sum") is not None  # scheduled right away


def test_study_mode_defaults_first_solves_to_saw_solution(session) -> None:
    set_study_mode(session, True)
    add_problem(session, "new-problem")
    add_problem(session, "old-problem")
    add_problem(session, "history-problem")
    first = add_solve(session, "new-problem", at(0), wrong=0)
    add_solve(session, "old-problem", at(0), source=HISTORY)
    resolve = add_solve(session, "old-problem", at(40), wrong=0)
    history = add_solve(session, "history-problem", at(0), source=HISTORY)

    schedule_new_solves(session, NOW)

    assert (first.rating, first.used_solution) == (Rating.Again, True)
    assert (resolve.rating, resolve.used_solution) == (Rating.Good, False)  # re-solve: inferred
    assert (history.rating, history.used_solution) == (Rating.Good, False)
    defaults = {p.slug: p.default for p in pending_ratings(session)}
    assert defaults == {"new-problem": Choice.SAW_SOLUTION, "old-problem": Choice.GOOD}


def test_study_mode_off_again_rates_normally(session) -> None:
    set_study_mode(session, True)
    set_study_mode(session, False)
    add_problem(session, "two-sum")
    solve = add_solve(session, "two-sum", at(0))

    schedule_new_solves(session, NOW)

    assert (solve.rating, solve.used_solution) == (Rating.Good, False)


# --- User actions ---------------------------------------------------------------------------


def test_set_rating_rebuilds_only_that_card(session) -> None:
    add_problem(session, "two-sum")
    add_problem(session, "other")
    solve = add_solve(session, "two-sum", at(0))
    add_solve(session, "other", at(0))
    schedule_new_solves(session, NOW)
    good_due = session.get(Card, "two-sum").due
    other_due = session.get(Card, "other").due

    set_rating(session, solve.id, Choice.AGAIN)

    assert session.get(Card, "two-sum").due < good_due
    assert session.get(Card, "other").due == other_due
    assert solve.rating_source == USER
    assert [p.slug for p in pending_ratings(session)] == ["other"]

    set_rating(session, solve.id, Choice.GOOD)
    assert session.get(Card, "two-sum").due == good_due  # rating back restores the schedule


def test_saw_solution_is_again_but_flagged(session) -> None:
    add_problem(session, "two-sum")
    solve = add_solve(session, "two-sum", at(0))
    schedule_new_solves(session, NOW)

    set_rating(session, solve.id, Choice.SAW_SOLUTION)

    assert (solve.rating, solve.used_solution) == (Rating.Again, True)
    row = session.scalar(select(ReviewLog).where(ReviewLog.solve_id == solve.id))
    assert row.rating == Rating.Again


def test_mark_reviewed_adds_manual_review(session) -> None:
    add_problem(session, "two-sum")
    add_solve(session, "two-sum", at(0))
    schedule_new_solves(session, NOW)
    before = session.get(Card, "two-sum").due

    card = mark_reviewed(session, "two-sum", Choice.GOOD, at=at(10))

    assert card.reps == 2 and card.due > before
    manual = session.scalar(select(ReviewLog).where(ReviewLog.solve_id.is_(None)))
    assert manual.slug == "two-sum"


def test_mark_reviewed_requires_a_card(session) -> None:
    add_problem(session, "never-solved")
    with pytest.raises(LookupError):
        mark_reviewed(session, "never-solved", Choice.GOOD)


# --- Due queue ------------------------------------------------------------------------------


def test_due_reviews_excludes_not_due_and_suspended(session) -> None:
    for slug in ("fresh", "old", "older", "not-due", "suspended"):
        add_problem(session, slug)
    add_solve(session, "fresh", NOW - timedelta(days=5))
    add_solve(session, "old", NOW - timedelta(days=60))
    add_solve(session, "older", NOW - timedelta(days=200))
    add_solve(session, "not-due", NOW - timedelta(hours=2))
    add_solve(session, "suspended", NOW - timedelta(days=90))
    schedule_new_solves(session, NOW)
    session.get(Card, "suspended").suspended = True

    items = due_reviews(session, NOW)

    # All Medium, so priority order is lowest recall first.
    assert [i.slug for i in items] == ["older", "old", "fresh"]
    assert items[0].recall < items[1].recall < items[2].recall
    assert items[0].priority > items[1].priority > items[2].priority
    assert as_utc(session.get(Card, "not-due").due) > NOW
    assert [i.slug for i in due_reviews(session, NOW, limit=1)] == ["older"]
