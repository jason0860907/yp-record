"""Session metadata persistence."""
from __future__ import annotations

import asyncio
from typing import List

from src.logging import get_logger
from src.models import SessionInfo
from src.store.base import BaseStore

logger = get_logger(__name__)


class SessionStoreMixin(BaseStore):
    """Session metadata CRUD."""

    async def save_session(self, session: SessionInfo) -> None:
        await self._write_file(session.id, "session.json", session.model_dump_json(indent=2))

    async def load_session(self, session_id: str) -> SessionInfo | None:
        raw = await self._read_file(session_id, "session.json")
        if raw is None:
            return None
        try:
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
