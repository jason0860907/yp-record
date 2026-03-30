"""Recording service facade."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from src.infra.config import get_settings
from src.infra.events import get_event_bus
from src.infra.logging import get_logger, setup_logging
from src.infra.models import KnowledgePage, KnowledgeCategory, KnowledgeSource, KnowledgeStatus
from src.recording.store import RecordingSessionStore
from src.recording.manager import RecordingSessionManager
from src.recording.audio.qwen_asr_stt import QwenASRSTT
from src.recording.audio.forced_aligner import ForcedAlignmentService
from src.recording.audio.diarization import DiarizationService
from src.recording.pipeline import RecordingPipeline
from src.knowledge.notion import NotionKB
from src.knowledge.extractor import KnowledgeExtractor

logger = get_logger(__name__)


class RecordingService:
    """Top-level service that assembles and manages all subsystems."""

    def __init__(self) -> None:
        settings = get_settings()
        setup_logging()

        self._settings = settings
        self.event_bus = get_event_bus()
        self.session_store = RecordingSessionStore(base_dir=settings.storage_dir)
        self.session_manager = RecordingSessionManager(store=self.session_store)

        self.stt_engine = QwenASRSTT(
            base_url=settings.asr_base_url,
            model=settings.asr_model,
            timeout=settings.asr_timeout,
        )

        self.forced_aligner: ForcedAlignmentService | None = None
        if settings.aligner_enabled:
            self.forced_aligner = ForcedAlignmentService(
                model=settings.aligner_model,
                device=settings.aligner_device,
            )

        self.diarization_service: DiarizationService | None = None
        if settings.diarization_enabled:
            self.diarization_service = DiarizationService(
                hf_token=settings.diarization_hf_token,
                device=settings.diarization_device,
                min_speakers=settings.diarization_min_speakers,
                max_speakers=settings.diarization_max_speakers,
            )

        self._extractor: KnowledgeExtractor | None = None
        if settings.extract_enabled:
            from src.knowledge.llm import LLMClient as ExtractLLM
            llm = ExtractLLM(
                base_url=settings.extract_base_url,
                model=settings.extract_model,
                api_key=settings.extract_api_key,
                temperature=settings.extract_temperature,
                timeout=settings.extract_timeout,
            )
            self._extractor = KnowledgeExtractor(llm)

        self.pipeline = RecordingPipeline(
            event_bus=self.event_bus,
            session_store=self.session_store,
            session_manager=self.session_manager,
            forced_aligner=self.forced_aligner,
            diarization_service=self.diarization_service,
            extractor=self._extractor,
            aligner_language=settings.aligner_language,
            aligner_auto_on_session_end=settings.aligner_auto_on_session_end,
            diarization_enabled=settings.diarization_enabled,
            extract_auto_on_session_end=settings.extract_auto_on_session_end,
            sample_rate=settings.sample_rate,
        )

        self._notion: NotionKB | None = None
        if settings.notion_api_key and settings.notion_database_id:
            try:
                self._notion = NotionKB(
                    database_id=settings.notion_database_id,
                    api_key=settings.notion_api_key,
                )
            except ValueError as e:
                logger.warning(f"Notion not configured: {e}")

    async def start(self) -> None:
        self.pipeline.wire()
        await self.session_manager.preload_from_disk()
        logger.info("RecordingService started")

    async def close(self) -> None:
        self.pipeline.unwire()
        await self.session_manager.close_all()
        await self.stt_engine.close()
        if self.forced_aligner:
            await self.forced_aligner.close()
        if self.diarization_service:
            await self.diarization_service.close()
        if self._extractor:
            await self._extractor.close()
        if self._notion:
            await self._notion.close()
        logger.info("RecordingService closed")

    def create_audio_receiver(self, channels: int, session_id: str):
        """Create an AudioReceiver for a session."""
        from src.recording.audio.receiver import AudioReceiver
        settings = self._settings
        audio_save_path = Path(settings.storage_dir) / session_id / "audio.raw"
        return AudioReceiver(
            stt_engine=self.stt_engine,
            buffer_seconds=settings.buffer_seconds,
            sample_rate=settings.sample_rate,
            channels=channels,
            audio_save_path=audio_save_path,
        )

    async def trigger_alignment(self, session_id: str) -> None:
        await self.pipeline.trigger_alignment(session_id)

    async def trigger_extract(self, session_id: str) -> None:
        """Re-run transcript polishing and meeting note generation."""
        await self.pipeline.trigger_extract(session_id)

    async def import_youtube(self, url: str, session_id: str) -> None:
        """Download YouTube audio and run through the ASR pipeline."""
        from src.recording.youtube import YouTubeImporter

        importer = YouTubeImporter(
            stt_engine=self.stt_engine,
            store=self.session_store,
            sample_rate=self._settings.sample_rate,
            chunk_seconds=self._settings.buffer_seconds,
        )
        try:
            await importer.import_video(url, session_id)
            await self.session_manager.complete_processing(session_id)
        except Exception:
            await self.session_manager.fail_processing(session_id, error=str(url))

    @property
    def extract_enabled(self) -> bool:
        return self._extractor is not None

    async def export_to_notion(self, session_id: str) -> str:
        """Export session to Notion. Prefers meeting note if available, falls back to raw transcript."""
        if not self._notion:
            raise RuntimeError("Notion is not configured. Set NOTION_API_KEY and NOTION_DATABASE_ID.")

        session = await self.session_manager.get_session_or_disk(session_id)
        if not session:
            raise KeyError(f"Session not found: {session_id}")

        # Prefer meeting note (from extraction) if available
        meeting_note = await self.session_store.load_meeting_note(session_id)

        # If no meeting note yet but extraction is available, run it now
        if not meeting_note and self._extractor:
            await self.pipeline.trigger_extract(session_id)
            meeting_note = await self.session_store.load_meeting_note(session_id)

        if meeting_note:
            meeting_note.status = KnowledgeStatus.PUBLISHED
            meeting_note.participants = session.participants
            # Append polished transcript
            polished = await self.session_store.load_polished_transcript(session_id)
            if polished:
                meeting_note.content += f"\n\n---\n\n# 完整逐字稿\n\n{polished}"
            return await self._notion.create_page(meeting_note)

        # Fallback: build content from alignment or raw segments
        segments = await self.session_store.load_segments(session_id)
        alignment = await self.session_store.load_alignment_result(session_id)

        lines = []
        upload_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        if session.started_at:
            lines.append(f"**Recorded:** {session.started_at}")
        lines.append(f"**Uploaded:** {upload_time}\n")
        if alignment and alignment.status == "completed" and alignment.segments:
            lines.append("## Transcript\n")
            for seg in alignment.segments:
                speaker_label = seg.speaker or "Unknown"
                ts = f"{int(seg.start // 60):02d}:{seg.start % 60:04.1f}"
                lines.append(f"**[{speaker_label} {ts}]** {seg.text}")
        elif segments:
            lines.append("## Transcript\n")
            for seg in segments:
                speaker_label = "Mic" if seg.channel == 0 else "Tab"
                lines.append(f"**[{speaker_label}]** {seg.text}")

        content = "\n".join(lines)

        title = session.title or f"Recording {session.started_at or session_id[:8]}"
        page = KnowledgePage(
            title=title,
            content=content,
            category=KnowledgeCategory.MEETING_NOTES,
            source=KnowledgeSource.MEETING,
            session_id=session_id,
            participants=session.participants,
            status=KnowledgeStatus.PUBLISHED,
        )

        return await self._notion.create_page(page)

    @property
    def notion_enabled(self) -> bool:
        return self._notion is not None

    async def save_audio_meta(self, session_id: str, channels: int) -> None:
        await self.session_store.save_audio_meta(session_id, channels, self._settings.sample_rate)


# Module-level singleton
_service: RecordingService | None = None


def get_service() -> RecordingService:
    global _service
    if _service is None:
        _service = RecordingService()
    return _service
