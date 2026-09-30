"""Typed access to user settings in the `settings` key-value table."""

from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.db.models import Setting

DEFAULT_RETENTION = 0.90  # the design doc's Steady mode


def get_setting(session: Session, key: str, default: Any = None) -> Any:
    row = session.get(Setting, key)
    return default if row is None else row.value


def set_setting(session: Session, key: str, value: Any) -> None:
    session.merge(Setting(key=key, value=value))


def delete_setting(session: Session, key: str) -> None:
    row = session.get(Setting, key)
    if row is not None:
        session.delete(row)


def desired_retention(session: Session) -> float:
    return float(get_setting(session, "desired_retention", DEFAULT_RETENTION))


# --- Daily target modes --------------------------------------------------------------------
# Casual and Steady are fixed presets. Interview is the one adjustable mode: its own number
# of reviews and retention, remembered so switching back to it restores them.

TargetMode = Literal["casual", "steady", "interview"]
PRESETS: dict[str, tuple[int, float]] = {"casual": (5, 0.90), "steady": (8, 0.90)}
INTERVIEW_DEFAULTS = (15, 0.95)
DEFAULT_MODE = "steady"
MIN_RETENTION, MAX_RETENTION = 0.70, 0.97
# Keys from earlier versions (end dates, auto-revert), removed on the next save.
LEGACY_KEYS = ("interview_end_date", "previous_mode")


@dataclass(frozen=True)
class Target:
    mode: str
    daily_target: int
    retention: float
    # Interview's saved values, to pre-fill the form even while another mode is active.
    interview_target: int = INTERVIEW_DEFAULTS[0]
    interview_retention: float = INTERVIEW_DEFAULTS[1]


def _stored_mode(session: Session) -> str:
    mode = get_setting(session, "target_mode", DEFAULT_MODE)
    return "interview" if mode == "custom" else mode  # Custom became Interview


def _interview_values(session: Session) -> tuple[int, float]:
    saved_target = get_setting(session, "interview_target")
    saved_retention = get_setting(session, "interview_retention")
    if saved_target is not None and saved_retention is not None:
        return int(saved_target), float(saved_retention)
    if _stored_mode(session) == "interview":  # legacy Interview/Custom: its active values
        return int(get_setting(session, "daily_target", INTERVIEW_DEFAULTS[0])), (
            desired_retention(session)
        )
    return INTERVIEW_DEFAULTS


def get_target(session: Session) -> Target:
    mode = _stored_mode(session)
    interview_target, interview_retention = _interview_values(session)
    return Target(
        mode=mode,
        daily_target=int(get_setting(session, "daily_target", PRESETS[DEFAULT_MODE][0])),
        retention=desired_retention(session),
        interview_target=interview_target,
        interview_retention=interview_retention,
    )


def set_target(
    session: Session,
    mode: str,
    daily_target: int | None = None,
    retention: float | None = None,
) -> bool:
    """Change the daily target. Returns True if retention changed (cards must be rebuilt).

    Casual and Steady take no values. Interview takes a number and a retention, falling back
    to its saved (or default) values for any that are missing.
    """
    if mode in PRESETS:
        if daily_target is not None or retention is not None:
            raise ValueError(f"{mode.title()} uses fixed values; only Interview is adjustable")
        new_target, new_retention = PRESETS[mode]
    elif mode == "interview":
        if daily_target is not None and not 1 <= daily_target <= 100:
            raise ValueError("daily_target must be between 1 and 100")
        if retention is not None and not MIN_RETENTION <= retention <= MAX_RETENTION:
            raise ValueError(f"retention must be between {MIN_RETENTION} and {MAX_RETENTION}")
        saved_target, saved_retention = _interview_values(session)
        new_target = daily_target if daily_target is not None else saved_target
        new_retention = retention if retention is not None else saved_retention
        set_setting(session, "interview_target", new_target)
        set_setting(session, "interview_retention", new_retention)
    else:
        raise ValueError(f"Unknown target mode '{mode}'")

    previous_retention = desired_retention(session)
    set_setting(session, "target_mode", mode)
    set_setting(session, "daily_target", new_target)
    set_setting(session, "desired_retention", new_retention)
    for key in LEGACY_KEYS:
        delete_setting(session, key)
    return new_retention != previous_retention


# --- Study mode -----------------------------------------------------------------------------


@dataclass(frozen=True)
class StudyMode:
    """'I'm learning from solutions right now': first solves default to 'Saw solution'.

    On until switched off (earlier versions had an end date; it's ignored now).
    """

    enabled: bool = False


def get_study_mode(session: Session) -> StudyMode:
    value = get_setting(session, "study_mode") or {}
    return StudyMode(bool(value.get("enabled")))


def set_study_mode(session: Session, enabled: bool) -> None:
    set_setting(session, "study_mode", {"enabled": enabled})
