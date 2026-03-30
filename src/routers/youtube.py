"""YouTube video import endpoint."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.infra.models import SessionSource
from src.recording.service import get_service

router = APIRouter(prefix="/api/youtube", tags=["youtube"])


class YouTubeImportRequest(BaseModel):
    url: str
    title: str | None = None


@router.post("/import")
async def import_youtube(body: YouTubeImportRequest):
    svc = get_service()

    # Create session with youtube source
    session = await svc.session_manager.create_session(title=body.title)
    session.source = SessionSource.YOUTUBE
    session.source_url = body.url
    await svc.session_store.save_session(session)

    # Transition to PROCESSING
    await svc.session_manager.start_processing(session.id)

    # Fire-and-forget the import task
    asyncio.create_task(svc.import_youtube(body.url, session.id))

    return session.model_dump()
