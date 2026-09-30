import threading

from fastapi.testclient import TestClient

from app.sync.manager import SyncManager, get_sync_manager
from tests.sync.conftest import FakeLeetCode


def test_start_and_poll_sync(client: TestClient, session_factory, fake: FakeLeetCode) -> None:
    fake.gate = threading.Event()  # hold the sync in check_auth until released
    manager = SyncManager(session_factory, client_factory=lambda: fake)
    client.app.dependency_overrides[get_sync_manager] = lambda: manager

    first = client.post("/api/sync")
    assert first.status_code == 202
    assert first.json()["state"] == "running"

    second = client.post("/api/sync")  # already running: reports, doesn't start another
    assert second.json()["state"] == "running"

    fake.gate.set()
    manager.wait(5)

    status = client.get("/api/sync/status").json()
    assert status["state"] == "succeeded"
    assert status["mode"] == "backfill"
    assert status["backfill_done"] is True
    assert status["last_sync_at"]
    assert fake.calls["check_auth"] == 1
