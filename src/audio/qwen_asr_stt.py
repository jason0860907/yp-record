"""Speech-to-Text engine calling Qwen3-ASR via a vLLM server."""
from __future__ import annotations

import io
import struct
from typing import List

import httpx
from qwen_asr.inference.utils import parse_asr_output

from src.models import TranscriptSegment
from src.logging import get_logger

logger = get_logger(__name__)


class QwenASRSTT:
    """Speech-to-Text engine backed by Qwen3-ASR running on a vLLM server."""

    def __init__(
        self,
        base_url: str = "http://localhost:8006/v1",
        model: str = "Qwen/Qwen3-ASR-1.7B",
        timeout: float = 20.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        logger.info(f"QwenASRSTT configured: base_url={self.base_url}, model={model}")

    async def initialize(self) -> None:
        self._client = httpx.AsyncClient(timeout=self.timeout)
        try:
            resp = await self._client.get(f"{self.base_url}/models")
            resp.raise_for_status()
            logger.info(f"vLLM ASR server reachable at {self.base_url}")
        except httpx.HTTPError as exc:
            logger.warning(f"vLLM ASR server health-check failed ({exc}).")

    async def transcribe_chunk(
        self,
        audio_data: bytes,
        channel: int = 0,
        sample_rate: int = 16000,
    ) -> List[TranscriptSegment]:
        if self._client is None:
            await self.initialize()

        if not audio_data:
            return []

        wav_bytes = self._pcm_to_wav(audio_data, sample_rate)
        lang, text = await self._call_vllm(wav_bytes)

        if not text:
            return []

        speaker = "self" if channel == 0 else "other"
        return [
            TranscriptSegment(
                text=text,
                speaker=speaker,
                channel=channel,
                start_time=0.0,
                end_time=0.0,
                language=lang,
            )
        ]

    @staticmethod
    def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int) -> bytes:
        num_channels = 1
        bits_per_sample = 16
        byte_rate = sample_rate * num_channels * bits_per_sample // 8
        block_align = num_channels * bits_per_sample // 8
        data_size = len(pcm_bytes)
        riff_size = 36 + data_size

        buf = io.BytesIO()
        buf.write(b"RIFF")
        buf.write(struct.pack("<I", riff_size))
        buf.write(b"WAVE")
        buf.write(b"fmt ")
        buf.write(struct.pack("<I", 16))
        buf.write(struct.pack("<H", 1))
        buf.write(struct.pack("<H", num_channels))
        buf.write(struct.pack("<I", sample_rate))
        buf.write(struct.pack("<I", byte_rate))
        buf.write(struct.pack("<H", block_align))
        buf.write(struct.pack("<H", bits_per_sample))
        buf.write(b"data")
        buf.write(struct.pack("<I", data_size))
        buf.write(pcm_bytes)
        return buf.getvalue()

    async def _call_vllm(self, wav_bytes: bytes) -> tuple[str, str]:
        url = f"{self.base_url}/audio/transcriptions"
        files = {"file": ("audio.wav", wav_bytes, "audio/wav")}
        data = {"model": self.model}
        try:
            resp = await self._client.post(url, files=files, data=data)
            resp.raise_for_status()
            body = resp.json()
            raw = body.get("text", "")
            lang, text = parse_asr_output(raw)
            return lang, text
        except httpx.HTTPError as exc:
            logger.error(f"vLLM ASR request failed: {exc}")
            return "", ""

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
