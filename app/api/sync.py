from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.sync.engine import get_state
from app.sync.manager import SyncManager, get_sync_manager

router = APIRouter(prefix="/sync", tags=["sync"])

Manager = Annotated[SyncManager, Depends(get_sync_manager)]
Db = Annotated[Session, Depends(get_db)]


def _status(manager: SyncManager, db: Session) -> dict[str, Any]:
    return {
        **asdict(manager.status()),
        "last_sync_at": get_state(db, "last_sync_at"),
        "backfill_done": bool(get_state(db, "backfill_done", False)),
    }


@router.post("", status_code=202)
def start_sync(manager: Manager, db: Db, full: bool = False) -> dict[str, Any]:
    """Start a sync in the background; if one is running, just report it."""
    manager.start(full=full)
    return _status(manager, db)


@router.get("/status")
def sync_status(manager: Manager, db: Db) -> dict[str, Any]:
    return _status(manager, db)
