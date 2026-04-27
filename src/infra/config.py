"""Application configuration via environment variables."""
from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Server
    host: str = "0.0.0.0"
    port: int = 8080
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ASR (vLLM)
    asr_base_url: str = "http://localhost:8006/v1"
    asr_model: str = "Qwen/Qwen3-ASR-1.7B"
    asr_timeout: float = 20.0

    # Audio
    sample_rate: int = 16000
    buffer_seconds: float = 10.0

    # Screenshots
    screenshot_interval_seconds: int = 10

    # Forced Aligner
    aligner_enabled: bool = True
    aligner_model: str = "Qwen/Qwen3-ForcedAligner-0.6B"
    aligner_device: str = "auto"
    aligner_language: str = "zh"
    aligner_auto_on_session_end: bool = True

    # Diarization
    diarization_enabled: bool = True
    diarization_device: str = "auto"
    diarization_min_speakers: int | None = None
    diarization_max_speakers: int | None = None

    # HuggingFace (consumed via env by pyannote / transformers / etc.)
    hf_token: str = ""

    # Notion
    notion_api_key: str = ""
    notion_database_id: str = ""

    # LLM extraction (transcript polish + meeting note generation)
    extract_enabled: bool = False
    extract_base_url: str = "http://localhost:8000/v1"
    extract_model: str = "cyankiwi/Qwen3.5-9B-AWQ-4bit"
    extract_api_key: str = ""
    extract_temperature: float = 0.3
    extract_timeout: float = 120.0
    extract_auto_on_session_end: bool = True

    # Storage
    storage_dir: str = "storage/sessions"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
