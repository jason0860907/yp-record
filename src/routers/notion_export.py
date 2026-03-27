"""Notion export and extraction endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.recording.service import get_service

router = APIRouter(prefix="/api/sessions", tags=["notion"])

_NOTION_PAGE_URL = "https://notion.so/{page_id}"


@router.post("/{session_id}/export/notion")
async def export_to_notion(session_id: str):
    svc = get_service()
    if not svc.notion_enabled:
        raise HTTPException(
            status_code=503,
            detail="Notion is not configured. Set NOTION_API_KEY and NOTION_DATABASE_ID.",
        )

    session = await svc.session_manager.get_session_or_disk(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        page_id = await svc.export_to_notion(session_id)
        url = _NOTION_PAGE_URL.format(page_id=page_id.replace("-", ""))
        return {"notion_page_id": page_id, "url": url}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Notion export failed: {e}")


@router.post("/{session_id}/extract")
async def extract_session(session_id: str):
    """Manually trigger transcript polish + meeting note generation."""
    svc = get_service()
    if not svc.extract_enabled:
        raise HTTPException(
            status_code=503,
            detail="Extraction is not enabled. Set EXTRACT_ENABLED=true and configure LLM settings.",
        )

    session = await svc.session_manager.get_session_or_disk(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        await svc.trigger_extract(session_id)
        meeting_note = await svc.session_store.load_meeting_note(session_id)
        polished = await svc.session_store.load_polished_transcript(session_id)
        return {
            "session_id": session_id,
            "has_polished_transcript": polished is not None,
            "meeting_note_title": meeting_note.title if meeting_note else None,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {e}")


@router.get("/{session_id}/meeting-note")
async def get_meeting_note(session_id: str):
    """Get the generated meeting note for a session."""
    svc = get_service()
    session = await svc.session_manager.get_session_or_disk(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    meeting_note = await svc.session_store.load_meeting_note(session_id)
    if not meeting_note:
        raise HTTPException(status_code=404, detail="Meeting note not found. Run extraction first.")

    return {
        "session_id": session_id,
        "title": meeting_note.title,
        "content": meeting_note.content,
        "category": meeting_note.category.value,
        "tags": meeting_note.tags,
        "created_at": meeting_note.created_at,
    }


@router.get("/{session_id}/polished-transcript")
async def get_polished_transcript(session_id: str):
    """Get the polished transcript for a session."""
    svc = get_service()
    session = await svc.session_manager.get_session_or_disk(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    polished = await svc.session_store.load_polished_transcript(session_id)
    if not polished:
        raise HTTPException(status_code=404, detail="Polished transcript not found. Run extraction first.")

    return {"session_id": session_id, "transcript": polished}
