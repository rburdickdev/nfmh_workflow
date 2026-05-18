from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.models.clip import ClipStatus


class ClipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    upload_id: str
    title: str
    hook_text: str
    reason: str
    score: float
    start_seconds: float
    end_seconds: float
    clip_path: str
    captions_path: str
    status: ClipStatus
    created_at: datetime

