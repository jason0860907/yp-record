"""Forced alignment service using Qwen3-ForcedAligner."""
from __future__ import annotations

import asyncio
import os
import tempfile
import wave
from pathlib import Path
from typing import List, TYPE_CHECKING

from src.models import EnrichedTranscriptSegment, WordTimestamp
from src.logging import get_logger

if TYPE_CHECKING:
    from src.models import TranscriptSegment

logger = get_logger(__name__)

_PAUSE_THRESHOLD = 2.0

_LANGUAGE_MAP = {
    "zh": "Chinese",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "ru": "Russian",
}


class ForcedAlignmentService:
    """Aligns transcript text to audio using Qwen3-ForcedAligner-0.6B."""

    def __init__(
        self,
        model: str = "Qwen/Qwen3-ForcedAligner-0.6B",
        device: str = "auto",
    ) -> None:
        self._model_name = model
        self._device_cfg = device
        self._model = None
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        await asyncio.to_thread(self._load_model)
        self._initialized = True

    def _load_model(self) -> None:
        import torch
        from qwen_asr import Qwen3ForcedAligner

        device = self._resolve_device()
        logger.info(f"Loading ForcedAligner model={self._model_name} device={device}")
        self._model = Qwen3ForcedAligner.from_pretrained(
            self._model_name,
            dtype=torch.bfloat16,
            device_map=device,
        )
        logger.info("ForcedAligner model loaded")

    def _resolve_device(self) -> str:
        if self._device_cfg != "auto":
            return self._device_cfg
        try:
            import torch
            return "cuda:0" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    async def align(self, wav_path: Path, text: str, language: str) -> List[EnrichedTranscriptSegment]:
        if not self._initialized:
            await self.initialize()
        return await asyncio.to_thread(self._align_sync, wav_path, text, language)

    def _align_sync(self, wav_path: Path, text: str, language: str) -> List[EnrichedTranscriptSegment]:
        lang_name = _LANGUAGE_MAP.get(language, language)
        results = self._model.align(audio=str(wav_path), text=text, language=lang_name)
        words_raw = results[0] if results else []

        words: List[WordTimestamp] = []
        for w in words_raw:
            words.append(WordTimestamp(
                word=w.text,
                start=float(w.start_time),
                end=float(w.end_time),
                score=0.0,
            ))
        return _group_words_to_segments(words, language)

    async def align_chunked(
        self, wav_path: Path, segments: List["TranscriptSegment"], language: str
    ) -> List[EnrichedTranscriptSegment]:
        if not self._initialized:
            await self.initialize()
        return await asyncio.to_thread(self._align_chunked_sync, wav_path, segments, language)

    def _align_chunked_sync(
        self, wav_path: Path, segments: List["TranscriptSegment"], language: str
    ) -> List[EnrichedTranscriptSegment]:
        lang_name = _LANGUAGE_MAP.get(language, language)
        all_words: List[WordTimestamp] = []

        with wave.open(str(wav_path), "rb") as wf:
            sr = wf.getframerate()
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()

            for seg in segments:
                if not seg.text.strip():
                    continue
                start_frame = int(seg.start_time * sr)
                n_frames = int((seg.end_time - seg.start_time) * sr)
                if n_frames <= 0:
                    continue

                wf.setpos(start_frame)
                frames = wf.readframes(n_frames)

                tmp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                tmp_path = tmp_file.name
                try:
                    with wave.open(tmp_file, "wb") as tmp_wf:
                        tmp_wf.setnchannels(n_channels)
                        tmp_wf.setsampwidth(sampwidth)
                        tmp_wf.setframerate(sr)
                        tmp_wf.writeframes(frames)

                    results = self._model.align(audio=tmp_path, text=seg.text, language=lang_name)
                    words_raw = results[0] if results else []

                    offset = seg.start_time
                    for w in words_raw:
                        all_words.append(WordTimestamp(
                            word=w.text,
                            start=float(w.start_time) + offset,
                            end=float(w.end_time) + offset,
                            score=0.0,
                        ))
                finally:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

        return _group_words_to_segments(all_words, language)

    def offload_to_cpu(self) -> None:
        import torch
        if self._model is not None:
            del self._model
            self._model = None
            self._initialized = False
        torch.cuda.empty_cache()

    def restore_to_gpu(self) -> None:
        pass  # Reloads lazily on next align() call

    async def close(self) -> None:
        self._model = None
        self._initialized = False


def _group_words_to_segments(
    words: List[WordTimestamp],
    language: str,
    pause_threshold: float = _PAUSE_THRESHOLD,
) -> List[EnrichedTranscriptSegment]:
    if not words:
        return []

    segments: List[EnrichedTranscriptSegment] = []
    current: List[WordTimestamp] = [words[0]]

    for word in words[1:]:
        gap = word.start - current[-1].end
        if gap > pause_threshold:
            segments.append(_make_segment(current, language))
            current = [word]
        else:
            current.append(word)

    if current:
        segments.append(_make_segment(current, language))

    return segments


def _make_segment(words: List[WordTimestamp], language: str) -> EnrichedTranscriptSegment:
    text = "".join(w.word for w in words)
    return EnrichedTranscriptSegment(
        text=text,
        start=words[0].start,
        end=words[-1].end,
        speaker=None,
        words=words,
        language=language,
    )
