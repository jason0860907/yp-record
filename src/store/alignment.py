"""Alignment result persistence."""
from __future__ import annotations

from src.logging import get_logger
from src.models import AlignmentResult
from src.store.base import BaseStore

logger = get_logger(__name__)


class AlignmentStoreMixin(BaseStore):
    """Alignment result save and load."""

    async def save_alignment_result(self, session_id: str, result: AlignmentResult) -> None:
        await self._write_file(session_id, "alignment.json", result.model_dump_json(indent=2))

    async def load_alignment_result(self, session_id: str) -> AlignmentResult | None:
        raw = await self._read_file(session_id, "alignment.json")
        if raw is None:
            return None
        try:
            return AlignmentResult.model_validate_json(raw)
        except Exception as exc:
            logger.warning(f"Failed to load alignment result for {session_id}: {exc}")
            return None
