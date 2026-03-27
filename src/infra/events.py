"""Event system for yp-record — recording-specific events only."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from src.infra.logging import get_logger

logger = get_logger(__name__)


class EventType(Enum):
    # Session lifecycle
    SESSION_STARTED = "session.started"
    SESSION_PAUSED = "session.paused"
    SESSION_RESUMED = "session.resumed"
    SESSION_ENDED = "session.ended"

    # Audio
    AUDIO_CHUNK_RECEIVED = "audio.chunk_received"
    AUDIO_ERROR = "audio.error"

    # Transcript
    TRANSCRIPT_SEGMENT = "transcript.segment"

    # Alignment post-processing
    ALIGNMENT_STARTED = "alignment.started"
    ALIGNMENT_COMPLETED = "alignment.completed"
    ALIGNMENT_FAILED = "alignment.failed"

    # Knowledge extraction (transcript polish + meeting note)
    KNOWLEDGE_EXTRACTED = "knowledge.extracted"


@dataclass
class EventMeta:
    trace_id: str | None = None
    source: str | None = None
    cancellable: bool = False
    _cancelled: bool = field(default=False, repr=False)

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> None:
        if self.cancellable:
            self._cancelled = True


@dataclass
class Event:
    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    source: Optional[str] = None
    meta: EventMeta = field(default_factory=EventMeta)

    def __post_init__(self):
        if self.data is None:
            self.data = {}
        if not self.meta.source and self.source:
            self.meta.source = self.source


EventHandler = Callable[[Event], None]
AsyncEventHandler = Callable[[Event], Any]


class EventBus:
    def __init__(self):
        self._handlers: Dict[EventType, List[Union[EventHandler, AsyncEventHandler]]] = {}

    def subscribe(self, event_type: EventType, handler: Union[EventHandler, AsyncEventHandler]) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: Union[EventHandler, AsyncEventHandler]) -> None:
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
            except ValueError:
                pass

    async def publish(self, event: Event) -> None:
        handlers = list(self._handlers.get(event.type, []))
        for handler in handlers:
            if event.meta.cancelled:
                break
            await self._call_handler(handler, event)

    async def _call_handler(self, handler: Union[EventHandler, AsyncEventHandler], event: Event) -> None:
        try:
            result = handler(event)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.error(f"Handler error for {event.type.value}: {e}")

    def publish_fire_and_forget(self, event: Event) -> None:
        asyncio.create_task(self.publish(event))

    def clear(self) -> None:
        self._handlers.clear()


_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


async def publish_event(
    event_type: EventType,
    data: Optional[Dict[str, Any]] = None,
    source: Optional[str] = None,
) -> None:
    event = Event(type=event_type, data=data or {}, source=source)
    await get_event_bus().publish(event)
