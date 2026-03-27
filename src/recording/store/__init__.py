"""
File-based session persistence.

Composed from single-responsibility mixins, re-exported as one class
so existing imports (``from src.recording.store import RecordingSessionStore``) remain valid.
"""
from src.recording.store.session import SessionStoreMixin
from src.recording.store.transcript import TranscriptStoreMixin
from src.recording.store.audio import AudioStoreMixin
from src.recording.store.screenshots import ScreenshotStoreMixin
from src.recording.store.alignment import AlignmentStoreMixin


class RecordingSessionStore(
    SessionStoreMixin,
    TranscriptStoreMixin,
    AudioStoreMixin,
    ScreenshotStoreMixin,
    AlignmentStoreMixin,
):
    """Unified store — delegates to focused mixins."""
    pass
