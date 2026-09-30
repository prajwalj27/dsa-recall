from sqlalchemy import func, select

from app.db.models import Card, Problem, ReviewLog, Solve, Submission
from app.engines.reviews import pause, pending_ratings
from app.leetcode import RateLimitedError
from app.sync.engine import get_state, run_sync
from app.sync.progress import ErrorKind, RunState
from tests.sync.conftest import FakeSub, day


def count(session_factory, model) -> int:
    with session_factory() as s:
        return s.scalar(select(func.count()).select_from(model))


def solves_of(session_factory, slug: str) -> list[tuple[int, int, int]]:
    with session_factory() as s:
        rows = s.scalars(select(Solve).where(Solve.slug == slug).order_by(Solve.accepted_at))
        return [(r.id, r.accepted_submission_id, r.wrong_before_ac) for r in rows]


def test_backfill_stores_everything(session_factory, fake) -> None:
    progress = run_sync(session_factory, fake)

    assert progress.state is RunState.SUCCEEDED
    assert (progress.mode, progress.total, progress.done) == ("backfill", 3, 3)
    assert count(session_factory, Problem) == 3
    assert count(session_factory, Submission) == 8
    assert [(a, w) for _, a, w in solves_of(session_factory, "two-sum")] == [(103, 2), (105, 0)]

    with session_factory() as s:
        with_code = s.scalars(select(Submission.submission_id).where(Submission.code.is_not(None)))
        # solve 103 + its 2 failures, solve 105, walls-and-gates 201; merged 104 has no code
        assert sorted(with_code) == [101, 102, 103, 105, 201]
        assert get_state(s, "backfill_done") is True
        assert get_state(s, "last_sync_at")

        walls = s.get(Problem, "walls-and-gates")
        assert walls.is_paid_only and walls.statement is None

        median = s.get(Problem, "median-of-two-sorted-arrays")
        assert median.question_status == "ATTEMPTED" and median.difficulty == "Hard"
    assert solves_of(session_factory, "median-of-two-sorted-arrays") == []
    assert fake.calls["submission_detail"] == 5
    assert fake.calls["question"] == 3


def test_second_run_is_incremental_and_makes_one_request(session_factory, fake) -> None:
    run_sync(session_factory, fake)
    fake.calls.clear()

    progress = run_sync(session_factory, fake)

    assert progress.state is RunState.SUCCEEDED
    assert progress.mode == "incremental"
    assert progress.done == 0
    assert dict(fake.calls) == {"check_auth": 1, "progress": 1}


def test_incremental_appends_new_solve_and_stops_early(session_factory, fake) -> None:
    run_sync(session_factory, fake)
    before = solves_of(session_factory, "two-sum")
    fake.add("two-sum", FakeSub(106, "Wrong Answer", day(60)))
    fake.add("two-sum", FakeSub(107, "Accepted", day(60.01)))
    fake.calls.clear()

    progress = run_sync(session_factory, fake)

    assert progress.mode == "incremental"
    assert progress.done == 1  # two-sum synced, stopped at walls-and-gates
    assert (progress.new_submissions, progress.new_solves) == (2, 1)
    after = solves_of(session_factory, "two-sum")
    assert after[:2] == before  # existing solves untouched
    assert after[2][1:] == (107, 1)
    assert fake.calls["question"] == 0
    assert fake.calls["submission_detail"] == 2  # 107 and its failure 106


def test_internal_errors_are_stored_but_not_wrong_attempts(session_factory, fake) -> None:
    fake.add("two-sum", FakeSub(106, "Internal Error", day(60)))
    fake.add("two-sum", FakeSub(107, "Wrong Answer", day(60.001)))
    fake.add("two-sum", FakeSub(108, "Accepted", day(60.002)))

    run_sync(session_factory, fake)

    assert solves_of(session_factory, "two-sum")[-1][1:] == (108, 1)
    with session_factory() as s:
        assert s.get(Submission, 106).status == "Internal Error"
        assert s.get(Submission, 106).code is None  # not fetched as a failed attempt


