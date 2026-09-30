"""Typed access to user settings in the `settings` key-value table."""

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Setting

DEFAULT_RETENTION = 0.90  # the design doc's Steady mode


def get_setting(session: Session, key: str, default: Any = None) -> Any:
    row = session.get(Setting, key)
    return default if row is None else row.value


def set_setting(session: Session, key: str, value: Any) -> None:
    session.merge(Setting(key=key, value=value))


def desired_retention(session: Session) -> float:
    return float(get_setting(session, "desired_retention", DEFAULT_RETENTION))


@dataclass(frozen=True)
class StudyMode:
    """'I'm learning from solutions right now': first solves default to 'Saw solution'."""

    enabled: bool = False
    until: date | None = None  # last day it applies; None = until turned off

    def active(self, today: date) -> bool:
        return self.enabled and (self.until is None or today <= self.until)


def get_study_mode(session: Session) -> StudyMode:
    value = get_setting(session, "study_mode") or {}
    until = value.get("until")
    return StudyMode(bool(value.get("enabled")), date.fromisoformat(until) if until else None)


def set_study_mode(session: Session, enabled: bool, until: date | None = None) -> None:
    value = {"enabled": enabled, "until": until.isoformat() if until else None}
    set_setting(session, "study_mode", value)
