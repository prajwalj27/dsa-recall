from app.sync.codehash import code_hash
from app.sync.solves import Attempt, group_solves
from tests.sync.conftest import day


def ok(id_: int, at: float) -> Attempt:
    return Attempt(id_, True, day(at))


def fail(id_: int, at: float) -> Attempt:
    return Attempt(id_, False, day(at))


def summary(attempts: list[Attempt]) -> list[tuple[int, int, tuple[int, ...]]]:
    return [
        (s.accepted_submission_id, s.wrong_before_ac, s.failed_submission_ids)
        for s in group_solves(attempts)
    ]


def test_single_accept() -> None:
    assert summary([ok(1, 0)]) == [(1, 0, ())]


def test_failures_before_accept_count_as_wrong() -> None:
    assert summary([fail(1, 0), fail(2, 0.01), ok(3, 0.02)]) == [(3, 2, (1, 2))]


def test_only_last_three_failures_are_kept_for_details() -> None:
    attempts = [fail(i, i * 0.01) for i in range(1, 6)] + [ok(6, 0.1)]
    assert summary(attempts) == [(6, 5, (3, 4, 5))]


def test_accepts_minutes_apart_merge() -> None:
    assert summary([ok(1, 0), ok(2, 0.002)]) == [(1, 0, ())]


def test_accepts_more_than_a_day_apart_are_separate_solves() -> None:
    assert summary([ok(1, 0), ok(2, 25 / 24)]) == [(1, 0, ()), (2, 0, ())]


def test_merge_window_does_not_chain() -> None:
    # 0 h, 20 h, 40 h: the 40 h accept is > 24 h after the solve's first accept.
    assert summary([ok(1, 0), ok(2, 20 / 24), ok(3, 40 / 24)]) == [(1, 0, ()), (3, 0, ())]


def test_failures_between_merged_accepts_are_dropped() -> None:
    attempts = [ok(1, 0), fail(2, 0.01), ok(3, 0.02), ok(4, 5)]
    assert summary(attempts) == [(1, 0, ()), (4, 0, ())]


def test_failures_after_window_count_toward_next_solve() -> None:
    assert summary([ok(1, 0), fail(2, 3), ok(3, 3.01)]) == [(1, 0, ()), (3, 1, (2,))]


def test_failures_only_make_no_solve() -> None:
    assert summary([fail(1, 0), fail(2, 1)]) == []


def test_input_order_does_not_matter() -> None:
    attempts = [ok(3, 0.02), fail(1, 0), fail(2, 0.01)]
    assert summary(attempts) == [(3, 2, (1, 2))]


def test_code_hash_ignores_whitespace_only_changes() -> None:
    a = "def f(x):\n    return x + 1\n"
    b = "def f(x):   \n\n        return   x + 1"
    assert code_hash(a) == code_hash(b)
    assert code_hash(a) != code_hash("def f(x):\n    return x + 2\n")
