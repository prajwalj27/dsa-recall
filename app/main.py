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
from app.config import ROOT_DIR, get_settings
from app.db.migrate import upgrade_to_head

WEB_DIST = ROOT_DIR / "web" / "dist"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    upgrade_to_head(get_settings().database_url)
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
    """Entry point for the `dsa-recall` command."""
    settings = get_settings()
    url = f"http://{settings.host}:{settings.port}"
    threading.Timer(1.5, webbrowser.open, args=[url]).start()
    uvicorn.run(app, host=settings.host, port=settings.port)
