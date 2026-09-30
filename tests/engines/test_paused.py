"""Paused problems (plan 009): out of Today until resumed or solved (again)."""

from datetime import timedelta

from app.db.models import Problem
from app.engines.reviews import (
    HISTORY,
    Choice,
    due_reviews,
    mark_reviewed,
    pause,
    paused_problems,
    rebuild_card,
    resume,
    resume_all,
    schedule_new_solves,
)
from tests.factories import NOW, add_problem, add_solve, add_submission


def seed_due(session, *slugs: str) -> None:
    """Problems solved long ago (so they're due), as backfill history."""
    for i, slug in enumerate(slugs):
        add_problem(session, slug)
        add_solve(session, slug, NOW - timedelta(days=400 + i), source=HISTORY)
    schedule_new_solves(session, NOW)


def seed_attempted(session, slug: str, days_ago: float = 3) -> None:
    add_problem(session, slug, "Hard")
    session.get(Problem, slug).question_status = "ATTEMPTED"
    add_submission(session, slug, NOW - timedelta(days=days_ago), "Time Limit Exceeded")


def due_slugs(session) -> set[str]:
    return {item.slug for item in due_reviews(session, NOW)}


def is_paused(session, slug: str) -> bool:
    return session.get(Problem, slug).paused


def test_pause_removes_from_due_and_resume_brings_back(session) -> None:
    seed_due(session, "a", "b", "c")

    assert pause(session, ["a", "b"]) == 2
    assert due_slugs(session) == {"c"}
    assert [p.slug for p in paused_problems(session, NOW)] == ["a", "b"]  # newest solve first

    assert resume(session, ["a"]) == 1
    assert due_slugs(session) == {"a", "c"}
    assert resume_all(session) == 1
    assert due_slugs(session) == {"a", "b", "c"}
    assert paused_problems(session, NOW) == []


def test_counts_only_actual_changes_and_ignores_unknown(session) -> None:
    seed_due(session, "a")

    assert pause(session, ["a", "a", "nope"]) == 1
    assert pause(session, ["a"]) == 0  # already paused
    assert resume(session, ["nope"]) == 0
    assert pause(session, []) == 0


def test_solved_paused_items_carry_recall(session) -> None:
    seed_due(session, "a")
    pause(session, ["a"])

    [item] = paused_problems(session, NOW)

    assert item.solved
    assert 0 < item.recall < 1
    assert item.last_review is not None
    assert (item.last_status, item.last_attempt_at) == (None, None)


def test_attempted_problems_can_be_paused(session) -> None:
    seed_due(session, "solved")
    seed_attempted(session, "attempted", days_ago=1)

    assert pause(session, ["attempted", "solved"]) == 2

    attempted, solved = paused_problems(session, NOW)  # most recent activity first
    assert (attempted.slug, attempted.solved, attempted.recall) == ("attempted", False, None)
    assert attempted.last_status == "Time Limit Exceeded"
    assert attempted.last_attempt_at is not None
    assert solved.slug == "solved"


def test_rebuild_keeps_paused(session) -> None:
    seed_due(session, "a")
    pause(session, ["a"])
    rebuild_card(session, "a")
    assert is_paused(session, "a")


def test_new_solve_resumes(session) -> None:
    seed_due(session, "a")
    pause(session, ["a"])
    add_solve(session, "a", NOW - timedelta(hours=1))  # a re-solve found by a later sync

    schedule_new_solves(session, NOW)

    assert not is_paused(session, "a")
    assert "a" not in due_slugs(session)  # rescheduled from the fresh solve, not overdue


def test_first_solve_resumes_a_paused_attempted_problem(session) -> None:
    seed_attempted(session, "attempted")
    pause(session, ["attempted"])
    add_solve(session, "attempted", NOW - timedelta(hours=1))

    schedule_new_solves(session, NOW)

    assert not is_paused(session, "attempted")


def test_history_solve_does_not_resume(session) -> None:
    seed_due(session, "a")
    pause(session, ["a"])
    add_solve(session, "a", NOW - timedelta(days=100), source=HISTORY)

    schedule_new_solves(session, NOW)

    assert is_paused(session, "a")


def test_mark_reviewed_resumes(session) -> None:
    seed_due(session, "a")
    pause(session, ["a"])

    mark_reviewed(session, "a", Choice.GOOD, at=NOW)

    assert not is_paused(session, "a")
