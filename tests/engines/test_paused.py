"""Paused problems (plan 009): out of the due queue until resumed or solved again."""

from datetime import timedelta

from app.db.models import Card
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
from tests.factories import NOW, add_problem, add_solve


def seed_due(session, *slugs: str) -> None:
    """Problems solved long ago (so they're due), as backfill history."""
    for i, slug in enumerate(slugs):
        add_problem(session, slug)
        add_solve(session, slug, NOW - timedelta(days=400 + i), source=HISTORY)
    schedule_new_solves(session, NOW)


def due_slugs(session) -> set[str]:
    return {item.slug for item in due_reviews(session, NOW)}


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
    add_problem(session, "attempted-only")  # no card: can't be paused

    assert pause(session, ["a", "a", "attempted-only", "nope"]) == 1
    assert pause(session, ["a"]) == 0  # already paused
    assert resume(session, ["nope"]) == 0
    assert pause(session, []) == 0


def test_paused_items_carry_review_fields(session) -> None:
    seed_due(session, "a")
    pause(session, ["a"])

    [item] = paused_problems(session, NOW)

    assert 0 < item.recall < 1
    assert item.last_review is not None
    assert item.difficulty == "Medium"


def test_rebuild_keeps_paused(session) -> None:
    seed_due(session, "a")
    pause(session, ["a"])
    rebuild_card(session, "a")
    assert session.get(Card, "a").suspended is True


def test_new_solve_resumes(session) -> None:
    seed_due(session, "a")
    pause(session, ["a"])
    add_solve(session, "a", NOW - timedelta(hours=1))  # a re-solve found by a later sync

    schedule_new_solves(session, NOW)

    card = session.get(Card, "a")
    assert card.suspended is False
    assert "a" not in due_slugs(session)  # rescheduled from the fresh solve, not overdue


def test_history_solve_does_not_resume(session) -> None:
    seed_due(session, "a")
    pause(session, ["a"])
    add_solve(session, "a", NOW - timedelta(days=100), source=HISTORY)

    schedule_new_solves(session, NOW)

    assert session.get(Card, "a").suspended is True


def test_mark_reviewed_resumes(session) -> None:
    seed_due(session, "a")
    pause(session, ["a"])

    mark_reviewed(session, "a", Choice.GOOD, at=NOW)

    assert session.get(Card, "a").suspended is False
