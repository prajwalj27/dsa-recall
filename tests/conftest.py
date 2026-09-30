from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db.session import get_engine, get_sessionmaker
from app.main import create_app


def _clear_caches() -> None:
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()


@pytest.fixture
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point the app at a fresh SQLite file for this test."""
    path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(path))
    _clear_caches()
    yield path
    get_engine().dispose()
    _clear_caches()


@pytest.fixture
def client(db_path: Path) -> Iterator[TestClient]:
    # Entering the context runs the lifespan, which applies migrations.
    with TestClient(create_app()) as test_client:
        yield test_client
