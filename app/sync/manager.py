import copy
import threading
from collections.abc import Callable
from functools import lru_cache

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_sessionmaker
from app.leetcode import LeetCodeClient
from app.sync.engine import run_sync
from app.sync.progress import RunState, SyncProgress


class SyncManager:
    """Runs at most one sync at a time in a background thread and exposes its progress."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        client_factory: Callable[[], LeetCodeClient],
    ) -> None:
        self._session_factory = session_factory
        self._client_factory = client_factory
        self._progress = SyncProgress()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, full: bool = False) -> bool:
        """Start a sync unless one is already running. Returns whether one was started."""
        with self._lock:
            if self.running:
                return False
            self._progress.reset()
            self._progress.state = RunState.RUNNING  # visible before the thread gets going
            self._thread = threading.Thread(
                target=self._run, args=(full,), name="dsa-recall-sync", daemon=True
            )
            self._thread.start()
            return True

    def wait(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    def status(self) -> SyncProgress:
        return copy.copy(self._progress)

    def _run(self, full: bool) -> None:
        with self._client_factory() as client:
            run_sync(self._session_factory, client, self._progress, full=full)


@lru_cache
def get_sync_manager() -> SyncManager:
    """The process-wide manager. Settings are read per run, so a new cookie needs a restart."""
    return SyncManager(
        session_factory=lambda: get_sessionmaker()(),
        client_factory=lambda: LeetCodeClient(get_settings()),
    )
