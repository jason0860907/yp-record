"""Recording event pipeline with transcript extraction."""
from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Callable, Dict, List

from src.models import AlignmentResult, EnrichedTranscriptSegment, TranscriptSegment
from src.events import Event, EventBus, EventType
from src.logging import get_logger

if TYPE_CHECKING:
    from src.audio.diarization import DiarizationService, SpeakerSegment
    from src.audio.forced_aligner import ForcedAlignmentService
    from src.extractor import KnowledgeExtractor
    from src.manager import RecordingSessionManager
    from src.store import RecordingSessionStore

logger = get_logger(__name__)


def _split_and_assign_speakers(
    segments: List[EnrichedTranscriptSegment],
    speaker_segs: List["SpeakerSegment"],
) -> List[EnrichedTranscriptSegment]:
    """Split segments at speaker boundaries and assign speaker labels."""
    result: List[EnrichedTranscriptSegment] = []

    for seg in segments:
        overlapping = [
            sp for sp in speaker_segs
            if sp.end > seg.start and sp.start < seg.end
        ]

        if len(overlapping) <= 1:
            seg.speaker = overlapping[0].speaker if overlapping else None
            result.append(seg)
            continue

        def _speaker_at(t: float) -> "str | None":
            for sp in overlapping:
                if sp.start <= t < sp.end:
                    return sp.speaker
            return min(overlapping, key=lambda s: min(abs(s.start - t), abs(s.end - t))).speaker

        groups: List[tuple] = []
        for word in seg.words:
            spk = _speaker_at((word.start + word.end) / 2)
            if groups and groups[-1][0] == spk:
                groups[-1][1].append(word)
            else:
                groups.append((spk, [word]))

        for spk, words in groups:
            text = "".join(w.word for w in words)
            result.append(EnrichedTranscriptSegment(
                text=text,
                start=words[0].start,
                end=words[-1].end,
                speaker=spk,
                words=words,
                language=seg.language,
            ))

    return result


