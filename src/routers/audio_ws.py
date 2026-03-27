"""WebSocket endpoint for receiving PCM audio."""
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.recording.service import get_service
from src.infra.logging import get_logger

router = APIRouter(tags=["audio"])
logger = get_logger(__name__)


@router.websocket("/api/audio/ws")
async def audio_websocket(websocket: WebSocket, session_id: str, channels: int = 2):
    await websocket.accept()
    svc = get_service()

    # Verify session exists
    session = await svc.session_manager.get_session_or_disk(session_id)
    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return

    # Save audio metadata
    await svc.save_audio_meta(session_id, channels)

    receiver = svc.create_audio_receiver(channels=channels, session_id=session_id)
    try:
        await receiver.handle_websocket(websocket, session_id)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Audio WebSocket error for session {session_id}: {e}")
