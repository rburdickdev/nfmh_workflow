from pydantic import BaseModel, Field


class YouTubeUploadRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    privacy_status: str | None = None


class YouTubeUploadResponse(BaseModel):
    clip_id: str
    youtube_video_id: str
    youtube_url: str
    rendered_video_path: str
    thumbnail_path: str
