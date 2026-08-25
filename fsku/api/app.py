"""FastAPI application factory and static server configuration."""

from __future__ import annotations
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

    return app

app = create_app()
