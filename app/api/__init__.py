from fastapi import APIRouter

from app.api import health, problems, settings, solves, sync, today

api_router = APIRouter()
for module in (health, sync, today, problems, solves, settings):
    api_router.include_router(module.router)
