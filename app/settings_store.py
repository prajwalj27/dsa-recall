"""Typed access to user settings in the `settings` key-value table."""

from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

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


# --- Daily target modes (design doc) -------------------------------------------------------

TargetMode = Literal["casual", "steady", "interview", "custom"]
TARGET_MODES: dict[str, tuple[int, float | None]] = {
    # mode: (default daily target, retention; None = keep the current one)
    "casual": (5, 0.90),
    "steady": (8, 0.90),
    "interview": (15, 0.95),
    "custom": (8, None),
}
DEFAULT_MODE = "steady"
MIN_RETENTION, MAX_RETENTION = 0.70, 0.97


@dataclass(frozen=True)
class Target:
    mode: str
    daily_target: int
    retention: float
    interview_end_date: date | None = None  # after this day, revert to previous_mode
    previous_mode: str | None = None


def get_target(session: Session) -> Target:
    end = get_setting(session, "interview_end_date")
    return Target(
        mode=get_setting(session, "target_mode", DEFAULT_MODE),
        daily_target=int(get_setting(session, "daily_target", TARGET_MODES[DEFAULT_MODE][0])),
        retention=desired_retention(session),
        interview_end_date=date.fromisoformat(end) if end else None,
        previous_mode=get_setting(session, "previous_mode"),
    )


def set_target(
    session: Session,
    mode: str,
    daily_target: int | None = None,
    retention: float | None = None,
    end_date: date | None = None,
) -> bool:
    """Change the daily target. Returns True if retention changed (cards must be rebuilt).

    Picking a different mode applies its default number; the number can then be adjusted.
    Retention is set by the mode, except Custom, which takes an explicit one.
    """
    if mode not in TARGET_MODES:
        raise ValueError(f"Unknown target mode '{mode}'")
    if daily_target is not None and not 1 <= daily_target <= 100:
        raise ValueError("daily_target must be between 1 and 100")
    if retention is not None and not MIN_RETENTION <= retention <= MAX_RETENTION:
        raise ValueError(f"retention must be between {MIN_RETENTION} and {MAX_RETENTION}")

    current = get_target(session)
    default_number, mode_retention = TARGET_MODES[mode]
    if daily_target is None:
        daily_target = current.daily_target if mode == current.mode else default_number
    if mode == "custom":
        new_retention = retention if retention is not None else current.retention
    else:
        new_retention = mode_retention

    if mode == "interview" and current.mode != "interview":
        set_setting(session, "previous_mode", current.mode)
    set_setting(session, "target_mode", mode)
    set_setting(session, "daily_target", daily_target)
    set_setting(session, "desired_retention", new_retention)
    end = end_date.isoformat() if mode == "interview" and end_date else None
    set_setting(session, "interview_end_date", end)
    return new_retention != current.retention


def revert_expired_interview(session: Session, today: date) -> bool:
    """After Interview prep's end date, return to the previous mode. True if retention changed."""
    current = get_target(session)
    if current.mode != "interview" or not current.interview_end_date:
        return False
    if today <= current.interview_end_date:
        return False
    return set_target(session, current.previous_mode or DEFAULT_MODE)


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
