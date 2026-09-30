"""Engine pieces behind the Today screen: priority, done-today, timeline, target modes."""

from datetime import timedelta

import pytest

from app.db.models import Card, Setting
from app.engines.reviews import (
    Choice,
    change_target,
    confirm_defaults,
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
# Casual and Steady are fixed presets; Interview is the one adjustable mode.


def test_default_target_is_steady(session) -> None:
    target = get_target(session)
    assert (target.mode, target.daily_target, target.retention) == ("steady", 8, 0.90)


def test_presets_are_fixed(session) -> None:
    assert (change_target(session, "casual").daily_target, get_target(session).retention) == (
        5,
        0.90,
    )
    assert change_target(session, "steady").daily_target == 8
    for kwargs in ({"daily_target": 4}, {"retention": 0.85}):
        with pytest.raises(ValueError, match="fixed values"):
            change_target(session, "casual", **kwargs)


def test_interview_defaults_raise_retention_and_rebuild_cards(session) -> None:
    add_problem(session, "p")
    add_solve(session, "p", NOW - timedelta(days=30))
    schedule_new_solves(session, NOW)
    steady_due = session.get(Card, "p").due

    target = change_target(session, "interview")

    assert (target.mode, target.daily_target, target.retention) == ("interview", 15, 0.95)
    assert session.get(Card, "p").due < steady_due  # higher retention: sooner reviews


def test_interview_takes_number_and_retention_and_remembers_them(session) -> None:
    target = change_target(session, "interview", daily_target=12, retention=0.85)
    assert (target.daily_target, target.retention) == (12, 0.85)

    change_target(session, "steady")
    steady = get_target(session)
    assert (steady.daily_target, steady.retention) == (8, 0.90)
    assert (steady.interview_target, steady.interview_retention) == (12, 0.85)  # for the form

    back = change_target(session, "interview")
    assert (back.daily_target, back.retention) == (12, 0.85)


def test_interview_partial_update_keeps_the_other_value(session) -> None:
    change_target(session, "interview", daily_target=12, retention=0.85)
    target = change_target(session, "interview", daily_target=20)
    assert (target.daily_target, target.retention) == (20, 0.85)


def _put(session, key: str, value) -> None:
    session.merge(Setting(key=key, value=value))
    session.flush()


def test_legacy_custom_mode_reads_as_interview(session) -> None:
    _put(session, "target_mode", "custom")
    _put(session, "daily_target", 12)
    _put(session, "desired_retention", 0.85)

    target = get_target(session)

    assert (target.mode, target.daily_target, target.retention) == ("interview", 12, 0.85)
    assert (target.interview_target, target.interview_retention) == (12, 0.85)


def test_legacy_end_date_keys_are_removed_on_save(session) -> None:
    _put(session, "target_mode", "interview")
    _put(session, "interview_end_date", "2026-10-10")
    _put(session, "previous_mode", "custom")

    change_target(session, "steady")

    assert session.get(Setting, "interview_end_date") is None
    assert session.get(Setting, "previous_mode") is None


@pytest.mark.parametrize("kwargs", [{"daily_target": 0}, {"daily_target": 101}, {"retention": 0.5}])
def test_invalid_interview_values(session, kwargs) -> None:
    with pytest.raises(ValueError):
        change_target(session, "interview", **kwargs)


@pytest.mark.parametrize("mode", ["hardcore", "custom"])
def test_unknown_mode(session, mode) -> None:
    with pytest.raises(ValueError):
        change_target(session, mode)
