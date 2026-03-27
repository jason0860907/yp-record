"""Screenshot upload and retrieval endpoints."""
from __future__ import annotations

import time
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

from src.service import get_service

router = APIRouter(prefix="/api/sessions/{session_id}/screenshots", tags=["screenshots"])


@router.post("")
async def upload_screenshot(session_id: str, file: UploadFile = File(...)):
    svc = get_service()
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(400, "Empty file")

    # Calculate timestamp relative to session start (seconds from 0)
    session = svc.session_manager.get_session(session_id)
    if session and session.started_at:
        started = datetime.fromisoformat(session.started_at).timestamp()
        timestamp = time.time() - started
    else:
        timestamp = 0.0

    filename = await svc.session_store.save_screenshot(session_id, timestamp, image_bytes)
    return {"filename": filename, "timestamp": timestamp}


@router.get("")
async def list_screenshots(session_id: str):
    svc = get_service()
    screenshots = await svc.session_store.list_screenshots(session_id)
    return {"screenshots": screenshots}


@router.get("/{filename}")
async def get_screenshot(session_id: str, filename: str):
    if ".." in filename or "/" in filename:
        raise HTTPException(400, "Invalid filename")
    svc = get_service()
    path = svc.session_store.get_screenshots_dir(session_id) / filename
    if not path.exists():
        raise HTTPException(404, "Screenshot not found")
    return FileResponse(path, media_type="image/jpeg")
