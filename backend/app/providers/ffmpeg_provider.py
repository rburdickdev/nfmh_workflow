import logging
import subprocess

from app.providers.base import ClipExtractionProvider

logger = logging.getLogger(__name__)


class FFmpegClipExtractionProvider(ClipExtractionProvider):
    """
    Local FFmpeg clip extraction provider.

    Integration point:
    - You can swap this with a cloud media pipeline later while keeping the same
      ClipExtractionProvider interface.
    """

    def extract_clip(
        self,
        source_audio_path: str,
        output_clip_path: str,
        output_srt_path: str,
        start_seconds: float,
        end_seconds: float,
        transcript_segments: list[dict],
    ) -> None:
        duration = max(end_seconds - start_seconds, 10.0)
        command = [
            "ffmpeg",
            "-y",
            "-i",
            source_audio_path,
            "-ss",
            str(start_seconds),
            "-t",
            str(duration),
            "-af",
            "loudnorm",
            "-ar",
            "44100",
            "-ac",
            "2",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "192k",
            output_clip_path,
        ]

        logger.info("Running FFmpeg clip extraction", extra={"command": " ".join(command)})
        subprocess.run(command, check=True, capture_output=True, text=True)
        _write_srt(output_srt_path, transcript_segments, start_seconds, end_seconds)


def _write_srt(path: str, segments: list[dict], clip_start: float, clip_end: float) -> None:
    relevant = [
        s
        for s in segments
        if float(s.get("start", 0.0)) <= clip_end and float(s.get("end", 0.0)) >= clip_start
    ]
    with open(path, "w", encoding="utf-8") as file:
        for idx, segment in enumerate(relevant, start=1):
            start = max(float(segment.get("start", clip_start)) - clip_start, 0.0)
            end = max(float(segment.get("end", clip_end)) - clip_start, start + 0.5)
            file.write(f"{idx}\n")
            file.write(f"{_to_srt_time(start)} --> {_to_srt_time(end)}\n")
            file.write(f"{segment.get('text', '').strip()}\n\n")


def _to_srt_time(value: float) -> str:
    hours = int(value // 3600)
    minutes = int((value % 3600) // 60)
    seconds = int(value % 60)
    millis = int((value - int(value)) * 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"
