"""Shared base for file-based stores."""
from __future__ import annotations

import asyncio
from pathlib import Path


class BaseStore:
    """Provides session directory layout and async I/O helpers."""

    def __init__(self, base_dir: str = "storage/sessions") -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    def _session_dir(self, session_id: str) -> Path:
        return self._base / session_id

    def _ensure_dir(self, session_id: str) -> Path:
        d = self._session_dir(session_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    async def _write_file(self, session_id: str, filename: str, content: str) -> None:
        def _do():
            d = self._ensure_dir(session_id)
            (d / filename).write_text(content, encoding="utf-8")
        await asyncio.to_thread(_do)

    async def _read_file(self, session_id: str, filename: str) -> str | None:
        path = self._session_dir(session_id) / filename
        if not path.exists():
            return None
        return await asyncio.to_thread(path.read_text, "utf-8")
