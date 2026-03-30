"""Consolidated Pydantic models for yp-record."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List
from pydantic import BaseModel, Field


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class SessionStatus(str, Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class SessionSource(str, Enum):
    RECORDING = "recording"
    YOUTUBE = "youtube"


class SessionInfo(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    status: SessionStatus = SessionStatus.IDLE
    source: SessionSource = SessionSource.RECORDING
    source_url: str | None = None
    title: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    duration_seconds: float = 0.0
    segment_count: int = 0
    participants: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Transcript
# ---------------------------------------------------------------------------

class TranscriptSegment(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    text: str
    speaker: str = "unknown"  # "self" | "other" | "unknown"
    channel: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    language: str = "zh"
    timestamp: str = Field(default_factory=_iso_now)


class WordTimestamp(BaseModel):
    word: str
    start: float
    end: float
    score: float = 0.0


class EnrichedTranscriptSegment(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    text: str
    start: float
    end: float
    speaker: str | None = None
    words: List[WordTimestamp] = Field(default_factory=list)
    language: str = "zh"


class AlignmentResult(BaseModel):
    session_id: str
    status: str = "pending"
    language: str = ""
    segments: List[EnrichedTranscriptSegment] = Field(default_factory=list)
    num_speakers: int = 0
    processing_time_seconds: float = 0.0
    created_at: str = Field(default_factory=_iso_now)
    error: str | None = None


# ---------------------------------------------------------------------------
# Knowledge (for Notion export)
# ---------------------------------------------------------------------------

class KnowledgeCategory(str, Enum):
    MEETING_NOTES = "meeting_notes"
    SESSION_SUMMARY = "session_summary"
    RESEARCH_FINDING = "research_finding"
    DECISION_RECORD = "decision_record"
    HOW_TO = "how_to"
    REFERENCE = "reference"


class KnowledgeSource(str, Enum):
    MEETING = "meeting"
    CONVERSATION = "conversation"
    RESEARCH = "research"
    MANUAL = "manual"


class KnowledgeStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class KnowledgePage(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    title: str
    content: str
    category: KnowledgeCategory = KnowledgeCategory.MEETING_NOTES
    tags: List[str] = Field(default_factory=list)
    source: KnowledgeSource = KnowledgeSource.MEETING
    session_id: str | None = None
    participants: List[str] = Field(default_factory=list)
    status: KnowledgeStatus = KnowledgeStatus.DRAFT
    created_at: str = Field(default_factory=_iso_now)
    updated_at: str = Field(default_factory=_iso_now)
    metadata: Dict[str, Any] = Field(default_factory=dict)
