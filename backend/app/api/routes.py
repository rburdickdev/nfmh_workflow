import logging
import os
import shutil
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
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
from app.schemas.youtube import YouTubeUploadRequest, YouTubeUploadResponse
from app.services.youtube_upload import upload_clip_to_youtube
from app.workers.celery_app import celery_app

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/m4a",
    "audio/mp4",
    "audio/x-m4a",
}
ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a"}


@router.post("/upload", response_model=UploadResponse)
def upload_audio(file: UploadFile = File(...), db: Session = Depends(get_db)):
    settings = get_settings()
    extension = (os.path.splitext(file.filename or "upload.mp3")[1] or ".mp3").lower()

    # Some browsers/clients send generic MIME types (for example, application/octet-stream).
    # To keep operator UX simple, accept file when either MIME or extension is recognized.
    if file.content_type not in ALLOWED_MIME_TYPES and extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only MP3, WAV, and M4A files are supported")

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


@router.get("/uploads/{upload_id}/audio")
def stream_uploaded_audio(upload_id: str, request: Request, db: Session = Depends(get_db)):
    upload = db.query(Upload).filter(Upload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    if not os.path.exists(upload.storage_path):
        raise HTTPException(status_code=404, detail="Uploaded audio file not found")
    file_size = os.path.getsize(upload.storage_path)
    range_header = request.headers.get("range")
    media_type = upload.mime_type or "audio/mpeg"

    if not range_header:
        return FileResponse(
            path=upload.storage_path,
            media_type=media_type,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Disposition": f'inline; filename="{upload.original_filename}"',
            },
        )

    range_value = range_header.replace("bytes=", "").strip()
    if "-" not in range_value:
        raise HTTPException(status_code=416, detail="Invalid Range header")

    start_text, end_text = range_value.split("-", 1)
    try:
        if start_text == "":
            suffix_length = int(end_text)
            start = max(file_size - suffix_length, 0)
            end = file_size - 1
        else:
            start = int(start_text)
            end = int(end_text) if end_text else file_size - 1
    except ValueError as exc:
        raise HTTPException(status_code=416, detail="Invalid Range header") from exc

    if start >= file_size or start < 0 or end < start:
        raise HTTPException(status_code=416, detail="Requested range not satisfiable")
    end = min(end, file_size - 1)
    content_length = end - start + 1

    def iter_file_range(path: str, start_offset: int, length: int):
        with open(path, "rb") as file_obj:
            file_obj.seek(start_offset)
            remaining = length
            while remaining > 0:
                chunk = file_obj.read(min(8192, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    return StreamingResponse(
        iter_file_range(upload.storage_path, start, content_length),
        status_code=206,
        media_type=media_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(content_length),
            "Content-Disposition": f'inline; filename="{upload.original_filename}"',
        },
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


@router.post("/clips/{clip_id}/youtube/upload", response_model=YouTubeUploadResponse)
def upload_clip_to_youtube_endpoint(
    clip_id: str,
    payload: YouTubeUploadRequest,
    db: Session = Depends(get_db),
):
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    if clip.status != ClipStatus.approved:
        raise HTTPException(status_code=400, detail="Clip must be approved before YouTube upload")
    if not os.path.exists(clip.clip_path):
        raise HTTPException(status_code=404, detail="Clip audio file not found")
    if not os.path.exists(clip.captions_path):
        raise HTTPException(status_code=404, detail="Clip captions file not found")

    upload = db.query(Upload).filter(Upload.id == clip.upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    try:
        result = upload_clip_to_youtube(
            settings=get_settings(),
            clip=clip,
            upload=upload,
            title=payload.title,
            description=payload.description,
            privacy_status=payload.privacy_status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("YouTube upload failed", extra={"clip_id": clip_id})
        raise HTTPException(status_code=500, detail=f"YouTube upload failed: {exc}") from exc

    return YouTubeUploadResponse(
        clip_id=clip.id,
        youtube_video_id=result.video_id,
        youtube_url=result.video_url,
        rendered_video_path=result.rendered_video_path,
        thumbnail_path=result.thumbnail_path,
    )


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
            "youtube": bool(
                settings.youtube_client_id
                and settings.youtube_client_secret
                and settings.youtube_refresh_token
            ),
        },
    }
