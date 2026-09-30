import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.config import Settings
from app.leetcode import LeetCodeClient
from app.leetcode.throttle import Throttle

FIXTURES = Path(__file__).parent.parent / "fixtures" / "leetcode"

# A handler gets the GraphQL payload and returns a JSON body (HTTP 200) or a full response.
Handler = Callable[[dict[str, Any]], dict[str, Any] | httpx.Response]


def load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.json").read_text())


def payload_of(request: httpx.Request) -> dict[str, Any]:
    return json.loads(request.content)


class FakeClock:
    """Stands in for time.monotonic/time.sleep so throttle and backoff never really wait."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        leetcode_username="testuser",
        leetcode_session="sess-cookie",
        leetcode_csrftoken="csrf-token",
    )


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def sent() -> list[httpx.Request]:
    """Every request the client sent, in order."""
    return []


@pytest.fixture
def make_client(
    settings: Settings, fake_clock: FakeClock, sent: list[httpx.Request]
) -> Callable[[Handler], LeetCodeClient]:
    def factory(handler: Handler) -> LeetCodeClient:
        def respond(request: httpx.Request) -> httpx.Response:
            sent.append(request)
            result = handler(payload_of(request))
            if isinstance(result, httpx.Response):
                return result
            return httpx.Response(200, json=result)

        http = httpx.Client(base_url="https://leetcode.com", transport=httpx.MockTransport(respond))
        throttle = Throttle(clock=fake_clock.clock, sleep=fake_clock.sleep)
        return LeetCodeClient(settings, http=http, throttle=throttle, sleep=fake_clock.sleep)

    return factory
