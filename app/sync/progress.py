from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum
from typing import Literal


class RunState(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ErrorKind(StrEnum):
    AUTH_EXPIRED = "auth_expired"
    RATE_LIMITED = "rate_limited"
    SCHEMA_CHANGED = "schema_changed"
    OTHER = "other"


@dataclass
class SyncProgress:
    """Live state of one sync run. Written by the engine, read by the API and CLI."""

    state: RunState = RunState.IDLE
    mode: Literal["backfill", "incremental"] | None = None
    phase: Literal["auth", "listing", "problems", "done"] | None = None
    done: int = 0  # problems processed (synced or skipped as unchanged)
    total: int | None = None  # known in backfill mode only
    current_slug: str | None = None
    new_submissions: int = 0
    new_solves: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_kind: ErrorKind | None = None
    error: str | None = None

    def reset(self) -> None:
        for field in fields(self):
            setattr(self, field.name, field.default)
