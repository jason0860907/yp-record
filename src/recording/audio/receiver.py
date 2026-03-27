"""WebSocket audio receiver."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List, Protocol

from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from src.recording.audio.channels import split_stereo
from src.infra.models import TranscriptSegment
from src.infra.events import EventType, publish_event
from src.infra.logging import get_logger

logger = get_logger(__name__)


class _STTEngine(Protocol):
    async def transcribe_chunk(
        self, audio_data: bytes, channel: int = 0, sample_rate: int = 16000,
    ) -> List[TranscriptSegment]: ...


class AudioReceiver:
    """Receives PCM audio chunks from a WebSocket and feeds them to STT."""

    def __init__(
        self,
        stt_engine: _STTEngine,
        buffer_seconds: float = 10.0,
        sample_rate: int = 16000,
        channels: int = 2,
        audio_save_path: Path | None = None,
    ) -> None:
        self.stt_engine = stt_engine
        self.buffer_seconds = buffer_seconds
        self.sample_rate = sample_rate
        self.channels = channels
        self.audio_save_path = audio_save_path

        self.bytes_per_frame = 2 * channels
        self.buffer_threshold = int(sample_rate * buffer_seconds * self.bytes_per_frame)
        self._time_offset: float = 0.0

        logger.info(
            f"AudioReceiver configured: buffer={buffer_seconds}s, "
            f"rate={sample_rate}Hz, channels={channels}"
        )

    async def _transcribe_and_publish(
        self, chunk: bytes, session_id: str, start_time: float, end_time: float
    ) -> int:
        segments: List[TranscriptSegment] = []

        if self.channels == 2:
            try:
                ch0_data, ch1_data = split_stereo(chunk)
            except ValueError as e:
                logger.warning(f"Channel split failed: {e}")
                return 0
            ch0_segs, ch1_segs = await asyncio.gather(
                self.stt_engine.transcribe_chunk(ch0_data, channel=0, sample_rate=self.sample_rate),
                self.stt_engine.transcribe_chunk(ch1_data, channel=1, sample_rate=self.sample_rate),
            )
            segments.extend(ch0_segs)
            segments.extend(ch1_segs)
        else:
            segs = await self.stt_engine.transcribe_chunk(chunk, channel=0, sample_rate=self.sample_rate)
            segments.extend(segs)

        for seg in segments:
            seg.start_time = start_time
            seg.end_time = end_time
            await publish_event(
                EventType.TRANSCRIPT_SEGMENT,
                data={"session_id": session_id, "segment": seg.model_dump()},
                source="audio.receiver",
            )
        return len(segments)

    async def handle_websocket(self, websocket: WebSocket, session_id: str) -> None:
        buffer = bytearray()
        total_bytes_received = 0
        chunk_count = 0
        audio_file = None

        logger.info(f"Starting audio reception for session {session_id}")

        async def _keepalive(ws: WebSocket, interval: float = 30.0) -> None:
            try:
                while True:
                    await asyncio.sleep(interval)
                    if ws.client_state == WebSocketState.CONNECTED:
                        await ws.send_json({"type": "ping"})
            except Exception:
                pass

        keepalive_task = asyncio.create_task(_keepalive(websocket))

        try:
            if self.audio_save_path:
                self.audio_save_path.parent.mkdir(parents=True, exist_ok=True)
                audio_file = open(self.audio_save_path, "wb")

            while True:
                data = await websocket.receive_bytes()
                if audio_file:
                    audio_file.write(data)
                buffer.extend(data)
                total_bytes_received += len(data)

                if len(buffer) >= self.buffer_threshold:
                    chunk_count += 1
                    chunk_data = bytes(buffer[:self.buffer_threshold])
                    buffer = bytearray(buffer[self.buffer_threshold:])

                    chunk_start = self._time_offset
                    chunk_duration = len(chunk_data) / (self.sample_rate * self.bytes_per_frame)
                    self._time_offset += chunk_duration

                    await self._transcribe_and_publish(chunk_data, session_id, chunk_start, self._time_offset)

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for session {session_id}")

        except Exception as e:
            logger.error(f"Audio receiver error for session {session_id}: {e}")
            await publish_event(
                EventType.AUDIO_ERROR,
                data={"session_id": session_id, "error": str(e)},
                source="audio.receiver",
            )
            raise

        finally:
            keepalive_task.cancel()
            if audio_file:
                audio_file.close()

            if len(buffer) >= self.bytes_per_frame:
                valid_length = (len(buffer) // self.bytes_per_frame) * self.bytes_per_frame
                if valid_length > 0:
                    remainder = bytes(buffer[:valid_length])
                    remainder_start = self._time_offset
                    remainder_end = remainder_start + valid_length / (self.sample_rate * self.bytes_per_frame)
                    try:
                        await self._transcribe_and_publish(remainder, session_id, remainder_start, remainder_end)
                    except Exception as e:
                        logger.warning(f"Failed to process remaining audio: {e}")
