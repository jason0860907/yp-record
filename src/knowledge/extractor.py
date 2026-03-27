"""
Transcript extractor — two-step LLM processing at session end.

Step 1: Polish raw ASR transcript (remove filler words, fix errors)
Step 2: Generate structured meeting note from polished transcript
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, List

from src.knowledge.llm import LLMClient

if TYPE_CHECKING:
    from src.infra.events import EventBus
    from src.recording.store import RecordingSessionStore
from src.infra.logging import get_logger
from src.infra.models import (
    KnowledgeCategory,
    KnowledgePage,
    KnowledgeSource,
    SessionInfo,
    TranscriptSegment,
)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Prompt templates (ported from yp-agent configs/prompts/)
# ---------------------------------------------------------------------------

_PROMPT_POLISH = """\
你是會議逐字稿整理助手。請將以下語音辨識原文整理成通順的逐字稿。

## 原始逐字稿
{transcript}

## 任務
1. 清除語氣詞（嗯、啊、那個）、重複、口吃
2. 修正明顯的語音辨識錯誤
3. 保留所有實質內容，不要遺漏任何資訊
4. 移除所有說話者標記（如 [我]、[對方] 等）
5. 適當加入標點符號，使文字易讀

直接輸出整理後的逐字稿，不要加前言或解釋。"""

_PROMPT_SUMMARY = """\
你是專業的會議紀錄整理助手。根據以下會議逐字稿，產生一份完整的會議紀錄。

## 會議資訊
{session_info}

## 整理後的逐字稿
{transcript}

## 輸出格式（Markdown）
# 自動產生的標題

## 摘要
2-3句重點摘要

## 關鍵決議
- 決議

## 行動項目
- [ ] 行動項目 — @負責人

## 重要見解
- 見解

## 討論紀要
按主題組織的精煉討論內容

