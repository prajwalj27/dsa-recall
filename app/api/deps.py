from datetime import datetime
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db

Db = Annotated[Session, Depends(get_db)]


def local_now() -> datetime:
    """The app runs on the user's machine, so its local clock defines "today"."""
    return datetime.now().astimezone()


def local_day_start(now: datetime | None = None) -> datetime:
    now = now or local_now()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)
