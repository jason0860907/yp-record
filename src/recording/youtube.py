"""YouTube video import — subtitle-first, fallback to ASR."""
from __future__ import annotations

import asyncio
import json
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

from src.infra.events import EventType, publish_event
from src.infra.models import TranscriptSegment
from src.infra.logging import get_logger

if TYPE_CHECKING:
    from src.recording.audio.qwen_asr_stt import QwenASRSTT
    from src.recording.store import RecordingSessionStore

logger = get_logger(__name__)

# Preferred subtitle languages, in priority order
_SUBTITLE_LANGS = ["zh-TW", "zh-Hant", "zh-CN", "zh-Hans", "zh", "en"]


class YouTubeImporter:
    """Import YouTube videos: grab subtitles if available, otherwise download audio + ASR."""

    def __init__(
        self,
        stt_engine: "QwenASRSTT",
        store: "RecordingSessionStore",
        sample_rate: int = 16000,
        chunk_seconds: float = 10.0,
    ) -> None:
        self._stt = stt_engine
        self._store = store
        self._sample_rate = sample_rate
        self._chunk_seconds = chunk_seconds

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    async def extract_info(self, url: str) -> dict:
        """Validate URL and return video metadata."""
        import yt_dlp

        def _extract():
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                return ydl.extract_info(url, download=False)

        return await asyncio.to_thread(_extract)

    async def import_video(self, url: str, session_id: str) -> None:
        """Full import pipeline — subtitle-first with audio fallback."""
        try:
            # 1. Extract info
            logger.info(f"[{session_id}] Extracting info: {url}")
            await publish_event(
                EventType.YOUTUBE_DOWNLOAD_STARTED,
                {"session_id": session_id, "url": url},
                source="youtube_importer",
            )

            info = await self.extract_info(url)
            video_title = info.get("title", "YouTube Import")
            video_duration = info.get("duration", 0) or 0

            # Update session title
            session = await self._store.load_session(session_id)
            if session and not session.title:
                session.title = video_title
                await self._store.save_session(session)

            # 2. Try subtitles first
            sub_segments = self._find_subtitles(info)

            if sub_segments:
                logger.info(
                    f"[{session_id}] Found {len(sub_segments)} subtitle segments, "
                    "skipping ASR"
                )
                await self._emit_subtitle_segments(session_id, sub_segments)

                # Download audio in background (for alignment / diarization)
                self._store._ensure_dir(session_id)
                audio_task = asyncio.create_task(
                    self._download_audio_async(url, session_id)
                )

                await publish_event(
                    EventType.YOUTUBE_DOWNLOAD_COMPLETED,
                    {"session_id": session_id},
                    source="youtube_importer",
                )

                # Wait for audio before triggering alignment
                await audio_task
            else:
                # 3. No subtitles — fallback to audio + ASR
                logger.info(f"[{session_id}] No subtitles, falling back to ASR")
                await self._audio_asr_pipeline(url, session_id)

            # 4. Trigger downstream (alignment + extraction)
            logger.info(f"[{session_id}] Import done, triggering post-processing")
            await publish_event(
                EventType.SESSION_ENDED,
                {"session_id": session_id, "duration": video_duration},
                source="youtube_importer",
            )

        except Exception as exc:
            logger.error(f"[{session_id}] YouTube import failed: {exc}")
            await publish_event(
                EventType.YOUTUBE_DOWNLOAD_FAILED,
                {"session_id": session_id, "error": str(exc)},
                source="youtube_importer",
            )
            raise

    # ------------------------------------------------------------------
    # Subtitle path
    # ------------------------------------------------------------------

    def _find_subtitles(self, info: dict) -> list[dict] | None:
        """Return parsed json3 subtitle events, or None if unavailable.

        Priority: manual subtitles > auto captions, preferred languages first.
        """
        for source_key in ("subtitles", "automatic_captions"):
            subs = info.get(source_key) or {}
            for lang in _SUBTITLE_LANGS:
                formats = subs.get(lang, [])
                for fmt in formats:
                    if fmt.get("ext") == "json3":
                        try:
                            data = self._fetch_json3(fmt["url"])
                            events = data.get("events", [])
                            if events:
                                logger.info(
                                    f"Using {source_key}/{lang}: "
                                    f"{len(events)} events"
                                )
                                return events
                        except Exception as exc:
                            logger.warning(
                                f"Failed to fetch {source_key}/{lang}: {exc}"
                            )
        return None

    @staticmethod
    def _fetch_json3(url: str) -> dict:
        """Download and parse a json3 subtitle file."""
        with urllib.request.urlopen(url, timeout=15) as resp:
            return json.loads(resp.read())

    @staticmethod
    def _json3_to_segments(events: list[dict]) -> list[TranscriptSegment]:
        """Convert YouTube json3 events to TranscriptSegments."""
        segments: list[TranscriptSegment] = []
        for ev in events:
            segs = ev.get("segs")
            if not segs:
                continue
            text = "".join(s.get("utf8", "") for s in segs).strip()
            if not text:
                continue
            start_ms = ev.get("tStartMs", 0)
            dur_ms = ev.get("dDurationMs", 0)
            segments.append(
                TranscriptSegment(
                    text=text,
                    speaker="other",
                    channel=0,
                    start_time=start_ms / 1000.0,
                    end_time=(start_ms + dur_ms) / 1000.0,
                    language="zh",
                )
            )
        return segments

    async def _emit_subtitle_segments(
        self, session_id: str, events: list[dict]
    ) -> None:
        """Convert json3 events to TranscriptSegments and publish them."""
        segments = self._json3_to_segments(events)
        total = len(segments)
        for i, seg in enumerate(segments):
            await publish_event(
                EventType.TRANSCRIPT_SEGMENT,
                {"session_id": session_id, "segment": seg.model_dump()},
                source="youtube_importer",
            )
            # Emit progress every 10 segments to avoid flooding
            if (i + 1) % 10 == 0 or i + 1 == total:
                await publish_event(
                    EventType.YOUTUBE_TRANSCRIPTION_PROGRESS,
                    {
                        "session_id": session_id,
                        "current_chunk": i + 1,
                        "total_chunks": total,
                    },
                    source="youtube_importer",
                )

    # ------------------------------------------------------------------
    # Audio + ASR fallback path
    # ------------------------------------------------------------------

    async def _audio_asr_pipeline(self, url: str, session_id: str) -> None:
        """Download audio then chunk-and-transcribe via ASR."""
        self._store._ensure_dir(session_id)
        await self._download_audio_async(url, session_id)

        await publish_event(
            EventType.YOUTUBE_DOWNLOAD_COMPLETED,
            {"session_id": session_id},
            source="youtube_importer",
        )
        logger.info(f"[{session_id}] Audio download completed, starting ASR")

        # Chunk and transcribe
        chunks = await self._store.read_wav_mono_chunks(
            session_id, self._chunk_seconds
        )
        total_chunks = len(chunks)

        for i, (pcm, start_time, end_time, sr) in enumerate(chunks):
            segments = await self._stt.transcribe_chunk(
                pcm, channel=0, sample_rate=sr
            )
            for seg in segments:
                seg.start_time = start_time
                seg.end_time = end_time
                seg.speaker = "other"
                await publish_event(
                    EventType.TRANSCRIPT_SEGMENT,
                    {"session_id": session_id, "segment": seg.model_dump()},
                    source="youtube_importer",
                )

            await publish_event(
                EventType.YOUTUBE_TRANSCRIPTION_PROGRESS,
                {
                    "session_id": session_id,
                    "current_chunk": i + 1,
                    "total_chunks": total_chunks,
                },
                source="youtube_importer",
            )

    # ------------------------------------------------------------------
    # Audio download (shared by both paths)
    # ------------------------------------------------------------------

    async def _download_audio_async(self, url: str, session_id: str) -> None:
        """Download audio as 16kHz mono WAV."""
        wav_path = self._store.get_audio_wav_path(session_id)
        loop = asyncio.get_running_loop()
        await asyncio.to_thread(
            self._download_audio, url, wav_path, session_id, loop
        )
        await self._store.save_audio_meta(
            session_id, channels=1, sample_rate=self._sample_rate
        )

    def _download_audio(
        self,
        url: str,
        wav_path: Path,
        session_id: str,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Synchronous yt-dlp download — runs in a thread."""
        import yt_dlp

        def progress_hook(d: dict) -> None:
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes", 0)
                percent = (downloaded / total * 100) if total else 0
                asyncio.run_coroutine_threadsafe(
                    publish_event(
                        EventType.YOUTUBE_DOWNLOAD_PROGRESS,
                        {
                            "session_id": session_id,
                            "percent": round(percent, 1),
                            "status": "downloading",
                        },
                        source="youtube_importer",
                    ),
                    loop,
                )

        outtmpl = str(wav_path).replace(".wav", ".%(ext)s")
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "wav"}
            ],
            "postprocessor_args": ["-ar", str(self._sample_rate), "-ac", "1"],
            "progress_hooks": [progress_hook],
            "quiet": True,
            "no_warnings": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
