"""Speaker diarization service using pyannote.audio."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import List

from src.infra.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SpeakerSegment:
    start: float
    end: float
    speaker: str  # e.g. "SPEAKER_00"


class DiarizationService:
    """Performs speaker diarization via pyannote.audio."""

    def __init__(
        self,
        device: str = "auto",
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ) -> None:
        self._device_cfg = device
        self._min_speakers = min_speakers
        self._max_speakers = max_speakers
        self._pipeline = None
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        await asyncio.to_thread(self._load_pipeline)
        self._initialized = True

    def _load_pipeline(self) -> None:
        from pyannote.audio import Pipeline

        device = self._resolve_device()
        logger.info(f"Loading pyannote diarization pipeline device={device}")
        self._pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1")
        if device != "cpu":
            import torch
            self._pipeline = self._pipeline.to(torch.device(device))
        logger.info("Pyannote diarization pipeline loaded")

    def _resolve_device(self) -> str:
        if self._device_cfg != "auto":
            return self._device_cfg
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    async def diarize(self, wav_path: Path) -> List[SpeakerSegment]:
        if not self._initialized:
            await self.initialize()
        return await asyncio.to_thread(self._diarize_sync, wav_path)

    def _diarize_sync(self, wav_path: Path) -> List[SpeakerSegment]:
        kwargs = {}
        if self._min_speakers is not None:
            kwargs["min_speakers"] = self._min_speakers
        if self._max_speakers is not None:
            kwargs["max_speakers"] = self._max_speakers

        import soundfile as sf
        import torch
        data, sample_rate = sf.read(str(wav_path), dtype="float32")
        waveform = torch.from_numpy(data)
        if waveform.ndim == 1:
            waveform = waveform.unsqueeze(0)
        else:
            waveform = waveform.T
        output = self._pipeline({"waveform": waveform, "sample_rate": sample_rate}, **kwargs)
        diarization = output.exclusive_speaker_diarization

        result: List[SpeakerSegment] = []
        for segment, _, speaker in diarization.itertracks(yield_label=True):
            result.append(SpeakerSegment(
                start=segment.start,
                end=segment.end,
                speaker=speaker,
            ))
        return result

    def offload_to_cpu(self) -> None:
        import torch
        try:
            if self._pipeline is not None:
                self._pipeline.to(torch.device("cpu"))
        except Exception:
            pass
        torch.cuda.empty_cache()

    async def close(self) -> None:
        self._pipeline = None
        self._initialized = False
