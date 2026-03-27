"""Notion knowledge base client."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx

from src.models import KnowledgePage
from src.logging import get_logger

logger = get_logger(__name__)

_NOTION_BASE_URL = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"
_LIST_BLOCK_TYPES = ("bulleted_list_item", "to_do")


class NotionKB:
    """Notion-backed knowledge base using the Notion REST API."""

    def __init__(self, database_id: str, api_key: str) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("NOTION_API_KEY is empty.")
        self._database_id = database_id
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=_NOTION_BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Notion-Version": _NOTION_VERSION,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    @staticmethod
    def _rich_text(text: str) -> List[Dict[str, Any]]:
        elements: List[Dict[str, Any]] = []
        pattern = re.compile(r"\*\*(.+?)\*\*|\*(.+?)\*|([^*]+)")
        for m in pattern.finditer(text):
            bold_text, italic_text, plain_text = m.group(1), m.group(2), m.group(3)
            if bold_text:
                content, annotations = bold_text, {"bold": True}
            elif italic_text:
                content, annotations = italic_text, {"italic": True}
            else:
                content, annotations = plain_text, {}

            for i in range(0, len(content), 2000):
                chunk = content[i: i + 2000]
                el: Dict[str, Any] = {"type": "text", "text": {"content": chunk}}
                if annotations:
                    el["annotations"] = annotations
                elements.append(el)

        return elements or [{"type": "text", "text": {"content": ""}}]

    @staticmethod
    def _make_block(stripped: str) -> Dict[str, Any]:
        if stripped.startswith("### "):
            return {"object": "block", "type": "heading_3",
                    "heading_3": {"rich_text": NotionKB._rich_text(stripped[4:])}}
        if stripped.startswith("## "):
            return {"object": "block", "type": "heading_2",
                    "heading_2": {"rich_text": NotionKB._rich_text(stripped[3:])}}
        if stripped.startswith("# "):
            return {"object": "block", "type": "heading_1",
                    "heading_1": {"rich_text": NotionKB._rich_text(stripped[2:])}}
        if stripped.startswith("- [ ] ") or stripped.startswith("- [x] "):
            checked = stripped[3] == "x"
            return {"object": "block", "type": "to_do",
                    "to_do": {"rich_text": NotionKB._rich_text(stripped[6:]), "checked": checked}}
        if stripped.startswith("- ") or stripped.startswith("* "):
            return {"object": "block", "type": "bulleted_list_item",
                    "bulleted_list_item": {"rich_text": NotionKB._rich_text(stripped[2:])}}
        if stripped == "---":
            return {"object": "block", "type": "divider", "divider": {}}
        return {"object": "block", "type": "paragraph",
                "paragraph": {"rich_text": NotionKB._rich_text(stripped)}}

    @staticmethod
    def _content_to_blocks(content: str) -> List[Dict[str, Any]]:
        top_blocks: List[Dict[str, Any]] = []
        stack: List[tuple] = []

        for raw in content.splitlines():
            stripped = raw.rstrip()
            if not stripped:
                stack.clear()
                continue

            indent = len(stripped) - len(stripped.lstrip())
            block = NotionKB._make_block(stripped.lstrip())
            is_list = block["type"] in _LIST_BLOCK_TYPES

            if not is_list:
                stack.clear()
                top_blocks.append(block)
                continue

            while stack and stack[-1][0] >= indent:
                stack.pop()

            if stack:
                parent = stack[-1][1]
                ptype = parent["type"]
                parent[ptype].setdefault("children", []).append(block)
            else:
                top_blocks.append(block)

            stack.append((indent, block))

        return top_blocks

    @staticmethod
    def _build_properties(page: KnowledgePage) -> Dict[str, Any]:
        props: Dict[str, Any] = {
            "Name": {"title": [{"text": {"content": page.title}}]},
            "Category": {"select": {"name": page.category.value}},
            "Source": {"select": {"name": page.source.value}},
            "Status": {"select": {"name": page.status.value}},
        }
        if page.session_id:
            props["Session ID"] = {"rich_text": [{"text": {"content": page.session_id}}]}
        props["Date"] = {"date": {"start": datetime.now(timezone.utc).isoformat()}}
        return props

    async def create_page(self, page: KnowledgePage) -> str:
        """Create a knowledge page in Notion. Returns the Notion page ID."""
        blocks = self._content_to_blocks(page.content)
        body: Dict[str, Any] = {
            "parent": {"database_id": self._database_id},
            "properties": self._build_properties(page),
            "children": blocks[:100],
        }
        try:
            resp = await self._client.post("/pages", json=body)
            resp.raise_for_status()
            page_id: str = resp.json()["id"]
            logger.info(f"Notion page created: {page_id}")

            for i in range(100, len(blocks), 100):
                batch = blocks[i: i + 100]
                resp = await self._client.patch(f"/blocks/{page_id}/children", json={"children": batch})
                resp.raise_for_status()

            return page_id
        except httpx.HTTPStatusError as exc:
            logger.error(f"Notion create_page failed ({exc.response.status_code}): {exc.response.text}")
            raise
        except Exception as exc:
            logger.error(f"Notion create_page error: {exc}")
            raise

    async def close(self) -> None:
        await self._client.aclose()
