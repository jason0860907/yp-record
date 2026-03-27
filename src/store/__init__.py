"""
File-based session persistence.

Composed from single-responsibility mixins, re-exported as one class
so existing imports (``from src.store import RecordingSessionStore``) remain valid.
"""
from src.store.session import SessionStoreMixin
from src.store.transcript import TranscriptStoreMixin
from src.store.audio import AudioStoreMixin
from src.store.screenshots import ScreenshotStoreMixin
from src.store.alignment import AlignmentStoreMixin


class RecordingSessionStore(
    SessionStoreMixin,
    TranscriptStoreMixin,
    AudioStoreMixin,
    ScreenshotStoreMixin,
    AlignmentStoreMixin,
):
    """Unified store — delegates to focused mixins."""
    pass
