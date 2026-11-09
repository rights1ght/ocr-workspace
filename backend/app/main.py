"""OCR Workspace backend — точка входа (OCR/TZ 10.2)."""
from __future__ import annotations

from fastapi import FastAPI

from app.core.config import load_settings
from app.core.logging import setup_logging
from app.core.paths import ensure_dirs


def create_app() -> FastAPI:
    settings = load_settings()
    ensure_dirs(settings.data_dir)
    setup_logging(settings.data_dir, settings.debug)
    app = FastAPI(title="OCR Workspace", docs_url=None, redoc_url=None)
    app.state.settings = settings

    from app.db.session import create_engine, run_migrations
    from pathlib import Path

    eng = create_engine(Path(settings.data_dir) / "app.db")
    run_migrations(eng)
    app.state.engine = eng

    from app.api.documents import router as documents_router
    from app.api.jobs import router as jobs_router

    app.include_router(documents_router)
    app.include_router(jobs_router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    # Статика фронтенда (prod): backend отдаёт Vite-сборку на «/» (ТЗ §10.2, SEC-1 loopback-only).
    from pathlib import Path as _Path

    dist = _Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    if dist.is_dir():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")

    return app


app = create_app()