class RecordingPipeline:
    """Manages recording event bus subscriptions."""

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
        self._aligner_auto_on_session_end = aligner_auto_on_session_end
        self._diarization_enabled = diarization_enabled
        self._extract_auto = extract_auto_on_session_end
        self._sample_rate = sample_rate
        self._alignment_locks: dict[str, asyncio.Lock] = {}
        self._session_segments: Dict[str, List[TranscriptSegment]] = {}
        self._handlers: List[tuple] = []

    def wire(self) -> None:
        """Subscribe to all recording events."""

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
            # Accumulate for extraction
            if self._extractor:
                self._session_segments.setdefault(session_id, []).append(segment)

        self._subscribe(EventType.TRANSCRIPT_SEGMENT, _on_transcript_segment)

        async def _on_session_ended(event: Event) -> None:
            session_id = event.data.get("session_id", "")
            if not session_id:
                return

            # Convert raw → wav
            if self._store:
                raw_path = self._store.get_audio_raw_path(session_id)
                if raw_path.exists():
                    try:
                        meta = await self._store.load_audio_meta(session_id)
                        channels = meta["channels"] if meta else await self._store.detect_audio_channels(session_id)
                        await self._store.raw_to_wav(session_id, sample_rate=self._sample_rate, channels=channels)
                        logger.info(f"Converted audio.raw → audio.wav for session {session_id}")
                    except Exception as e:
                        logger.warning(f"Failed to convert raw→wav for {session_id}: {e}")

            # Auto-trigger alignment
            if (
                self._forced_aligner
                and self._aligner_auto_on_session_end
                and self._store
            ):
                asyncio.create_task(self._run_alignment(session_id))

            # Auto-trigger extraction (transcript polish + meeting note)
            if self._extractor and self._extract_auto:
                asyncio.create_task(self._run_extraction(session_id))

        self._subscribe(EventType.SESSION_ENDED, _on_session_ended)
        logger.info("Recording pipeline wired")

    def unwire(self) -> None:
        for event_type, handler in self._handlers:
            self._event_bus.unsubscribe(event_type, handler)
        self._handlers.clear()

    async def trigger_alignment(self, session_id: str) -> None:
        if not self._forced_aligner or not self._store:
            raise RuntimeError("ForcedAlignmentService or session store not available")
        await self._run_alignment(session_id)

    async def trigger_extract(self, session_id: str) -> None:
        """Manually trigger transcript polish + meeting note generation."""
        if not self._extractor or not self._store:
            raise RuntimeError("Extractor or session store not available")
        await self._run_extraction(session_id)

    def _get_alignment_lock(self, session_id: str) -> asyncio.Lock:
        if session_id not in self._alignment_locks:
            self._alignment_locks[session_id] = asyncio.Lock()
        return self._alignment_locks[session_id]

    async def _run_alignment(self, session_id: str) -> None:
        async with self._get_alignment_lock(session_id):
            await self._do_alignment(session_id)

    async def _do_alignment(self, session_id: str) -> None:
        store = self._store
        wav_path = store.get_audio_wav_path(session_id)
        raw_path = store.get_audio_raw_path(session_id)

        if not wav_path.exists():
            if not raw_path.exists():
                logger.warning(f"No audio found for session {session_id}, skipping alignment")
                return
            try:
                meta = await store.load_audio_meta(session_id)
                channels = meta["channels"] if meta else await store.detect_audio_channels(session_id)
                wav_path = await store.raw_to_wav(session_id, sample_rate=self._sample_rate, channels=channels)
            except Exception as e:
                logger.error(f"Failed to create WAV for {session_id}: {e}")
                return

        await self._event_bus.publish(Event(
            type=EventType.ALIGNMENT_STARTED,
            data={"session_id": session_id},
            source="recording_pipeline",
        ))

        pending = AlignmentResult(session_id=session_id, status="processing")
        await store.save_alignment_result(session_id, pending)

        t0 = time.monotonic()
        try:
            segments_raw = await store.load_segments(session_id)
            full_text = "".join(seg.text for seg in segments_raw)
            if not full_text.strip():
                failed = AlignmentResult(
                    session_id=session_id,
                    status="failed",
                    error="No transcript text available",
                    processing_time_seconds=round(time.monotonic() - t0, 2),
                )
                await store.save_alignment_result(session_id, failed)
                await self._event_bus.publish(Event(
                    type=EventType.ALIGNMENT_FAILED,
                    data={"session_id": session_id, "error": failed.error},
                    source="recording_pipeline",
                ))
                return

            has_timestamps = any(seg.end_time > seg.start_time for seg in segments_raw)
            if has_timestamps:
                aligned_segments = await self._forced_aligner.align_chunked(wav_path, segments_raw, self._aligner_language)
            else:
                aligned_segments = await self._forced_aligner.align(wav_path, full_text, self._aligner_language)

            if self._diarization_enabled and self._diarization_service:
                await asyncio.to_thread(self._forced_aligner.offload_to_cpu)
                speaker_segs = await self._diarization_service.diarize(wav_path)
                await asyncio.to_thread(self._forced_aligner.restore_to_gpu)
                aligned_segments = _split_and_assign_speakers(aligned_segments, speaker_segs)

            num_speakers = len({seg.speaker for seg in aligned_segments if seg.speaker})

            result = AlignmentResult(
                session_id=session_id,
                status="completed",
                language=self._aligner_language,
                segments=aligned_segments,
                num_speakers=num_speakers,
                processing_time_seconds=round(time.monotonic() - t0, 2),
            )
            await store.save_alignment_result(session_id, result)

            await self._event_bus.publish(Event(
                type=EventType.ALIGNMENT_COMPLETED,
                data={
                    "session_id": session_id,
                    "num_segments": len(result.segments),
                    "num_speakers": result.num_speakers,
                },
                source="recording_pipeline",
            ))
            logger.info(f"Alignment completed for {session_id}: {len(result.segments)} segments, {num_speakers} speakers")

        except Exception as e:
            logger.error(f"Alignment pipeline error for {session_id}: {e}")
            failed = AlignmentResult(
                session_id=session_id,
                status="failed",
                error=str(e),
                processing_time_seconds=round(time.monotonic() - t0, 2),
            )
            await store.save_alignment_result(session_id, failed)
            await self._event_bus.publish(Event(
                type=EventType.ALIGNMENT_FAILED,
                data={"session_id": session_id, "error": str(e)},
                source="recording_pipeline",
            ))

    # ------------------------------------------------------------------
    # Extraction (transcript polish + meeting note)
    # ------------------------------------------------------------------

    async def _run_extraction(self, session_id: str) -> None:
        """Polish transcript and generate meeting note for a session."""
        from src.extractor import format_segments

        store = self._store
        extractor = self._extractor

        # Use accumulated segments or load from disk
        segments = self._session_segments.pop(session_id, None)
        if not segments and store:
            segments = await store.load_segments(session_id)
        if not segments:
            logger.debug(f"No segments for session '{session_id}', skipping extraction")
            return

        raw_text = format_segments(segments)
        logger.info(f"Running extraction for session '{session_id}' ({len(segments)} segments)")

        try:
            # Step 1: Polish transcript
            polished = await extractor.polish_transcript(raw_text)
            if polished and store:
                await store.save_polished_transcript(session_id, polished)

            # Step 2: Generate meeting note
            transcript_for_note = polished or raw_text
            session_info = await store.load_session(session_id) if store else None
            page = await extractor.generate_session_note(
                transcript=transcript_for_note,
                session_info=session_info,
            )
            if page is None:
                logger.warning(f"Meeting note generation returned None for '{session_id}'")
                return

            page.session_id = session_id

            # Save meeting note locally
            if store:
                await store.save_meeting_note(session_id, page)

            # Append full transcript to page content for Notion export
            page.content += f"\n\n---\n\n# 完整逐字稿\n\n{transcript_for_note}"

            # Publish event for downstream consumers (e.g., auto Notion export)
            await self._event_bus.publish(Event(
                type=EventType.KNOWLEDGE_EXTRACTED,
                data={"page": page.model_dump(), "session_id": session_id},
                source="recording_pipeline",
            ))
            logger.info(f"Extraction completed for '{session_id}': '{page.title}'")

        except Exception as e:
            logger.error(f"Extraction failed for session '{session_id}': {e}")

    def _subscribe(self, event_type: EventType, handler: Callable) -> None:
        self._event_bus.subscribe(event_type, handler)
        self._handlers.append((event_type, handler))
