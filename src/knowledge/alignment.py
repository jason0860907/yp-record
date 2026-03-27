"""Alignment orchestration — forced alignment + optional diarization."""
from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, List

from src.infra.models import AlignmentResult, EnrichedTranscriptSegment
from src.infra.events import Event, EventBus, EventType
from src.infra.logging import get_logger

if TYPE_CHECKING:
    from src.recording.audio.diarization import DiarizationService, SpeakerSegment
    from src.recording.audio.forced_aligner import ForcedAlignmentService
    from src.recording.store import RecordingSessionStore

logger = get_logger(__name__)


async def run_alignment(
    session_id: str,
    store: "RecordingSessionStore",
    aligner: "ForcedAlignmentService",
    event_bus: EventBus,
    language: str = "zh",
    sample_rate: int = 16000,
    diarization_service: "DiarizationService | None" = None,
) -> None:
    """Run forced alignment (+ optional diarization) for a session."""
    wav_path = store.get_audio_wav_path(session_id)
    raw_path = store.get_audio_raw_path(session_id)

    # Ensure WAV exists
    if not wav_path.exists():
        if not raw_path.exists():
            logger.warning(f"No audio found for session {session_id}, skipping alignment")
            return
        try:
            meta = await store.load_audio_meta(session_id)
            channels = meta["channels"] if meta else await store.detect_audio_channels(session_id)
            wav_path = await store.raw_to_wav(session_id, sample_rate=sample_rate, channels=channels)
        except Exception as e:
            logger.error(f"Failed to create WAV for {session_id}: {e}")
            return

    await event_bus.publish(Event(
        type=EventType.ALIGNMENT_STARTED,
        data={"session_id": session_id},
        source="alignment",
    ))
    await store.save_alignment_result(session_id, AlignmentResult(session_id=session_id, status="processing"))

    t0 = time.monotonic()
    try:
        segments_raw = await store.load_segments(session_id)
        full_text = "".join(seg.text for seg in segments_raw)
        if not full_text.strip():
            await _fail(store, event_bus, session_id, "No transcript text available", t0)
            return

        has_timestamps = any(seg.end_time > seg.start_time for seg in segments_raw)
        if has_timestamps:
            aligned = await aligner.align_chunked(wav_path, segments_raw, language)
        else:
            aligned = await aligner.align(wav_path, full_text, language)

        if diarization_service:
            await asyncio.to_thread(aligner.offload_to_cpu)
            speaker_segs = await diarization_service.diarize(wav_path)
            await asyncio.to_thread(aligner.restore_to_gpu)
            aligned = _split_and_assign_speakers(aligned, speaker_segs)

        num_speakers = len({seg.speaker for seg in aligned if seg.speaker})
        result = AlignmentResult(
            session_id=session_id,
            status="completed",
            language=language,
            segments=aligned,
            num_speakers=num_speakers,
            processing_time_seconds=round(time.monotonic() - t0, 2),
        )
        await store.save_alignment_result(session_id, result)
        await event_bus.publish(Event(
            type=EventType.ALIGNMENT_COMPLETED,
            data={"session_id": session_id, "num_segments": len(aligned), "num_speakers": num_speakers},
            source="alignment",
        ))
        logger.info(f"Alignment completed for {session_id}: {len(aligned)} segments, {num_speakers} speakers")

    except Exception as e:
        logger.error(f"Alignment error for {session_id}: {e}")
        await _fail(store, event_bus, session_id, str(e), t0)


async def _fail(
    store: "RecordingSessionStore",
    event_bus: EventBus,
    session_id: str,
    error: str,
    t0: float,
) -> None:
    failed = AlignmentResult(
        session_id=session_id,
        status="failed",
        error=error,
        processing_time_seconds=round(time.monotonic() - t0, 2),
    )
    await store.save_alignment_result(session_id, failed)
    await event_bus.publish(Event(
        type=EventType.ALIGNMENT_FAILED,
        data={"session_id": session_id, "error": error},
        source="alignment",
    ))


def _split_and_assign_speakers(
    segments: List[EnrichedTranscriptSegment],
    speaker_segs: List["SpeakerSegment"],
) -> List[EnrichedTranscriptSegment]:
    """Split segments at speaker boundaries and assign speaker labels."""
    result: List[EnrichedTranscriptSegment] = []

    for seg in segments:
        overlapping = [sp for sp in speaker_segs if sp.end > seg.start and sp.start < seg.end]

        if len(overlapping) <= 1:
            seg.speaker = overlapping[0].speaker if overlapping else None
            result.append(seg)
            continue

        def _speaker_at(t: float) -> str | None:
            for sp in overlapping:
                if sp.start <= t < sp.end:
                    return sp.speaker
            return min(overlapping, key=lambda s: min(abs(s.start - t), abs(s.end - t))).speaker

        groups: list[tuple] = []
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
