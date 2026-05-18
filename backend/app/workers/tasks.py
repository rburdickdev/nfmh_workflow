import logging

from celery.utils.log import get_task_logger

from app.db.session import SessionLocal
from app.services.pipeline import process_upload
from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)
logging.getLogger("app").setLevel(logging.INFO)


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def process_upload_task(self, upload_id: str) -> None:
    """
    Celery background task entrypoint.

    Retry behavior:
    - Retries transient failures (network hiccups, temporary file lock, etc.)
    - Marks upload as failed after max retries in pipeline error handling.
    """
    db = SessionLocal()
    try:
        logger.info("Starting upload task", extra={"upload_id": upload_id, "task_id": self.request.id})
        process_upload(upload_id, db)
    finally:
        db.close()
