"""The DB stores naive UTC datetimes; code outside the DB works with aware UTC ones."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_naive(dt: datetime) -> datetime:
    """Aware (any zone) or naive-UTC -> naive UTC, for storing."""
    return dt.astimezone(UTC).replace(tzinfo=None) if dt.tzinfo else dt


def as_utc(dt: datetime) -> datetime:
    """Naive UTC from the DB -> aware UTC."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
