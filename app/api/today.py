from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import Db, local_day_start, local_now
from app.api.schemas import (
    AttemptedItem,
    DueItem,
    DueSection,
    PausedItem,
    PendingItem,
    StudyModeOut,
    TargetOut,
    TodayOut,
)
from app.db.models import Problem, Submission
from app.engines.reviews import (
    due_reviews,
    paused_problems,
    pending_ratings,
    reviews_done_today,
)
from app.settings_store import get_study_mode, get_target
from app.sync.engine import get_state
from app.timeutil import as_utc

router = APIRouter(tags=["today"])


@router.get("/today")
def today(db: Db) -> TodayOut:
    now = local_now()
    target = get_target(db)
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
        study_mode=StudyModeOut(enabled=study.enabled),
        target=TargetOut.model_validate(target),
        paused=[PausedItem.model_validate(p) for p in paused_problems(db, now)],
        backfill_done=bool(get_state(db, "backfill_done", False)),
    )
    db.commit()
    return out


def _attempted(db: Db) -> list[AttemptedItem]:
    """Problems submitted to but never accepted (and not paused), most recent first."""
    problems = db.scalars(
        select(Problem)
        .where(Problem.question_status == "ATTEMPTED", Problem.paused.is_(False))
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
