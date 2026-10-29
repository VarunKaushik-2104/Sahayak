"""FastAPI application: JSON API under /api, the offline-first web app at /."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from . import __version__
from .config import settings
from .content import get_curriculum
from .db import SessionLocal, engine, init_db
from .routers import auth, content, parent, practice, student, teacher

log = logging.getLogger("sahayak")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    cur = get_curriculum()
    problems = cur.validate()
    if problems:
        log.error("Curriculum problems: %s", problems[:5])
    if settings.secret_is_ephemeral:
        log.warning("SECRET_KEY is not set: using a random key. Sessions end on restart. Set SECRET_KEY in production.")
    if settings.seed_demo:
        with SessionLocal() as db:
            from .seed import seed_demo

            if seed_demo(db, cur):
                log.info("Demo data created")
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Sahayak API", version=__version__, lifespan=lifespan,
                  description="Concept-gap tracing and exam preparation for Classes 6 to 10 (CBSE, ICSE, Telangana).")
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    if settings.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.url.path.startswith("/api/") and "cache-control" not in resp.headers:
            resp.headers["Cache-Control"] = "no-store"
        return resp

    for r in (auth.router, content.router, student.router, practice.router, teacher.router, parent.router):
        app.include_router(r, prefix="/api")

    @app.get("/api/health", tags=["meta"])
    def health():
        with engine.connect() as c:
            c.execute(text("select 1"))
        cur = get_curriculum()
        return {"status": "ok", "version": __version__, "topics": len(cur.T), "questions": cur.n_questions, "content": cur.version}

    if settings.frontend_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.frontend_dir, html=True), name="web")
    return app


app = create_app()
