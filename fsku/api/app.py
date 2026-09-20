"""FastAPI application factory and static server configuration."""

from __future__ import annotations
import asyncio
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from fsku import __version__
from fsku.api.routes import router
from fsku.core.database import get_db

def create_app(db_storage_dir: str = None) -> FastAPI:
    """Create and configure the FastAPI web application."""
    app = FastAPI(
        title="FSKU - GPU Compute Benchmark Index & Forward Curves (Built by NATIVX)",
        description="Open GPU compute price normalization, benchmark indexing, and implied forward curves. Built and maintained by NATIVX (nativx.net).",
        version=__version__,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    db = get_db(db_storage_dir)

    web_dir = Path(__file__).resolve().parent.parent / "web"
    index_file = web_dir / "index.html"

    @app.get("/", include_in_schema=False)
    def serve_dashboard():
        if index_file.exists():
            return FileResponse(index_file, media_type="text/html")
        return {"service": "FSKU API", "version": __version__, "docs": "/api/docs"}

    if web_dir.exists():
        app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")

    # Optional in-process daily settlement. Set FSKU_DAILY_FIX_UTC=HH:MM to
    # settle once a day at that UTC time while the server runs. Off by default;
    # the repository's scheduled workflow is the canonical publisher.
    schedule = os.environ.get("FSKU_DAILY_FIX_UTC")
    if schedule:
        @app.on_event("startup")
        async def _start_daily_fix():
            app.state.daily_fix_task = asyncio.create_task(_daily_fix_loop(db, schedule))

        @app.on_event("shutdown")
        async def _stop_daily_fix():
            task = getattr(app.state, "daily_fix_task", None)
            if task:
                task.cancel()

    return app


async def _daily_fix_loop(db, hhmm: str) -> None:
    from datetime import datetime, timedelta, timezone
    from fsku.core.settle import SettlementEngine
    hh, mm = (int(x) for x in hhmm.split(":"))
    while True:
        now = datetime.now(timezone.utc)
        nxt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if nxt <= now:
            nxt += timedelta(days=1)
        await asyncio.sleep((nxt - now).total_seconds())
        try:
            await SettlementEngine(db).settle()
        except Exception:
            pass  # one failed day leaves a gap in the history; it does not stop the next day

app = create_app()
