"""Solved page rows (plan 011)."""

from datetime import timedelta

from app.db.models import Problem
from app.engines.reviews import HISTORY, pause, schedule_new_solves, solved_list
from tests.factories import NOW, add_problem, add_solve, add_submission


def rows_by_slug(session) -> dict:
    return {row.slug: row for row in solved_list(session, NOW)}


def test_status_and_fields_for_each_kind(session) -> None:
    add_problem(session, "due", "Hard")
    add_solve(session, "due", NOW - timedelta(days=400), source=HISTORY)
    add_problem(session, "scheduled")
    add_solve(session, "scheduled", NOW - timedelta(days=60), source=HISTORY)
    add_solve(session, "scheduled", NOW - timedelta(hours=3))
    add_problem(session, "paused")
    add_solve(session, "paused", NOW - timedelta(days=200), source=HISTORY)
    add_problem(session, "unsolved", "Easy")
    add_submission(session, "unsolved", NOW - timedelta(days=2), "Wrong Answer")
    add_problem(session, "untouched")  # e.g. a future suggestion: never submitted to
    for slug in ("due", "scheduled", "paused", "unsolved"):
        session.get(Problem, slug).question_status = "SOLVED" if slug != "unsolved" else "ATTEMPTED"
    schedule_new_solves(session, NOW)
    pause(session, ["paused"])

    rows = rows_by_slug(session)

    assert set(rows) == {"due", "scheduled", "paused", "unsolved"}
    assert {slug: r.status for slug, r in rows.items()} == {
        "due": "due",
        "scheduled": "scheduled",
        "paused": "paused",
        "unsolved": "unsolved",
    }
    scheduled = rows["scheduled"]
    assert scheduled.solves == 2
    assert scheduled.next_review > NOW
    assert scheduled.last_solved is not None and 0 < scheduled.recall <= 1
    assert rows["due"].next_review <= NOW
    paused = rows["paused"]
    assert (paused.paused, paused.next_review, paused.solves) == (True, None, 1)
    assert paused.recall is not None  # still known, just not scheduled
    unsolved = rows["unsolved"]
    assert (unsolved.solves, unsolved.next_review, unsolved.recall, unsolved.last_solved) == (
        0,
        None,
        None,
        None,
    )


def test_sorted_by_next_review_with_empties_last(session) -> None:
    for slug, days in (("old", 400), ("mid", 100)):
        add_problem(session, slug)
        add_solve(session, slug, NOW - timedelta(days=days), source=HISTORY)
        session.get(Problem, slug).question_status = "SOLVED"
    add_problem(session, "unsolved")
    session.get(Problem, "unsolved").question_status = "ATTEMPTED"
    schedule_new_solves(session, NOW)

    assert [row.slug for row in solved_list(session, NOW)] == ["old", "mid", "unsolved"]


def test_tags_are_names(session) -> None:
    add_problem(session, "p")
    problem = session.get(Problem, "p")
    problem.question_status = "ATTEMPTED"
    problem.topic_tags = [
        {"name": "Array", "slug": "array"},
        {"name": "Two Pointers", "slug": "two-pointers"},
    ]

    assert rows_by_slug(session)["p"].tags == ("Array", "Two Pointers")
