"""WebSocket endpoint for real-time transcript events."""
from __future__ import annotations

import asyncio
import json
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from src.events import EventType, Event, get_event_bus
from src.logging import get_logger

router = APIRouter(tags=["transcript"])
logger = get_logger(__name__)

# session_id → set of connected WebSocket clients
_subscribers: Dict[str, Set[WebSocket]] = {}


def _add_subscriber(session_id: str, ws: WebSocket) -> None:
    if session_id not in _subscribers:
        _subscribers[session_id] = set()
    _subscribers[session_id].add(ws)


def _remove_subscriber(session_id: str, ws: WebSocket) -> None:
    if session_id in _subscribers:
        _subscribers[session_id].discard(ws)
        if not _subscribers[session_id]:
            del _subscribers[session_id]


async def _broadcast(session_id: str, message: dict) -> None:
    clients = list(_subscribers.get(session_id, set()))
    for ws in clients:
        try:
            if ws.client_state == WebSocketState.CONNECTED:
                await ws.send_text(json.dumps(message))
        except Exception:
            _remove_subscriber(session_id, ws)


def setup_event_handlers() -> None:
    """Register global event bus handlers to broadcast events to WebSocket clients."""
    bus = get_event_bus()

    async def on_transcript_segment(event: Event) -> None:
        session_id = event.data.get("session_id", "")
        segment = event.data.get("segment", {})
        if session_id:
            await _broadcast(session_id, {"type": "transcript_segment", "segment": segment})

    async def on_alignment_started(event: Event) -> None:
        session_id = event.data.get("session_id", "")
        if session_id:
            await _broadcast(session_id, {"type": "alignment_started", "session_id": session_id})

    async def on_alignment_completed(event: Event) -> None:
        session_id = event.data.get("session_id", "")
        if session_id:
            await _broadcast(session_id, {
                "type": "alignment_completed",
                "session_id": session_id,
                "num_segments": event.data.get("num_segments", 0),
                "num_speakers": event.data.get("num_speakers", 0),
            })

    async def on_alignment_failed(event: Event) -> None:
        session_id = event.data.get("session_id", "")
        if session_id:
            await _broadcast(session_id, {
                "type": "alignment_failed",
                "session_id": session_id,
                "error": event.data.get("error", ""),
            })

    bus.subscribe(EventType.TRANSCRIPT_SEGMENT, on_transcript_segment)
    bus.subscribe(EventType.ALIGNMENT_STARTED, on_alignment_started)
    bus.subscribe(EventType.ALIGNMENT_COMPLETED, on_alignment_completed)
    bus.subscribe(EventType.ALIGNMENT_FAILED, on_alignment_failed)


@router.websocket("/api/transcript/ws")
async def transcript_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()
    _add_subscriber(session_id, websocket)
    logger.info(f"Transcript WebSocket connected: session={session_id}")

    try:
        while True:
            # Keep connection alive; client messages are not expected
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        logger.info(f"Transcript WebSocket disconnected: session={session_id}")
    except Exception as e:
        logger.error(f"Transcript WebSocket error: {e}")
    finally:
        _remove_subscriber(session_id, websocket)
