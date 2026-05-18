from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.models.upload import UploadStatus


class UploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    mime_type: str
    status: UploadStatus
    created_at: datetime

