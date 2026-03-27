"""File-based session persistence."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List

from src.models import AlignmentResult, KnowledgePage, SessionInfo, TranscriptSegment
from src.logging import get_logger

logger = get_logger(__name__)


class RecordingSessionStore:
    """File-based session persistence under storage/sessions/."""

    def __init__(self, base_dir: str = "storage/sessions") -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    def _session_dir(self, session_id: str) -> Path:
        return self._base / session_id

    # ------------------------------------------------------------------
    # Session metadata
    # ------------------------------------------------------------------

    async def save_session(self, session: SessionInfo) -> None:
        def _write():
            d = self._session_dir(session.id)
            d.mkdir(parents=True, exist_ok=True)
            (d / "session.json").write_text(session.model_dump_json(indent=2))
        await asyncio.to_thread(_write)

    async def load_session(self, session_id: str) -> SessionInfo | None:
        path = self._session_dir(session_id) / "session.json"
        if not path.exists():
            return None
        try:
            raw = await asyncio.to_thread(path.read_text)
            return SessionInfo.model_validate_json(raw)
        except Exception as exc:
            logger.warning(f"Failed to load session {session_id}: {exc}")
            return None

    async def list_sessions(self) -> List[SessionInfo]:
        if not self._base.exists():
            return []
        dirs = sorted(d.name for d in self._base.iterdir() if d.is_dir())
        results = await asyncio.gather(*[self.load_session(name) for name in dirs])
        return [s for s in results if s is not None]

    async def delete_session(self, session_id: str) -> None:
        import shutil
        d = self._session_dir(session_id)
        if d.exists():
            await asyncio.to_thread(shutil.rmtree, d)
            logger.info(f"Deleted session store: {session_id}")

    # ------------------------------------------------------------------
    # Transcript segments
    # ------------------------------------------------------------------

    async def replace_segments(self, session_id: str, segments: List[TranscriptSegment]) -> None:
        def _write():
            d = self._session_dir(session_id)
            d.mkdir(parents=True, exist_ok=True)
            with open(d / "segments.jsonl", "w") as f:
                for seg in segments:
                    f.write(seg.model_dump_json() + "\n")
        await asyncio.to_thread(_write)

    async def append_segment(self, session_id: str, segment: TranscriptSegment) -> None:
        def _append():
            d = self._session_dir(session_id)
            d.mkdir(parents=True, exist_ok=True)
            with open(d / "segments.jsonl", "a") as f:
                f.write(segment.model_dump_json() + "\n")
        await asyncio.to_thread(_append)

    async def load_segments(self, session_id: str) -> List[TranscriptSegment]:
        path = self._session_dir(session_id) / "segments.jsonl"
        if not path.exists():
            return []
        def _read():
            segments: List[TranscriptSegment] = []
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        segments.append(TranscriptSegment.model_validate_json(line))
            return segments
        try:
            return await asyncio.to_thread(_read)
        except Exception as exc:
            logger.warning(f"Failed to load segments for {session_id}: {exc}")
            return []

    # ------------------------------------------------------------------
    # Audio metadata
    # ------------------------------------------------------------------

    async def save_audio_meta(self, session_id: str, channels: int, sample_rate: int) -> None:
        import json
        def _write():
            d = self._session_dir(session_id)
            d.mkdir(parents=True, exist_ok=True)
            (d / "audio_meta.json").write_text(json.dumps({
                "channels": channels, "sample_rate": sample_rate,
            }))
        await asyncio.to_thread(_write)

    async def load_audio_meta(self, session_id: str) -> dict | None:
        import json
        path = self._session_dir(session_id) / "audio_meta.json"
        if not path.exists():
            return None
        try:
            raw = await asyncio.to_thread(path.read_text)
            return json.loads(raw)
        except Exception:
            return None

    async def detect_audio_channels(self, session_id: str) -> int:
        raw_path = self.get_audio_raw_path(session_id)
        if not raw_path.exists():
            return 1
        session = await self.load_session(session_id)
        if not session or not session.duration_seconds or session.duration_seconds < 1:
            return 1
        bytes_per_sec = raw_path.stat().st_size / session.duration_seconds
        return 2 if bytes_per_sec > 48000 else 1

    # ------------------------------------------------------------------
    # Audio files
    # ------------------------------------------------------------------

    def get_audio_raw_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "audio.raw"

    def get_audio_wav_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "audio.wav"

    async def raw_to_wav(self, session_id: str, sample_rate: int = 16000, channels: int = 2) -> Path:
        import struct
        import wave

        raw_path = self.get_audio_raw_path(session_id)
        wav_path = self.get_audio_wav_path(session_id)

        def _convert():
            raw_data = raw_path.read_bytes()

            if channels == 2:
                samples = struct.unpack(f"<{len(raw_data) // 2}h", raw_data)
                mono = []
                for i in range(0, len(samples), 2):
                    if i + 1 < len(samples):
                        mono.append((samples[i] + samples[i + 1]) // 2)
                    else:
                        mono.append(samples[i])
                mono_data = struct.pack(f"<{len(mono)}h", *mono)
                out_channels = 1
            else:
                mono_data = raw_data
                out_channels = 1

            with wave.open(str(wav_path), "wb") as wf:
                wf.setnchannels(out_channels)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(mono_data)

            return wav_path

        return await asyncio.to_thread(_convert)

    async def read_wav_mono_chunks(
        self, session_id: str, chunk_seconds: float
    ) -> list[tuple[bytes, float, float, int]]:
        import struct
        import wave as wave_mod

        wav_path = self.get_audio_wav_path(session_id)

        def _read():
            result = []
            with wave_mod.open(str(wav_path), "rb") as wf:
                sr = wf.getframerate()
                n_ch = wf.getnchannels()
                chunk_frames = int(chunk_seconds * sr)
                t = 0.0
                while True:
                    frames = wf.readframes(chunk_frames)
                    if not frames:
                        break
                    samples = struct.unpack(f"<{len(frames) // 2}h", frames)
                    if n_ch > 1:
                        mono = []
                        for i in range(0, len(samples) - 1, n_ch):
                            mono.append((samples[i] + samples[i + 1]) // 2)
                        pcm = struct.pack(f"<{len(mono)}h", *mono)
                    else:
                        pcm = frames
                    dur = len(pcm) / (sr * 2)
                    result.append((pcm, t, t + dur, sr))
                    t += dur
            return result

        return await asyncio.to_thread(_read)

    # ------------------------------------------------------------------
    # Screenshots
    # ------------------------------------------------------------------

    def get_screenshots_dir(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "screenshots"

    async def save_screenshot(self, session_id: str, timestamp: float, image_bytes: bytes) -> str:
        def _write():
            d = self.get_screenshots_dir(session_id)
            d.mkdir(parents=True, exist_ok=True)
            filename = f"{int(timestamp * 1000):016d}.jpg"
            (d / filename).write_bytes(image_bytes)
            return filename
        return await asyncio.to_thread(_write)

    async def list_screenshots(self, session_id: str) -> List[dict]:
        d = self.get_screenshots_dir(session_id)
        if not d.exists():
            return []
        def _list():
            files = sorted(f.name for f in d.iterdir() if f.suffix == ".jpg")
            result = []
            for f in files:
                ts = int(f.replace(".jpg", "")) / 1000.0
                result.append({"filename": f, "timestamp": ts})
            return result
        return await asyncio.to_thread(_list)

    # ------------------------------------------------------------------
    # Polished transcript & meeting note
    # ------------------------------------------------------------------

    async def save_polished_transcript(self, session_id: str, text: str) -> None:
        def _write():
            d = self._session_dir(session_id)
            d.mkdir(parents=True, exist_ok=True)
            (d / "polished.txt").write_text(text, encoding="utf-8")
        await asyncio.to_thread(_write)

    async def load_polished_transcript(self, session_id: str) -> str | None:
        path = self._session_dir(session_id) / "polished.txt"
        if not path.exists():
            return None
        try:
            return await asyncio.to_thread(path.read_text, "utf-8")
        except Exception:
            return None

    async def save_meeting_note(self, session_id: str, page: KnowledgePage) -> None:
        def _write():
            d = self._session_dir(session_id)
            d.mkdir(parents=True, exist_ok=True)
            (d / "meeting_note.json").write_text(page.model_dump_json(indent=2))
        await asyncio.to_thread(_write)

    async def load_meeting_note(self, session_id: str) -> KnowledgePage | None:
        path = self._session_dir(session_id) / "meeting_note.json"
        if not path.exists():
            return None
        try:
            raw = await asyncio.to_thread(path.read_text)
            return KnowledgePage.model_validate_json(raw)
        except Exception as exc:
            logger.warning(f"Failed to load meeting note for {session_id}: {exc}")
            return None

    # ------------------------------------------------------------------
    # Alignment results
    # ------------------------------------------------------------------

    async def save_alignment_result(self, session_id: str, result: AlignmentResult) -> None:
        def _write():
            d = self._session_dir(session_id)
            d.mkdir(parents=True, exist_ok=True)
            (d / "alignment.json").write_text(result.model_dump_json(indent=2))
        await asyncio.to_thread(_write)

    async def load_alignment_result(self, session_id: str) -> AlignmentResult | None:
        path = self._session_dir(session_id) / "alignment.json"
        if not path.exists():
            return None
        try:
            raw = await asyncio.to_thread(path.read_text)
            return AlignmentResult.model_validate_json(raw)
        except Exception as exc:
            logger.warning(f"Failed to load alignment result for {session_id}: {exc}")
            return None
