from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import Db, local_day_start, local_now
from app.api.schemas import (
    AttemptedItem,
    DueItem,
    DueSection,
    PendingItem,
    StudyModeOut,
    TargetOut,
    TodayOut,
)
from app.db.models import Problem, Submission
from app.engines.reviews import current_target, due_reviews, pending_ratings, reviews_done_today
from app.settings_store import get_study_mode
from app.sync.engine import get_state
from app.timeutil import as_utc

router = APIRouter(tags=["today"])


@router.get("/today")
def today(db: Db) -> TodayOut:
    now = local_now()
    target = current_target(db, now.date())  # may end an expired Interview prep
    due = due_reviews(db, now)
    done = reviews_done_today(db, local_day_start(now))
    study = get_study_mode(db)
    out = TodayOut(
        pending=[PendingItem.model_validate(p) for p in pending_ratings(db)],
        due=DueSection(
            items=[DueItem.model_validate(d) for d in due],
            shown=min(max(target.daily_target - done, 0), len(due)),
            total_due=len(due),
            done_today=done,
            target=target.daily_target,
        ),
        attempted=_attempted(db),
        study_mode=StudyModeOut(
            enabled=study.enabled, until=study.until, active=study.active(now.date())
        ),
        target=TargetOut.model_validate(target),
        backfill_done=bool(get_state(db, "backfill_done", False)),
    )
    db.commit()
    return out


def _attempted(db: Db) -> list[AttemptedItem]:
    """Problems submitted to but never accepted, most recent first."""
    problems = db.scalars(
        select(Problem)
        .where(Problem.question_status == "ATTEMPTED")
        .order_by(Problem.last_submitted_at.desc())
    ).all()
    items = []
    for problem in problems:
        last = db.scalar(
            select(Submission)
            .where(Submission.slug == problem.slug)
            .order_by(Submission.timestamp.desc())
            .limit(1)
        )
        items.append(
            AttemptedItem(
                slug=problem.slug,
                title=problem.title,
                difficulty=problem.difficulty,
                frontend_id=problem.frontend_id,
                last_status=last.status if last else None,
                last_submitted_at=as_utc(last.timestamp) if last else None,
            )
        )
    return items
