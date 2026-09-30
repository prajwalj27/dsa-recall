from fastapi import APIRouter

from app.api import health, problems, settings, solved, solves, sync, today

api_router = APIRouter()
for module in (health, sync, today, solved, problems, solves, settings):
    api_router.include_router(module.router)