def test_interrupted_backfill_resumes(session_factory, fake) -> None:
    # Order is walls-and-gates (1 detail), then two-sum (details 2..); fail inside two-sum.
    fake.fail_on["submission_detail"] = (3, RateLimitedError("slow down"))

    progress = run_sync(session_factory, fake)

    assert progress.state is RunState.FAILED
    assert progress.error_kind is ErrorKind.RATE_LIMITED
    with session_factory() as s:
        assert s.scalars(select(Problem.slug)).all() == ["walls-and-gates"]
        assert not get_state(s, "backfill_done", False)

    fake.fail_on.clear()
    progress = run_sync(session_factory, fake)

    assert progress.state is RunState.SUCCEEDED
    assert progress.mode == "backfill"
    assert count(session_factory, Problem) == 3
    assert count(session_factory, Solve) == 3
    # walls-and-gates was committed in the first run and not fetched again
    assert fake.questions_requested == [
        "walls-and-gates",
        "two-sum",
        "two-sum",
        "median-of-two-sorted-arrays",
    ]


def test_signed_out_fails_without_writing(session_factory, fake) -> None:
    fake.signed_in = False

    progress = run_sync(session_factory, fake)

    assert progress.state is RunState.FAILED
    assert progress.error_kind is ErrorKind.AUTH_EXPIRED
    assert count(session_factory, Problem) == 0
    with session_factory() as s:
        assert get_state(s, "last_sync_at") is None


def test_full_resync_walks_everything_but_skips_unchanged(session_factory, fake) -> None:
    run_sync(session_factory, fake)
    fake.calls.clear()

    progress = run_sync(session_factory, fake, full=True)

    assert progress.mode == "backfill"
    assert progress.done == 3
    assert fake.calls["submissions"] == 0


# --- Review scheduling hook (plan 004) ---------------------------------------------------


def test_backfill_schedules_history_cards_for_solved_problems(session_factory, fake) -> None:
    progress = run_sync(session_factory, fake)

    assert progress.scheduled == 3
    with session_factory() as s:
        # median-of-two-sorted-arrays is attempted-only: no card
        assert sorted(s.scalars(select(Card.slug))) == ["two-sum", "walls-and-gates"]
        assert s.scalar(select(func.count()).select_from(ReviewLog)) == 3
        assert set(s.scalars(select(Solve.rating_source))) == {"history"}
        assert pending_ratings(s) == []


def test_solves_after_backfill_await_rating(session_factory, fake) -> None:
    run_sync(session_factory, fake)
    fake.add("two-sum", FakeSub(106, "Accepted", day(60)))

    progress = run_sync(session_factory, fake)

    assert progress.scheduled == 1
    with session_factory() as s:
        [pending] = pending_ratings(s)
        assert pending.slug == "two-sum" and pending.default == "good"
        assert s.get(Card, "two-sum").reps == 3


def test_solves_committed_before_a_failure_still_get_cards(session_factory, fake) -> None:
    fake.fail_on["submission_detail"] = (3, RateLimitedError("slow down"))

    progress = run_sync(session_factory, fake)

    assert progress.state is RunState.FAILED
    assert progress.scheduled == 1
    with session_factory() as s:
        assert s.scalars(select(Card.slug)).all() == ["walls-and-gates"]


def test_solving_a_paused_problem_again_resumes_it(session_factory, fake) -> None:
    run_sync(session_factory, fake)
    with session_factory() as s, s.begin():
        assert pause(s, ["two-sum"]) == 1
    fake.add("two-sum", FakeSub(106, "Accepted", day(60)))

    run_sync(session_factory, fake)

    with session_factory() as s:
        assert s.get(Problem, "two-sum").paused is False
        assert [p.slug for p in pending_ratings(s)] == ["two-sum"]


def test_paused_attempted_problem_resumes_only_when_solved(session_factory, fake) -> None:
    slug = "median-of-two-sorted-arrays"  # attempted-only in the sample data
    run_sync(session_factory, fake)
    with session_factory() as s, s.begin():
        assert pause(s, [slug]) == 1

    fake.add(slug, FakeSub(303, "Wrong Answer", day(61)))  # another failed attempt
    run_sync(session_factory, fake)
    with session_factory() as s:
        assert s.get(Problem, slug).paused is True

    fake.add(slug, FakeSub(304, "Accepted", day(62)))  # first solve
    run_sync(session_factory, fake)
    with session_factory() as s:
        assert s.get(Problem, slug).paused is False
        assert s.get(Card, slug) is not None
        assert [p.slug for p in pending_ratings(s)] == [slug]
