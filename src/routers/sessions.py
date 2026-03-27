"""Session CRUD and lifecycle endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

from src.recording.service import get_service

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    title: str | None = None
    participants: List[str] = []


class UpdateSessionRequest(BaseModel):
    title: str | None = None
    participants: List[str] | None = None


class SessionActionRequest(BaseModel):
    action: str  # start | pause | resume | end


@router.post("")
async def create_session(body: CreateSessionRequest):
    svc = get_service()
    session = await svc.session_manager.create_session(
        title=body.title, participants=body.participants
    )
    return session.model_dump()


@router.get("")
async def list_sessions():
    svc = get_service()
    sessions = await svc.session_manager.list_all_sessions()
    return {"sessions": [s.model_dump() for s in sessions]}


@router.get("/{session_id}")
async def get_session(session_id: str):
    svc = get_service()
    session = await svc.session_manager.get_session_or_disk(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.model_dump()


@router.patch("/{session_id}")
async def update_session(session_id: str, body: UpdateSessionRequest):
    svc = get_service()
    try:
        session = await svc.session_manager.update_session(
            session_id, title=body.title, participants=body.participants
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.model_dump()


@router.post("/{session_id}/action")
async def session_action(session_id: str, body: SessionActionRequest):
    svc = get_service()
    try:
        if body.action == "start":
            session = await svc.session_manager.start_session(session_id)
        elif body.action == "pause":
            session = await svc.session_manager.pause_session(session_id)
        elif body.action == "resume":
            session = await svc.session_manager.resume_session(session_id)
        elif body.action == "end":
            session = await svc.session_manager.end_session(session_id)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {body.action}")
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return session.model_dump()


@router.get("/{session_id}/segments")
async def get_segments(session_id: str):
    svc = get_service()
    segments = await svc.session_store.load_segments(session_id)
    return {"segments": [s.model_dump() for s in segments]}


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    svc = get_service()
    await svc.session_manager.delete_session(session_id)
    return {"deleted": True}
