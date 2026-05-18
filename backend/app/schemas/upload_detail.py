from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.models.upload import UploadStatus


class UploadDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    mime_type: str
    storage_path: str
    status: UploadStatus
    created_at: datetime
    updated_at: datetime
    transcript_text: str | None = None

