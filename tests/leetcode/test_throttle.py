import pytest

from app.leetcode.throttle import Throttle
from tests.leetcode.conftest import FakeClock


def test_first_call_does_not_wait() -> None:
    clock = FakeClock()
    Throttle(clock=clock.clock, sleep=clock.sleep).wait()
    assert clock.sleeps == []


def test_waits_out_the_rest_of_the_interval() -> None:
    clock = FakeClock()
    throttle = Throttle(min_interval=1.0, clock=clock.clock, sleep=clock.sleep)

    throttle.wait()
    throttle.wait()  # immediately after: the full second
    clock.now += 0.4
    throttle.wait()  # 0.4 s later: the remaining 0.6 s
    clock.now += 2.0
    throttle.wait()  # long after: no wait

    assert clock.sleeps == pytest.approx([1.0, 0.6])
