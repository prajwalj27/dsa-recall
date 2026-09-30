"""Helpers to seed the test DB directly (without going through a sync)."""

from datetime import UTC, datetime, timedelta
from itertools import count

from app.db.models import Problem, Solve, Submission
from app.engines.reviews import INFERRED
from app.timeutil import utc_naive

T0 = datetime(2026, 1, 1, tzinfo=UTC)
NOW = datetime(2026, 9, 30, tzinfo=UTC)
_ids = count(1000)


def at(days: float) -> datetime:
    return T0 + timedelta(days=days)


def add_problem(session, slug: str, difficulty: str = "Medium") -> None:
    session.add(Problem(slug=slug, title=slug.replace("-", " ").title(), difficulty=difficulty))
    session.flush()


def add_solve(session, slug: str, when: datetime, wrong: int = 0, source: str = INFERRED) -> Solve:
    submission = Submission(
        submission_id=next(_ids),
        slug=slug,
        status="Accepted",
        lang="python3",
        timestamp=utc_naive(when),
    )
    session.add(submission)
    session.flush()
    solve = Solve(
        slug=slug,
        accepted_submission_id=submission.submission_id,
        wrong_before_ac=wrong,
        accepted_at=utc_naive(when),
        rating_source=source,
    )
    session.add(solve)
    session.flush()
    return solve


def add_submission(session, slug: str, when: datetime, status: str = "Wrong Answer") -> int:
    """A standalone (usually failed) submission; returns its id."""
    submission_id = next(_ids)
    session.add(
        Submission(
            submission_id=submission_id,
            slug=slug,
            status=status,
            lang="python3",
            timestamp=utc_naive(when),
        )
    )
    session.flush()
    return submission_id
