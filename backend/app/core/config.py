from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralized environment-variable configuration.

    Every configurable value in this MVP should live here so operators can
    update behavior using only the `.env` file.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Newsroom Clipper MVP"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # =====================================================
    # AI PROVIDER CONFIGURATION
    #
    # This section controls which AI backend is used.
    #
    # Current default:
    # - Ollama running externally on the host machine
    #
    # Future supported providers:
    # - OpenAI
    # - Claude
    # - Gemini
    #
    # To switch providers:
    # 1. Update environment variables in `.env`
    # 2. Implement/select provider classes in app/providers
    # =====================================================
    ai_analysis_provider: str = "ollama"
    transcription_provider: str = "whisper_local"
    clip_extraction_provider: str = "ffmpeg"

    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "llama3"

    whisper_model: str = "small"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"

    transcript_chunk_size: int = 1200
    transcript_chunk_overlap: int = 150
    max_suggested_clips: int = 8
    analysis_timeout_seconds: int = 120

    postgres_url: str = "postgresql+psycopg2://clipper:clipper@postgres:5432/clipper_db"
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"

    storage_path: str = "/storage"
    uploads_dir: str = "/storage/uploads"
    transcripts_dir: str = "/storage/transcripts"
    clips_dir: str = "/storage/clips"
    captions_dir: str = "/storage/captions"

    # Optional future cloud credentials.
    # Keep blank unless migrating to cloud providers.
    openai_api_key: str | None = None
    claude_api_key: str | None = None
    deepgram_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
