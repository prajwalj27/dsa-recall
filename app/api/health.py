from fastapi import APIRouter

from app import __version__
from app.config import get_settings

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "version": __version__,
        "env": settings.env,
        "database": settings.resolved_database_path.name,
    }
