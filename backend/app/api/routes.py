import logging
import os
import shutil
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.clip import Clip, ClipStatus
from app.models.processing_job import ProcessingJob
from app.models.transcript import Transcript
from app.models.upload import Upload
from app.schemas.clip import ClipResponse
from app.schemas.upload import UploadResponse
from app.schemas.upload_detail import UploadDetailResponse
from app.workers.celery_app import celery_app

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {"audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav"}
ALLOWED_EXTENSIONS = {".mp3", ".wav"}


@router.post("/upload", response_model=UploadResponse)
def upload_audio(file: UploadFile = File(...), db: Session = Depends(get_db)):
    settings = get_settings()
    extension = (os.path.splitext(file.filename or "upload.mp3")[1] or ".mp3").lower()

    # Some browsers/clients send generic MIME types (for example, application/octet-stream).
    # To keep operator UX simple, accept file when either MIME or extension is recognized.
    if file.content_type not in ALLOWED_MIME_TYPES and extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only MP3 and WAV files are supported")

    upload_id = str(uuid.uuid4())
    destination_path = os.path.join(settings.uploads_dir, f"{upload_id}{extension}")
    os.makedirs(settings.uploads_dir, exist_ok=True)

    with open(destination_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    upload = Upload(
        id=upload_id,
        original_filename=file.filename or f"{upload_id}{extension}",
        storage_path=destination_path,
        mime_type=file.content_type or "audio/mpeg",
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)

    logger.info("Upload stored and queued", extra={"upload_id": upload_id})
    celery_app.send_task("app.workers.tasks.process_upload_task", args=[upload_id])

    return upload


@router.get("/uploads", response_model=list[UploadResponse])
def list_uploads(db: Session = Depends(get_db)):
    return db.query(Upload).order_by(Upload.created_at.desc()).all()


@router.get("/uploads/{upload_id}", response_model=UploadDetailResponse)
def get_upload(upload_id: str, db: Session = Depends(get_db)):
    upload = db.query(Upload).filter(Upload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    transcript = db.query(Transcript).filter(Transcript.upload_id == upload_id).first()
    return UploadDetailResponse(
        id=upload.id,
        original_filename=upload.original_filename,
        mime_type=upload.mime_type,
        storage_path=upload.storage_path,
        status=upload.status,
        created_at=upload.created_at,
        updated_at=upload.updated_at,
        transcript_text=transcript.full_text if transcript else None,
    )


@router.get("/uploads/{upload_id}/transcript/download")
def download_transcript(
    upload_id: str,
    format: str = Query(default="txt", pattern="^(txt|json)$"),
    db: Session = Depends(get_db),
):
    """
    Download transcript artifacts produced by the pipeline.

    Integration point:
    - This is the canonical place for transcript downloads.
    - Keep this API stable so UI/reporting tools can link to it.
    """
    transcript = db.query(Transcript).filter(Transcript.upload_id == upload_id).first()
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not ready yet")

    if format == "txt":
        path = transcript.text_path
        media_type = "text/plain"
        filename = f"{upload_id}_transcript.txt"
    else:
        path = transcript.json_path
        media_type = "application/json"
        filename = f"{upload_id}_transcript.json"

    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Transcript file not found")

    return FileResponse(path=path, media_type=media_type, filename=filename)


@router.get("/uploads/{upload_id}/clips", response_model=list[ClipResponse])
def get_upload_clips(upload_id: str, db: Session = Depends(get_db)):
    return db.query(Clip).filter(Clip.upload_id == upload_id).order_by(Clip.score.desc()).all()


@router.get("/uploads/{upload_id}/jobs")
def get_upload_jobs(upload_id: str, db: Session = Depends(get_db)):
    """
    Returns stage-level processing job states for UI progress tracking.
    """
    jobs = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.upload_id == upload_id)
        .order_by(ProcessingJob.created_at.asc())
        .all()
    )
    return [
        {
            "id": job.id,
            "job_type": job.job_type,
            "status": job.status.value,
            "error_message": job.error_message,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
        }
        for job in jobs
    ]


@router.post("/clips/{clip_id}/approve", response_model=ClipResponse)
def approve_clip(clip_id: str, db: Session = Depends(get_db)):
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    clip.status = ClipStatus.approved
    db.commit()
    db.refresh(clip)
    return clip


@router.post("/clips/{clip_id}/reject", response_model=ClipResponse)
def reject_clip(clip_id: str, db: Session = Depends(get_db)):
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    clip.status = ClipStatus.rejected
    db.commit()
    db.refresh(clip)
    return clip


@router.get("/config/providers")
def get_provider_config():
    """
    Returns safe, non-secret runtime configuration for newsroom operators.

    Integration point:
    - Only expose non-sensitive settings here.
    - API keys must stay in environment variables and should never be returned.
    """
    settings = get_settings()
    return {
        "ai_analysis_provider": settings.ai_analysis_provider,
        "transcription_provider": settings.transcription_provider,
        "clip_extraction_provider": settings.clip_extraction_provider,
        "ollama_base_url": settings.ollama_base_url,
        "ollama_model": settings.ollama_model,
        "whisper_model": settings.whisper_model,
        "supported_ollama_models": ["llama3", "mistral", "deepseek-r1", "qwen"],
        "cloud_provider_keys_configured": {
            "openai": bool(settings.openai_api_key),
            "claude": bool(settings.claude_api_key),
            "deepgram": bool(settings.deepgram_api_key),
        },
    }
