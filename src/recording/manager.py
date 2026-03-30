"""Recording session lifecycle manager."""
from __future__ import annotations

import uuid
from typing import Dict, TYPE_CHECKING

from src.infra.models import SessionInfo, SessionStatus, _iso_now
from src.infra.events import EventType, publish_event
from src.infra.logging import get_logger

if TYPE_CHECKING:
    from src.recording.store import RecordingSessionStore

logger = get_logger(__name__)

_VALID_TRANSITIONS: Dict[SessionStatus, set] = {
    SessionStatus.IDLE: {SessionStatus.RECORDING, SessionStatus.PROCESSING},
    SessionStatus.RECORDING: {SessionStatus.PAUSED, SessionStatus.COMPLETED},
    SessionStatus.PAUSED: {SessionStatus.RECORDING, SessionStatus.COMPLETED},
    SessionStatus.PROCESSING: {SessionStatus.COMPLETED, SessionStatus.ERROR},
    SessionStatus.COMPLETED: set(),
    SessionStatus.ERROR: set(),
}


class RecordingSessionManager:
    """Manages recording session lifecycles."""

    def __init__(self, store: "RecordingSessionStore | None" = None) -> None:
        self._sessions: Dict[str, SessionInfo] = {}
        self._store = store
        logger.info("RecordingSessionManager created")

    def _check_transition(self, session: SessionInfo, target: SessionStatus) -> None:
        allowed = _VALID_TRANSITIONS.get(session.status, set())
        if target not in allowed:
            raise ValueError(
                f"Invalid state transition: {session.status.value} -> {target.value}"
            )

    async def create_session(
        self, title: str | None = None, participants: list[str] | None = None
    ) -> SessionInfo:
        session_id = uuid.uuid4().hex
        session = SessionInfo(
            id=session_id,
            status=SessionStatus.IDLE,
            title=title,
            participants=participants or [],
        )
        self._sessions[session_id] = session
        if self._store:
            await self._store.save_session(session)
        logger.info(f"Session created: {session_id}")
        return session

    async def start_processing(self, session_id: str) -> SessionInfo:
        session = self._require_session(session_id)
        self._check_transition(session, SessionStatus.PROCESSING)
        session.status = SessionStatus.PROCESSING
        session.started_at = _iso_now()
        if self._store:
            await self._store.save_session(session)
        logger.info(f"Session processing: {session_id}")
        return session

    async def complete_processing(self, session_id: str, duration: float = 0.0) -> SessionInfo:
        session = self._require_session(session_id)
        self._check_transition(session, SessionStatus.COMPLETED)
        session.status = SessionStatus.COMPLETED
        session.ended_at = _iso_now()
        session.duration_seconds = duration
        if self._store:
            await self._store.save_session(session)
        logger.info(f"Session processing completed: {session_id}")
        return session

    async def fail_processing(self, session_id: str, error: str = "") -> SessionInfo:
        session = self._require_session(session_id)
        self._check_transition(session, SessionStatus.ERROR)
        session.status = SessionStatus.ERROR
        session.ended_at = _iso_now()
        if self._store:
            await self._store.save_session(session)
        logger.error(f"Session processing failed: {session_id} — {error}")
        return session

    async def start_session(self, session_id: str) -> SessionInfo:
        session = self._require_session(session_id)
        self._check_transition(session, SessionStatus.RECORDING)
        session.status = SessionStatus.RECORDING
        session.started_at = _iso_now()
        if self._store:
            await self._store.save_session(session)
        await publish_event(EventType.SESSION_STARTED, data={"session_id": session_id}, source="session_manager")
        logger.info(f"Session started: {session_id}")
        return session

    async def pause_session(self, session_id: str) -> SessionInfo:
        session = self._require_session(session_id)
        self._check_transition(session, SessionStatus.PAUSED)
        session.status = SessionStatus.PAUSED
        if self._store:
            await self._store.save_session(session)
        await publish_event(EventType.SESSION_PAUSED, data={"session_id": session_id}, source="session_manager")
        logger.info(f"Session paused: {session_id}")
        return session

    async def resume_session(self, session_id: str) -> SessionInfo:
        session = self._require_session(session_id)
        self._check_transition(session, SessionStatus.RECORDING)
        session.status = SessionStatus.RECORDING
        if self._store:
            await self._store.save_session(session)
        await publish_event(EventType.SESSION_RESUMED, data={"session_id": session_id}, source="session_manager")
        logger.info(f"Session resumed: {session_id}")
        return session

    async def end_session(self, session_id: str) -> SessionInfo:
        session = self._require_session(session_id)
        self._check_transition(session, SessionStatus.COMPLETED)
        session.status = SessionStatus.COMPLETED
        session.ended_at = _iso_now()

        if session.started_at:
            from datetime import datetime, timezone
            started = datetime.fromisoformat(session.started_at.replace("Z", "+00:00"))
            ended = datetime.fromisoformat(session.ended_at.replace("Z", "+00:00"))
            session.duration_seconds = (ended - started).total_seconds()

        if self._store:
            await self._store.save_session(session)
        await publish_event(
            EventType.SESSION_ENDED,
            data={"session_id": session_id, "duration": session.duration_seconds},
            source="session_manager",
        )
        logger.info(f"Session ended: {session_id}")
        return session

    async def update_session(self, session_id: str, title: str | None = None, participants: list[str] | None = None) -> SessionInfo:
        session = self._sessions.get(session_id)
        if session is None and self._store:
            session = await self._store.load_session(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")
        if title is not None:
            session.title = title
        if participants is not None:
            session.participants = participants
        if self._store:
            await self._store.save_session(session)
        return session

    def get_session(self, session_id: str) -> SessionInfo | None:
        return self._sessions.get(session_id)

    async def get_session_or_disk(self, session_id: str) -> SessionInfo | None:
        session = self._sessions.get(session_id)
        if session is not None:
            return session
        if self._store:
            return await self._store.load_session(session_id)
        return None

    async def preload_from_disk(self) -> None:
        if not self._store:
            return
        disk_sessions = await self._store.list_sessions()
        count = 0
        for s in disk_sessions:
            if s.id not in self._sessions:
                self._sessions[s.id] = s
                count += 1
        if count:
            logger.info(f"Preloaded {count} sessions from disk")

    async def list_all_sessions(self) -> list[SessionInfo]:
        result = list(self._sessions.values())
        result.sort(key=lambda s: s.started_at or "", reverse=True)
        return result

    async def delete_session(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session and session.status in (SessionStatus.RECORDING, SessionStatus.PAUSED, SessionStatus.IDLE):
            try:
                await self.end_session(session_id)
            except Exception:
                pass
        self._sessions.pop(session_id, None)
        if self._store:
            await self._store.delete_session(session_id)

    async def close_all(self) -> None:
        active_ids = [
            sid for sid, s in self._sessions.items()
            if s.status in (SessionStatus.RECORDING, SessionStatus.PAUSED, SessionStatus.IDLE)
        ]
        for sid in active_ids:
            try:
                await self.end_session(sid)
            except Exception as exc:
                logger.error(f"Error ending session {sid}: {exc}")

    def _require_session(self, session_id: str) -> SessionInfo:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")
        return session
