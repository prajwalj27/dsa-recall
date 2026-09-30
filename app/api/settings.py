from fastapi import APIRouter, HTTPException

from app.api.deps import Db, local_now
from app.api.schemas import StudyModeIn, StudyModeOut, TargetIn, TargetOut
from app.engines.reviews import change_target, current_target
from app.settings_store import get_study_mode, set_study_mode

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/target")
def get_target(db: Db) -> TargetOut:
    target = current_target(db, local_now().date())
    db.commit()
    return TargetOut.model_validate(target)


@router.put("/target")
def put_target(body: TargetIn, db: Db) -> TargetOut:
    try:
        target = change_target(
            db,
            body.mode,
            daily_target=body.daily_target,
            retention=body.retention,
            end_date=body.interview_end_date,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    db.commit()
    return TargetOut.model_validate(target)


@router.put("/study-mode")
def put_study_mode(body: StudyModeIn, db: Db) -> StudyModeOut:
    set_study_mode(db, body.enabled, body.until if body.enabled else None)
    db.commit()
    mode = get_study_mode(db)
    return StudyModeOut(
        enabled=mode.enabled, until=mode.until, active=mode.active(local_now().date())
    )
