"""Engine pieces behind the Today screen: priority, done-today, timeline, target modes."""

from datetime import date, timedelta

import pytest

from app.db.models import Card
from app.engines.reviews import (
    Choice,
    change_target,
    confirm_defaults,
    current_target,
    due_reviews,
    mark_reviewed,
    pending_ratings,
    priority,
    problem_timeline,
    reviews_done_today,
    schedule_new_solves,
)
from app.settings_store import get_target
from tests.factories import NOW, add_problem, add_solve, add_submission

# --- Priority ------------------------------------------------------------------------------


def test_harder_first_at_equal_recall() -> None:
    assert priority(0.4, "Hard") > priority(0.4, "Medium") > priority(0.4, "Easy")


def test_forgotten_easy_beats_well_remembered_medium() -> None:
    assert priority(0.3, "Easy") > priority(0.9, "Medium")


def test_due_queue_uses_priority(session) -> None:
    # Same solve date, so same recall: difficulty decides.
    for slug, difficulty in [("easy", "Easy"), ("medium", "Medium"), ("hard", "Hard")]:
        add_problem(session, slug, difficulty)
        add_solve(session, slug, NOW - timedelta(days=400))
    # A barely due Medium ranks below a long-forgotten Easy.
    add_problem(session, "fresh-medium", "Medium")
    add_solve(session, "fresh-medium", NOW - timedelta(days=3))
    schedule_new_solves(session, NOW)

    slugs = [i.slug for i in due_reviews(session, NOW)]
    assert slugs == ["hard", "medium", "easy", "fresh-medium"]


# --- Done today -----------------------------------------------------------------------------


def test_done_today_counts_reviews_not_first_solves(session) -> None:
    day_start = NOW - timedelta(hours=5)
    for slug in ("reviewed", "new-today", "manual"):
        add_problem(session, slug)
    add_solve(session, "reviewed", NOW - timedelta(days=30))
    add_solve(session, "reviewed", NOW - timedelta(hours=2))  # re-solve today: counts
    add_solve(session, "new-today", NOW - timedelta(hours=1))  # first solve: excluded
    add_solve(session, "manual", NOW - timedelta(days=30))
    schedule_new_solves(session, NOW)
    mark_reviewed(session, "manual", Choice.GOOD, at=NOW - timedelta(hours=1))  # counts

    assert reviews_done_today(session, day_start) == 2


# --- Timeline -------------------------------------------------------------------------------


def test_timeline_groups_submissions_into_solves(session) -> None:
    add_problem(session, "p")
    t = NOW - timedelta(days=100)
    add_submission(session, "p", t)  # lead-up to solve 1
    first = add_solve(session, "p", t + timedelta(minutes=5), wrong=1)
    add_submission(session, "p", t + timedelta(minutes=10), "Accepted")  # merged follow-up
    add_submission(session, "p", t + timedelta(days=10))  # lead-up to solve 2
    second = add_solve(session, "p", t + timedelta(days=10, minutes=5), wrong=1)
    add_submission(session, "p", t + timedelta(days=20), "Time Limit Exceeded")  # open attempt
    schedule_new_solves(session, NOW)
    mark_reviewed(session, "p", Choice.HARD, at=t + timedelta(days=15))

    timeline = problem_timeline(session, "p")

    assert [e.kind for e in timeline] == ["attempts", "review", "solve", "solve"]
    attempts, review, solve2, solve1 = timeline
    assert [s.status for s in attempts.submissions] == ["Time Limit Exceeded"]
    assert review.choice is Choice.HARD
    assert (solve2.solve_id, len(solve2.submissions)) == (second.id, 2)
    assert (solve1.solve_id, len(solve1.submissions)) == (first.id, 3)
    assert solve1.choice is Choice.HARD
    assert solve1.rating_source == "inferred"


# --- Confirm all ----------------------------------------------------------------------------


def test_confirm_defaults_accepts_pending_only(session) -> None:
    add_problem(session, "a")
    add_problem(session, "b")
    pending = add_solve(session, "a", NOW - timedelta(days=1), wrong=1)
    history = add_solve(session, "b", NOW - timedelta(days=1), source="history")
    schedule_new_solves(session, NOW)

    assert confirm_defaults(session, [pending.id, history.id, 99999]) == 1
    assert pending_ratings(session) == []
    assert (pending.rating_source, pending.rating) == ("user", 2)
    assert history.rating_source == "history"


# --- Target modes ---------------------------------------------------------------------------


def test_default_target_is_steady(session) -> None:
    target = get_target(session)
    assert (target.mode, target.daily_target, target.retention) == ("steady", 8, 0.90)


def test_mode_sets_default_number_and_number_is_adjustable(session) -> None:
    assert change_target(session, "casual").daily_target == 5
    assert change_target(session, "casual", daily_target=4).daily_target == 4
    assert change_target(session, "casual").daily_target == 4  # same mode keeps the number
    assert change_target(session, "steady").daily_target == 8


def test_interview_prep_raises_retention_and_rebuilds_cards(session) -> None:
    add_problem(session, "p")
    add_solve(session, "p", NOW - timedelta(days=30))
    schedule_new_solves(session, NOW)
    steady_due = session.get(Card, "p").due

    target = change_target(session, "interview", end_date=date(2026, 10, 15))

    assert (target.retention, target.daily_target, target.previous_mode) == (0.95, 15, "steady")
    assert session.get(Card, "p").due < steady_due  # higher retention: sooner reviews


def test_interview_prep_reverts_after_end_date(session) -> None:
    change_target(session, "casual")
    change_target(session, "interview", end_date=date(2026, 10, 15))

    assert current_target(session, date(2026, 10, 15)).mode == "interview"
    after = current_target(session, date(2026, 10, 16))
    assert (after.mode, after.retention, after.interview_end_date) == ("casual", 0.90, None)


def test_custom_mode_takes_retention(session) -> None:
    target = change_target(session, "custom", daily_target=12, retention=0.85)
    assert (target.daily_target, target.retention) == (12, 0.85)


@pytest.mark.parametrize("kwargs", [{"daily_target": 0}, {"daily_target": 101}, {"retention": 0.5}])
def test_invalid_target_values(session, kwargs) -> None:
    with pytest.raises(ValueError):
        change_target(session, "custom", **kwargs)


def test_unknown_mode(session) -> None:
    with pytest.raises(ValueError):
        change_target(session, "hardcore")
