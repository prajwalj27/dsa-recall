from fastapi import APIRouter

from app.api.deps import Db, local_now
from app.api.schemas import SolvedRow
from app.engines.reviews import solved_list

router = APIRouter(tags=["solved"])


@router.get("/solved")
def solved(db: Db) -> list[SolvedRow]:
    """Every problem submitted to (solved or attempted); the page filters and sorts."""
    return [SolvedRow.model_validate(row) for row in solved_list(db, local_now())]
