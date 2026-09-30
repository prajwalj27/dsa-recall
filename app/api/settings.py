from fastapi import APIRouter, HTTPException

from app.api.deps import Db
from app.api.schemas import StudyModeIn, StudyModeOut, TargetIn, TargetOut
from app.engines.reviews import change_target
from app.settings_store import get_study_mode, get_target, set_study_mode

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/target")
def read_target(db: Db) -> TargetOut:
    return TargetOut.model_validate(get_target(db))


@router.put("/target")
def put_target(body: TargetIn, db: Db) -> TargetOut:
    """Apply a daily target. Casual/Steady are presets; Interview takes a number/retention."""
    try:
        target = change_target(
            db, body.mode, daily_target=body.daily_target, retention=body.retention
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    db.commit()
    return TargetOut.model_validate(target)


@router.put("/study-mode")
def put_study_mode(body: StudyModeIn, db: Db) -> StudyModeOut:
    set_study_mode(db, body.enabled)
    db.commit()
    return StudyModeOut(enabled=get_study_mode(db).enabled)
