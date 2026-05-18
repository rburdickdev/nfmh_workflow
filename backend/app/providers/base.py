from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TranscriptResult:
    text: str
    segments: list[dict]


@dataclass
class ClipSuggestion:
    title: str
    hook_text: str
    reason: str
    score: float
    start_seconds: float
    end_seconds: float


class TranscriptionProvider(ABC):
    """
    Provider interface for speech-to-text engines.

    Future providers can implement this same contract (Deepgram, OpenAI, etc.)
    without changing the rest of the application flow.
    """

    @abstractmethod
    def transcribe(self, audio_path: str) -> TranscriptResult:
        raise NotImplementedError


class AIAnalysisProvider(ABC):
    """
    Provider interface for semantic clip detection.

    Keep this interface stable and swap implementations as needed.
    """

    @abstractmethod
    def analyze_transcript(
        self, transcript_text: str, segments: list[dict]
    ) -> list[ClipSuggestion]:
        raise NotImplementedError


class ClipExtractionProvider(ABC):
    """
    Provider interface for clip rendering.

    Default uses FFmpeg locally, but cloud media services can be added later.
    """

    @abstractmethod
    def extract_clip(
        self,
        source_audio_path: str,
        output_clip_path: str,
        output_srt_path: str,
        start_seconds: float,
        end_seconds: float,
        transcript_segments: list[dict],
    ) -> None:
        raise NotImplementedError
