import logging
import threading
import webbrowser
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import api_router
from app.config import ENV_VAR, ROOT_DIR, env_set_in_dotenv, get_settings, use_env
from app.db.migrate import prepare_database

log = logging.getLogger("dsa_recall")

WEB_DIST = ROOT_DIR / "web" / "dist"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if env_set_in_dotenv():
        log.warning("%s is set in .env; remove it so dev stays the default", ENV_VAR)
    log.warning("Using the %s database: %s", settings.env, settings.resolved_database_path)
    prepare_database(settings)
    yield


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built React app, falling back to index.html for client-side routes."""
    if (WEB_DIST / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        file = (WEB_DIST / path).resolve()
        if path and file.is_file() and file.is_relative_to(WEB_DIST):
            return FileResponse(file)
        return FileResponse(WEB_DIST / "index.html")


def create_app() -> FastAPI:
    app = FastAPI(title="DSA Recall", version=__version__, lifespan=lifespan)
    app.include_router(api_router, prefix="/api")
    if (WEB_DIST / "index.html").is_file():
        _mount_frontend(app)
    return app


app = create_app()


def run() -> None:
    """Entry point for the `dsa-recall` command: the real app, on the prod database."""
    settings = use_env("prod")
    url = f"http://{settings.host}:{settings.port}"
    threading.Timer(1.5, webbrowser.open, args=[url]).start()
    uvicorn.run(app, host=settings.host, port=settings.port)
