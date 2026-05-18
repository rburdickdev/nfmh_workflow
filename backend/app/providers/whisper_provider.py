import logging

from faster_whisper import WhisperModel

from app.core.config import get_settings
from app.providers.base import TranscriptResult, TranscriptionProvider

logger = logging.getLogger(__name__)


class WhisperTranscriptionProvider(TranscriptionProvider):
    """
    Local Whisper transcription provider (faster-whisper).

    Integration point:
    - Model name and device are controlled via environment variables.
    - To migrate to cloud transcription, add another provider class and switch
      TRANSCRIPTION_PROVIDER in `.env`.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )

    def transcribe(self, audio_path: str) -> TranscriptResult:
        logger.info("Starting local Whisper transcription", extra={"audio_path": audio_path})
        segments, _ = self.model.transcribe(audio_path, word_timestamps=True)
        segment_list: list[dict] = []
        transcript_parts: list[str] = []

        for idx, segment in enumerate(segments, start=1):
            segment_text = segment.text.strip()
            transcript_parts.append(segment_text)
            segment_list.append(
                {
                    "start": float(segment.start),
                    "end": float(segment.end),
                    "text": segment_text,
                }
            )
            # Verbose progress log for operators and debugging.
            if idx == 1 or idx % 25 == 0:
                logger.info(
                    "Whisper transcription progress",
                    extra={
                        "audio_path": audio_path,
                        "segments_processed": idx,
                        "latest_segment_end_seconds": float(segment.end),
                    },
                )

        logger.info(
            "Whisper transcription finished",
            extra={"audio_path": audio_path, "total_segments": len(segment_list)},
        )
        return TranscriptResult(text=" ".join(transcript_parts), segments=segment_list)
