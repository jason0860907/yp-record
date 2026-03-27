"""Audio metadata, format conversion, and chunk reading."""
from __future__ import annotations

import asyncio
import json
import struct
import wave
from pathlib import Path
from typing import List

from src.logging import get_logger
from src.store.base import BaseStore

logger = get_logger(__name__)

BYTES_PER_SAMPLE = 2  # 16-bit PCM


class AudioStoreMixin(BaseStore):
    """Audio files, metadata, and format conversion."""

    # -- Metadata --

    async def save_audio_meta(self, session_id: str, channels: int, sample_rate: int) -> None:
        content = json.dumps({"channels": channels, "sample_rate": sample_rate})
        await self._write_file(session_id, "audio_meta.json", content)

    async def load_audio_meta(self, session_id: str) -> dict | None:
        raw = await self._read_file(session_id, "audio_meta.json")
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    async def detect_audio_channels(self, session_id: str) -> int:
        raw_path = self.get_audio_raw_path(session_id)
        if not raw_path.exists():
            return 1
        session = await self.load_session(session_id)  # type: ignore[attr-defined]
        if not session or not session.duration_seconds or session.duration_seconds < 1:
            return 1
        bytes_per_sec = raw_path.stat().st_size / session.duration_seconds
        return 2 if bytes_per_sec > 48000 else 1

    # -- File paths --

    def get_audio_raw_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "audio.raw"

    def get_audio_wav_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "audio.wav"

    # -- Conversion --

    async def raw_to_wav(self, session_id: str, sample_rate: int = 16000, channels: int = 2) -> Path:
        raw_path = self.get_audio_raw_path(session_id)
        wav_path = self.get_audio_wav_path(session_id)

        def _convert():
            raw_data = raw_path.read_bytes()
            mono_data = _stereo_to_mono(raw_data) if channels == 2 else raw_data
            with wave.open(str(wav_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(BYTES_PER_SAMPLE)
                wf.setframerate(sample_rate)
                wf.writeframes(mono_data)
            return wav_path

        return await asyncio.to_thread(_convert)

    async def read_wav_mono_chunks(
        self, session_id: str, chunk_seconds: float,
    ) -> List[tuple[bytes, float, float, int]]:
        wav_path = self.get_audio_wav_path(session_id)

        def _read():
            result: list[tuple[bytes, float, float, int]] = []
            with wave.open(str(wav_path), "rb") as wf:
                sr = wf.getframerate()
                n_ch = wf.getnchannels()
                chunk_frames = int(chunk_seconds * sr)
                t = 0.0
                while True:
                    frames = wf.readframes(chunk_frames)
                    if not frames:
                        break
                    pcm = _stereo_to_mono(frames) if n_ch > 1 else frames
                    dur = len(pcm) / (sr * BYTES_PER_SAMPLE)
                    result.append((pcm, t, t + dur, sr))
                    t += dur
            return result

        return await asyncio.to_thread(_read)


def _stereo_to_mono(data: bytes) -> bytes:
    """Mix stereo 16-bit PCM to mono."""
    samples = struct.unpack(f"<{len(data) // BYTES_PER_SAMPLE}h", data)
    mono = []
    for i in range(0, len(samples), 2):
        if i + 1 < len(samples):
            mono.append((samples[i] + samples[i + 1]) // 2)
        else:
            mono.append(samples[i])
    return struct.pack(f"<{len(mono)}h", *mono)
