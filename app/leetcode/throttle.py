import threading
import time
from collections.abc import Callable


class Throttle:
    """Keeps at least `min_interval` seconds between the starts of consecutive requests."""

    def __init__(
        self,
        min_interval: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.min_interval = min_interval
        self._clock = clock
        self._sleep = sleep
        self._last: float | None = None
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = self._clock()
            if self._last is not None:
                remaining = self._last + self.min_interval - now
                if remaining > 0:
                    self._sleep(remaining)
                    now = self._clock()
            self._last = now
