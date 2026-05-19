import json
import logging
import os
import subprocess
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.clip import Clip
from app.models.processing_job import JobStatus, ProcessingJob
from app.models.transcript import Transcript
from app.models.upload import Upload, UploadStatus
from app.providers.factory import (
    get_analysis_provider,
    get_clip_extraction_provider,
    get_transcription_provider,
)

logger = logging.getLogger(__name__)


def process_upload(upload_id: str, db: Session) -> None:
    settings = get_settings()
    upload = db.query(Upload).filter(Upload.id == upload_id).first()
    if not upload:
        raise ValueError(f"Upload not found: {upload_id}")

    pipeline_job = _create_or_reset_job(db, upload_id, "full_pipeline")
    transcription_job = _create_or_reset_job(db, upload_id, "transcription")
    analysis_job = _create_or_reset_job(db, upload_id, "analysis")
    extraction_job = _create_or_reset_job(db, upload_id, "clip_extraction")

    try:
        upload.status = UploadStatus.processing
        pipeline_job.status = JobStatus.running
        db.commit()
        logger.info("Pipeline started", extra={"upload_id": upload_id, "stage": "pipeline"})

        # 1) Transcribe
        transcription_job.status = JobStatus.running
        db.commit()
        logger.info("Transcription started", extra={"upload_id": upload_id, "stage": "transcription"})
        transcription_provider = get_transcription_provider()
        transcription_audio_path = _normalize_audio_for_transcription(upload, settings)
        transcript_result = transcription_provider.transcribe(transcription_audio_path)
        transcript_text_path = os.path.join(settings.transcripts_dir, f"{upload_id}.txt")
        transcript_json_path = os.path.join(settings.transcripts_dir, f"{upload_id}.json")

        os.makedirs(settings.transcripts_dir, exist_ok=True)
        with open(transcript_text_path, "w", encoding="utf-8") as txt_file:
            txt_file.write(transcript_result.text)
        with open(transcript_json_path, "w", encoding="utf-8") as json_file:
            json.dump(transcript_result.segments, json_file, ensure_ascii=False, indent=2)

        transcript_row = db.query(Transcript).filter(Transcript.upload_id == upload_id).first()
        if transcript_row:
            transcript_row.text_path = transcript_text_path
            transcript_row.json_path = transcript_json_path
            transcript_row.full_text = transcript_result.text
            transcript_row.segments_json = {"segments": transcript_result.segments}
        else:
            db.add(
                Transcript(
                    upload_id=upload_id,
                    text_path=transcript_text_path,
                    json_path=transcript_json_path,
                    full_text=transcript_result.text,
                    segments_json={"segments": transcript_result.segments},
                )
            )
        transcription_job.status = JobStatus.completed
        db.commit()
        logger.info(
            "Transcription completed",
            extra={
                "upload_id": upload_id,
                "stage": "transcription",
                "segment_count": len(transcript_result.segments),
                "transcript_characters": len(transcript_result.text),
            },
        )

        # 2) Analyze transcript
        analysis_job.status = JobStatus.running
        db.commit()
        logger.info("Transcript analysis started", extra={"upload_id": upload_id, "stage": "analysis"})
        analysis_provider = get_analysis_provider()
        suggestions = analysis_provider.analyze_transcript(
            transcript_result.text, transcript_result.segments
        )
        analysis_job.status = JobStatus.completed
        db.commit()
        logger.info(
            "Transcript analysis completed",
            extra={
                "upload_id": upload_id,
                "stage": "analysis",
                "suggestion_count": len(suggestions),
            },
        )

        # 3) Extract clips + captions
        extraction_job.status = JobStatus.running
        db.commit()
        logger.info("Clip extraction started", extra={"upload_id": upload_id, "stage": "clip_extraction"})
        clip_provider = get_clip_extraction_provider()
        os.makedirs(settings.clips_dir, exist_ok=True)
        os.makedirs(settings.captions_dir, exist_ok=True)

        # Retry-safe behavior: if we reprocess an upload, replace existing clip rows.
        db.query(Clip).filter(Clip.upload_id == upload_id).delete()
        db.commit()

        for suggestion in suggestions:
            clip_id = str(uuid.uuid4())
            clip_path = os.path.join(settings.clips_dir, f"{clip_id}.mp3")
            captions_path = os.path.join(settings.captions_dir, f"{clip_id}.srt")
            clip_provider.extract_clip(
                source_audio_path=upload.storage_path,
                output_clip_path=clip_path,
                output_srt_path=captions_path,
                start_seconds=suggestion.start_seconds,
                end_seconds=suggestion.end_seconds,
                transcript_segments=transcript_result.segments,
            )

            db.add(
                Clip(
                    id=clip_id,
                    upload_id=upload_id,
                    title=suggestion.title,
                    hook_text=suggestion.hook_text,
                    reason=suggestion.reason,
                    score=suggestion.score,
                    start_seconds=suggestion.start_seconds,
                    end_seconds=suggestion.end_seconds,
                    clip_path=clip_path,
                    captions_path=captions_path,
                )
            )

        upload.status = UploadStatus.completed
        extraction_job.status = JobStatus.completed
        pipeline_job.status = JobStatus.completed
        db.commit()
        logger.info(
            "Upload processing completed",
            extra={"upload_id": upload_id, "stage": "pipeline", "created_clips": len(suggestions)},
        )
    except Exception as exc:
        logger.exception("Upload processing failed", extra={"upload_id": upload_id})
        upload.status = UploadStatus.failed
        pipeline_job.status = JobStatus.failed
        pipeline_job.error_message = str(exc)
        for stage_job in [transcription_job, analysis_job, extraction_job]:
            if stage_job.status in {JobStatus.pending, JobStatus.running}:
                stage_job.status = JobStatus.failed
                stage_job.error_message = str(exc)
        db.commit()
        raise


def _create_or_reset_job(db: Session, upload_id: str, job_type: str) -> ProcessingJob:
    job = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.upload_id == upload_id, ProcessingJob.job_type == job_type)
        .first()
    )
    if job:
        job.status = JobStatus.pending
        job.error_message = None
        db.commit()
        db.refresh(job)
        return job

    job = ProcessingJob(upload_id=upload_id, job_type=job_type, status=JobStatus.pending)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _normalize_audio_for_transcription(upload: Upload, settings) -> str:
    """
    Normalize source audio to WAV for stable transcription performance.

    Regardless of upload format (MP3/WAV/M4A), Whisper consumes a fresh
    44.1kHz stereo WAV artifact generated for the transcription stage.
    """
    os.makedirs(settings.normalized_audio_dir, exist_ok=True)
    normalized_path = os.path.join(settings.normalized_audio_dir, f"{upload.id}.wav")
    command = [
        "ffmpeg",
        "-y",
        "-i",
        upload.storage_path,
        "-ar",
        str(settings.transcription_wav_sample_rate),
        "-ac",
        str(settings.transcription_wav_channels),
        normalized_path,
    ]
    logger.info(
        "Normalizing audio for transcription",
        extra={
            "upload_id": upload.id,
            "source_audio_path": upload.storage_path,
            "normalized_audio_path": normalized_path,
            "sample_rate": settings.transcription_wav_sample_rate,
            "channels": settings.transcription_wav_channels,
        },
    )
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        logger.error(
            "Audio normalization failed",
            extra={
                "upload_id": upload.id,
                "command": " ".join(command),
                "stderr": exc.stderr,
            },
        )
        raise RuntimeError("Failed to normalize audio to WAV for transcription") from exc
    return normalized_path