直接輸出 Markdown，不要加前言或解釋。如果某個區段沒有內容則省略該區段。"""

_SYSTEM_POLISH = (
    "/no_think\n"
    "你是會議逐字稿整理助手。直接輸出整理後的逐字稿，不要加前言或解釋。"
)
_SYSTEM_SUMMARY = (
    "/no_think\n"
    "你是專業的會議紀錄整理助手。直接輸出 Markdown，不要加前言或解釋。"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def format_segments(segments: List[TranscriptSegment]) -> str:
    """Format transcript segments with speaker labels."""
    lines = []
    for seg in segments:
        speaker = seg.speaker
        if speaker == "self":
            label = "[我]"
        elif speaker == "other":
            label = "[對方]"
        elif speaker and speaker != "unknown":
            label = f"[{speaker}]"
        else:
            label = ""
        prefix = f"{label} " if label else ""
        lines.append(f"{prefix}{seg.text}")
    return "\n".join(lines)


def _split_chunks(text: str, max_chars: int = 8000) -> list[str]:
    """Split text into chunks of at most max_chars, breaking on newlines."""
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in text.split("\n"):
        line_len = len(line) + 1
        if current_len + line_len > max_chars and current:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += line_len
    if current:
        chunks.append("\n".join(current))
    return chunks


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------

async def run_extraction(
    session_id: str,
    extractor: "KnowledgeExtractor",
    store: "RecordingSessionStore",
    event_bus: "EventBus",
    cached_segments: list[TranscriptSegment] | None = None,
) -> None:
    """Orchestrate transcript polish + meeting note generation for a session."""
    from src.infra.events import Event, EventType

    segments = cached_segments
    if not segments:
        segments = await store.load_segments(session_id)
    if not segments:
        logger.debug(f"No segments for session '{session_id}', skipping extraction")
        return

    raw_text = format_segments(segments)
    logger.info(f"Running extraction for session '{session_id}' ({len(segments)} segments)")

    try:
        polished = await extractor.polish_transcript(raw_text)
        if polished:
            await store.save_polished_transcript(session_id, polished)

        transcript_for_note = polished or raw_text
        session_info = await store.load_session(session_id)
        page = await extractor.generate_session_note(
            transcript=transcript_for_note,
            session_info=session_info,
        )
        if page is None:
            logger.warning(f"Meeting note generation returned None for '{session_id}'")
            return

        page.session_id = session_id
        await store.save_meeting_note(session_id, page)

        page.content += f"\n\n---\n\n# 完整逐字稿\n\n{transcript_for_note}"

        await event_bus.publish(Event(
            type=EventType.KNOWLEDGE_EXTRACTED,
            data={"page": page.model_dump(), "session_id": session_id},
            source="extractor",
        ))
        logger.info(f"Extraction completed for '{session_id}': '{page.title}'")

    except Exception as e:
        logger.error(f"Extraction failed for session '{session_id}': {e}")


class KnowledgeExtractor:
    """Two-step LLM extraction: polish transcript → generate meeting note."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def close(self) -> None:
        await self._llm.close()

    # -- Step 1: Polish transcript --

    async def polish_transcript(self, raw_text: str) -> str | None:
        """Clean up raw ASR transcript. Returns polished text or None."""
        if not raw_text.strip():
            return None

        chunks = _split_chunks(raw_text)
        logger.info(f"Polishing transcript ({len(raw_text)} chars, {len(chunks)} chunk(s))")

        results: list[str] = []
        for i, chunk in enumerate(chunks):
            if len(chunks) > 1:
                logger.info(f"Polishing chunk {i + 1}/{len(chunks)} ({len(chunk)} chars)")
            polished = await self._polish_chunk(chunk)
            results.append(polished if polished is not None else chunk)

        result = "\n".join(results)
        logger.info(f"Polished transcript: {len(raw_text)} → {len(result)} chars")
        return result

    async def _polish_chunk(self, chunk: str) -> str | None:
        prompt = _PROMPT_POLISH.format(transcript=chunk)
        max_tokens = max(len(chunk) // 2, 4096)
        try:
            content = await self._llm.complete(
                prompt,
                system_prompt=_SYSTEM_POLISH,
                max_tokens=max_tokens,
            )
            if not content.strip():
                logger.warning("LLM returned empty polished chunk")
                return None
            return content
        except Exception as exc:
            logger.error(f"Transcript chunk polishing failed: {exc}")
            return None

    # -- Step 2: Generate meeting note --

    async def generate_session_note(
        self,
        transcript: str,
        session_info: SessionInfo | None = None,
    ) -> KnowledgePage | None:
        """Generate a structured meeting note from transcript."""
        if not transcript.strip():
            return None

        if session_info:
            info_text = (
                f"Session ID: {session_info.id}\n"
                f"Title: {session_info.title or 'N/A'}\n"
                f"Started: {session_info.started_at or 'N/A'}\n"
                f"Duration: {session_info.duration_seconds:.0f}s\n"
                f"Participants: {', '.join(session_info.participants) or 'N/A'}"
            )
        else:
            info_text = "N/A"

        prompt = _PROMPT_SUMMARY.format(session_info=info_text, transcript=transcript)
        logger.info(f"Generating session note ({len(transcript)} chars)")

        try:
            content = await self._llm.complete(prompt, system_prompt=_SYSTEM_SUMMARY)
            if not content.strip():
                logger.warning("LLM returned empty session note")
                return None

            title_match = re.match(r"^#\s+(.+)$", content, re.MULTILINE)
            title = title_match.group(1).strip()[:80] if title_match else "會議紀錄"

            page = KnowledgePage(
                title=title,
                content=content,
                category=KnowledgeCategory.SESSION_SUMMARY,
                tags=["session_summary"],
                source=KnowledgeSource.MEETING,
                session_id=session_info.id if session_info else None,
            )
            logger.info(f"Generated session note: '{title}' ({len(content)} chars)")
            return page

        except Exception as exc:
            logger.error(f"Session note generation failed: {exc}")
            return None
