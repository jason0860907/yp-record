"""Transcript segment, polished transcript, and meeting note persistence."""
from __future__ import annotations

import asyncio
from typing import List

from src.logging import get_logger
from src.models import KnowledgePage, TranscriptSegment
from src.store.base import BaseStore

logger = get_logger(__name__)


class TranscriptStoreMixin(BaseStore):
    """Transcript segments + polished transcript + meeting note."""

    # -- Segments --

    async def replace_segments(self, session_id: str, segments: List[TranscriptSegment]) -> None:
        def _write():
            d = self._ensure_dir(session_id)
            with open(d / "segments.jsonl", "w") as f:
                for seg in segments:
                    f.write(seg.model_dump_json() + "\n")
        await asyncio.to_thread(_write)

    async def append_segment(self, session_id: str, segment: TranscriptSegment) -> None:
        def _append():
            d = self._ensure_dir(session_id)
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

    # -- Polished transcript --

    async def save_polished_transcript(self, session_id: str, text: str) -> None:
        await self._write_file(session_id, "polished.txt", text)

    async def load_polished_transcript(self, session_id: str) -> str | None:
        return await self._read_file(session_id, "polished.txt")

    # -- Meeting note --

    async def save_meeting_note(self, session_id: str, page: KnowledgePage) -> None:
        await self._write_file(session_id, "meeting_note.json", page.model_dump_json(indent=2))

    async def load_meeting_note(self, session_id: str) -> KnowledgePage | None:
        raw = await self._read_file(session_id, "meeting_note.json")
        if raw is None:
            return None
        try:
            return KnowledgePage.model_validate_json(raw)
        except Exception as exc:
            logger.warning(f"Failed to load meeting note for {session_id}: {exc}")
            return None
