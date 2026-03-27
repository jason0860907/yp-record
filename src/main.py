"""FastAPI application entry point."""
from __future__ import annotations

import warnings
warnings.filterwarnings("ignore", message="torchcodec is not installed")
warnings.filterwarnings("ignore", message="TensorFloat-32.*has been disabled")
warnings.filterwarnings("ignore", message="std\\(\\): degrees of freedom")

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.infra.config import get_settings
from src.recording.service import get_service
from src.routers import sessions, audio_ws, transcript_ws, alignment, notion_export, screenshots
from src.routers.transcript_ws import setup_event_handlers
from src.infra.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    svc = get_service()
    await svc.start()
    setup_event_handlers()
    logger.info("yp-record started")
    yield
    # Shutdown
    await svc.close()
    logger.info("yp-record stopped")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="yp-record",
        description="Lightweight recording pipeline: ASR → alignment → diarization → Notion",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes
    app.include_router(sessions.router)
    app.include_router(audio_ws.router)
    app.include_router(transcript_ws.router)
    app.include_router(alignment.router)
    app.include_router(notion_export.router)
    app.include_router(screenshots.router)

    # Health + config
    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/config")
    async def config():
        svc = get_service()
        return {
            "notion_enabled": svc.notion_enabled,
            "aligner_enabled": svc.forced_aligner is not None,
            "diarization_enabled": svc.diarization_service is not None,
            "extract_enabled": svc.extract_enabled,
            "screenshot_interval_seconds": settings.screenshot_interval_seconds,
        }

    # Serve React frontend (if built)
    web_dist = Path("web/dist")
    if web_dist.exists():
        app.mount("/", StaticFiles(directory=str(web_dist), html=True), name="frontend")

    return app


app = create_app()
