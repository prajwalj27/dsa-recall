from fastapi import APIRouter, HTTPException

from app.api.deps import Db
from app.api.problems import card_out
from app.api.schemas import CardOut, ChoiceIn, ConfirmIn
from app.engines.reviews import confirm_defaults, set_rating

router = APIRouter(prefix="/solves", tags=["solves"])


@router.post("/confirm")
def confirm(body: ConfirmIn, db: Db) -> dict[str, int]:
    """'Confirm all': accept the pre-selected rating of these pending solves."""
    confirmed = confirm_defaults(db, body.solve_ids)
    db.commit()
    return {"confirmed": confirmed}


@router.post("/{solve_id}/rating")
def rate_solve(solve_id: int, body: ChoiceIn, db: Db) -> CardOut | None:
    try:
        card = set_rating(db, solve_id, body.choice)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    db.commit()
    return card_out(card)
