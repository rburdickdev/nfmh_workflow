from app.core.config import get_settings
from app.providers.base import AIAnalysisProvider, ClipExtractionProvider, TranscriptionProvider
from app.providers.ffmpeg_provider import FFmpegClipExtractionProvider
from app.providers.ollama_provider import OllamaAnalysisProvider
from app.providers.whisper_provider import WhisperTranscriptionProvider


def get_transcription_provider() -> TranscriptionProvider:
    settings = get_settings()
    if settings.transcription_provider == "whisper_local":
        return WhisperTranscriptionProvider()
    raise ValueError(f"Unsupported transcription provider: {settings.transcription_provider}")


def get_analysis_provider() -> AIAnalysisProvider:
    settings = get_settings()
    if settings.ai_analysis_provider == "ollama":
        return OllamaAnalysisProvider()
    raise ValueError(f"Unsupported AI analysis provider: {settings.ai_analysis_provider}")


def get_clip_extraction_provider() -> ClipExtractionProvider:
    settings = get_settings()
    if settings.clip_extraction_provider == "ffmpeg":
        return FFmpegClipExtractionProvider()
    raise ValueError(f"Unsupported clip extraction provider: {settings.clip_extraction_provider}")
