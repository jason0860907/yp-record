"""Channel splitting for interleaved stereo PCM audio."""
from __future__ import annotations

import struct
from typing import Tuple

from src.infra.logging import get_logger

logger = get_logger(__name__)


def split_stereo(data: bytes) -> Tuple[bytes, bytes]:
    """Split interleaved stereo PCM (16-bit int16) into separate mono channels."""
    frame_size = 4

    if len(data) % frame_size != 0:
        raise ValueError(
            f"Data length {len(data)} is not a multiple of {frame_size} bytes."
        )

    num_frames = len(data) // frame_size

    if num_frames == 0:
        return b"", b""

    all_samples = struct.unpack(f"<{num_frames * 2}h", data)

    ch0_samples = all_samples[0::2]
    ch1_samples = all_samples[1::2]

    ch0_bytes = struct.pack(f"<{num_frames}h", *ch0_samples)
    ch1_bytes = struct.pack(f"<{num_frames}h", *ch1_samples)

    return ch0_bytes, ch1_bytes
