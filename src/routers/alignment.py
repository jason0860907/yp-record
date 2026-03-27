"""Alignment endpoints."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from src.service import get_service
from src.logging import get_logger

router = APIRouter(prefix="/api/sessions", tags=["alignment"])
logger = get_logger(__name__)


@router.get("/{session_id}/alignment")
async def get_alignment(session_id: str):
    svc = get_service()
    result = await svc.session_store.load_alignment_result(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Alignment result not found")
    return result.model_dump()


@router.get("/{session_id}/alignment/status")
async def get_alignment_status(session_id: str):
    svc = get_service()
    result = await svc.session_store.load_alignment_result(session_id)
    wav_path = svc.session_store.get_audio_wav_path(session_id)
    raw_path = svc.session_store.get_audio_raw_path(session_id)

    if not result:
        return {
            "session_id": session_id,
            "status": "not_started",
            "num_segments": 0,
            "num_speakers": 0,
            "processing_time_seconds": 0.0,
            "error": None,
            "audio_available": raw_path.exists() or wav_path.exists(),
            "wav_available": wav_path.exists(),
            "service_available": svc.forced_aligner is not None,
        }

    return {
        "session_id": session_id,
        "status": result.status,
        "num_segments": len(result.segments),
        "num_speakers": result.num_speakers,
        "processing_time_seconds": result.processing_time_seconds,
        "error": result.error,
        "audio_available": raw_path.exists() or wav_path.exists(),
        "wav_available": wav_path.exists(),
        "service_available": svc.forced_aligner is not None,
    }


@router.post("/{session_id}/alignment")
async def trigger_alignment(session_id: str):
    svc = get_service()
    if not svc.forced_aligner:
        raise HTTPException(status_code=503, detail="Forced aligner is not enabled")
    session = await svc.session_manager.get_session_or_disk(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    import asyncio
    asyncio.create_task(svc.trigger_alignment(session_id))
    return {"status": "processing", "session_id": session_id}


@router.get("/{session_id}/audio")
async def get_audio(session_id: str):
    svc = get_service()
    wav_path = svc.session_store.get_audio_wav_path(session_id)
    if not wav_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(
        path=str(wav_path),
        media_type="audio/wav",
        filename=f"{session_id}.wav",
    )
