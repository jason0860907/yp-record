"""Screenshot persistence."""
from __future__ import annotations

import asyncio
from typing import List

from src.recording.store.base import BaseStore


class ScreenshotStoreMixin(BaseStore):
    """Screenshot save and listing."""

    def get_screenshots_dir(self, session_id: str):
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
            return [{"filename": f, "timestamp": int(f.replace(".jpg", "")) / 1000.0} for f in files]
        return await asyncio.to_thread(_list)
