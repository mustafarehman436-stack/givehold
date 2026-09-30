"""Single-service hosted application; the local API remains unchanged."""
import os
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .db import engine
from .main import app as api


def create_app():
    static_dir = Path(os.environ.get("STATIC_DIR", "/app/static"))
    if not (static_dir / "index.html").is_file():
        raise RuntimeError("Build the frontend before starting the hosted demo")
    hosted = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @hosted.middleware("http")
    async def demo_access(request: Request, call_next):
        # Render needs one unauthenticated readiness check, with no record data.
        if request.url.path == "/health" and request.method in ("GET", "HEAD"):
            return await call_next(request)
        # Reject browser writes originating on another website.
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            if request.headers.get("sec-fetch-site") == "cross-site" or (
                origin and urlsplit(origin).netloc != request.headers.get("host")
            ):
                return JSONResponse({"detail": "Cross-origin writes are not allowed"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @hosted.get("/health")
    def health():
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok"}

    hosted.mount("/api", api)
    hosted.mount("/", StaticFiles(directory=static_dir, html=True))
    return hosted
