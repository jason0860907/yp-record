"""Recording event pipeline — thin wiring layer that delegates to specialists."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Callable, Dict, List

from src.models import TranscriptSegment
from src.events import Event, EventBus, EventType
from src.logging import get_logger

if TYPE_CHECKING:
    from src.audio.diarization import DiarizationService
    from src.audio.forced_aligner import ForcedAlignmentService
    from src.extractor import KnowledgeExtractor
    from src.manager import RecordingSessionManager
    from src.store import RecordingSessionStore

logger = get_logger(__name__)


class RecordingPipeline:
    """Subscribes to recording events and delegates to alignment / extraction modules."""

    def __init__(
        self,
        event_bus: EventBus,
        session_store: "RecordingSessionStore | None" = None,
        session_manager: "RecordingSessionManager | None" = None,
        forced_aligner: "ForcedAlignmentService | None" = None,
        diarization_service: "DiarizationService | None" = None,
        extractor: "KnowledgeExtractor | None" = None,
        aligner_language: str = "zh",
        aligner_auto_on_session_end: bool = True,
        diarization_enabled: bool = True,
        extract_auto_on_session_end: bool = True,
        sample_rate: int = 16000,
    ) -> None:
        self._event_bus = event_bus
        self._store = session_store
        self._manager = session_manager
        self._forced_aligner = forced_aligner
        self._diarization_service = diarization_service
        self._extractor = extractor
        self._aligner_language = aligner_language
        self._aligner_auto = aligner_auto_on_session_end
        self._diarization_enabled = diarization_enabled
        self._extract_auto = extract_auto_on_session_end
        self._sample_rate = sample_rate
        self._alignment_locks: dict[str, asyncio.Lock] = {}
        self._session_segments: Dict[str, List[TranscriptSegment]] = {}
        self._handlers: List[tuple] = []

    # ------------------------------------------------------------------
    # Event wiring
    # ------------------------------------------------------------------

    def wire(self) -> None:
        async def _on_transcript_segment(event: Event) -> None:
            segment_data = event.data.get("segment", {})
            session_id = event.data.get("session_id", "")
            if not session_id or not segment_data:
                return
            segment = TranscriptSegment.model_validate(segment_data)
            if self._store:
                await self._store.append_segment(session_id, segment)
            if self._manager:
                session = self._manager.get_session(session_id)
                if session:
                    session.segment_count += 1
            if self._extractor:
                self._session_segments.setdefault(session_id, []).append(segment)

        self._subscribe(EventType.TRANSCRIPT_SEGMENT, _on_transcript_segment)

        async def _on_session_ended(event: Event) -> None:
            session_id = event.data.get("session_id", "")
            if not session_id:
                return
            await self._convert_raw_to_wav(session_id)
            if self._forced_aligner and self._aligner_auto and self._store:
                asyncio.create_task(self._run_alignment(session_id))
            if self._extractor and self._extract_auto:
                asyncio.create_task(self._run_extraction(session_id))

        self._subscribe(EventType.SESSION_ENDED, _on_session_ended)
        logger.info("Recording pipeline wired")

    def unwire(self) -> None:
        for event_type, handler in self._handlers:
            self._event_bus.unsubscribe(event_type, handler)
        self._handlers.clear()

    # ------------------------------------------------------------------
    # Public triggers (manual)
    # ------------------------------------------------------------------

    async def trigger_alignment(self, session_id: str) -> None:
        if not self._forced_aligner or not self._store:
            raise RuntimeError("ForcedAlignmentService or session store not available")
        await self._run_alignment(session_id)

    async def trigger_extract(self, session_id: str) -> None:
        if not self._extractor or not self._store:
            raise RuntimeError("Extractor or session store not available")
        await self._run_extraction(session_id)

    # ------------------------------------------------------------------
    # Internal — delegate to specialist modules
    # ------------------------------------------------------------------

    async def _convert_raw_to_wav(self, session_id: str) -> None:
        if not self._store:
            return
        raw_path = self._store.get_audio_raw_path(session_id)
        if not raw_path.exists():
            return
        try:
            meta = await self._store.load_audio_meta(session_id)
            channels = meta["channels"] if meta else await self._store.detect_audio_channels(session_id)
            await self._store.raw_to_wav(session_id, sample_rate=self._sample_rate, channels=channels)
            logger.info(f"Converted audio.raw → audio.wav for session {session_id}")
        except Exception as e:
            logger.warning(f"Failed to convert raw→wav for {session_id}: {e}")

    async def _run_alignment(self, session_id: str) -> None:
        from src.alignment import run_alignment

        lock = self._alignment_locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            await run_alignment(
                session_id=session_id,
                store=self._store,
                aligner=self._forced_aligner,
                event_bus=self._event_bus,
                language=self._aligner_language,
                sample_rate=self._sample_rate,
                diarization_service=(
                    self._diarization_service if self._diarization_enabled else None
                ),
            )

    async def _run_extraction(self, session_id: str) -> None:
        from src.extractor import run_extraction

        cached = self._session_segments.pop(session_id, None)
        await run_extraction(
            session_id=session_id,
            extractor=self._extractor,
            store=self._store,
            event_bus=self._event_bus,
            cached_segments=cached,
        )

    def _subscribe(self, event_type: EventType, handler: Callable) -> None:
        self._event_bus.subscribe(event_type, handler)
        self._handlers.append((event_type, handler))
