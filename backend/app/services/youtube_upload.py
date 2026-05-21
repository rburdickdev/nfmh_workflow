import os
import subprocess
import textwrap
from dataclasses import dataclass
import logging

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError, ResumableUploadError
from googleapiclient.http import MediaFileUpload
from PIL import Image, ImageDraw, ImageFont

from app.core.config import Settings
from app.models.clip import Clip
from app.models.upload import Upload

logger = logging.getLogger(__name__)

YOUTUBE_UPLOAD_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
]


@dataclass
class YouTubeUploadArtifacts:
    video_path: str
    thumbnail_path: str


@dataclass
class YouTubeUploadResult:
    video_id: str
    video_url: str
    rendered_video_path: str
    thumbnail_path: str


def upload_clip_to_youtube(
    *,
    settings: Settings,
    clip: Clip,
    upload: Upload,
    title: str | None,
    description: str | None,
    privacy_status: str | None,
) -> YouTubeUploadResult:
    _validate_youtube_config(settings)
    artifacts = _render_assets(settings=settings, clip=clip)
    youtube = _build_youtube_client(settings)

    resolved_title = (title or clip.title or "Newsroom clip").strip()
    resolved_description = (
        description
        or _build_default_description(upload_filename=upload.original_filename, clip=clip)
    ).strip()
    resolved_privacy = (privacy_status or settings.youtube_privacy_status).strip()
    tags = [tag.strip() for tag in settings.youtube_default_tags.split(",") if tag.strip()]

    video_insert = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": resolved_title[:100],
                "description": resolved_description[:5000],
                "categoryId": settings.youtube_category_id,
                "tags": tags,
            },
            "status": {
                "privacyStatus": resolved_privacy,
                "selfDeclaredMadeForKids": False,
            },
        },
        media_body=MediaFileUpload(artifacts.video_path, chunksize=-1, resumable=True),
    )
    video_response = _execute_resumable(video_insert)
    video_id = video_response["id"]

    try:
        thumbnail_insert = youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(artifacts.thumbnail_path, chunksize=-1, resumable=False),
        )
        thumbnail_insert.execute()
    except Exception as exc:
        logger.warning(
            "YouTube thumbnail upload failed; continuing without thumbnail",
            extra={"video_id": video_id, "thumbnail_path": artifacts.thumbnail_path, "error": str(exc)},
        )

    try:
        captions_insert = youtube.captions().insert(
            part="snippet",
            body={
                "snippet": {
                    "videoId": video_id,
                    "language": "en",
                    "name": "English captions",
                    "isDraft": False,
                }
            },
            media_body=MediaFileUpload(clip.captions_path, mimetype="application/octet-stream"),
        )
        captions_insert.execute()
    except Exception as exc:
        logger.warning(
            "YouTube caption upload failed; continuing without caption track",
            extra={"video_id": video_id, "captions_path": clip.captions_path, "error": str(exc)},
        )

    return YouTubeUploadResult(
        video_id=video_id,
        video_url=f"https://www.youtube.com/watch?v={video_id}",
        rendered_video_path=artifacts.video_path,
        thumbnail_path=artifacts.thumbnail_path,
    )


def _build_default_description(*, upload_filename: str, clip: Clip) -> str:
    return "\n".join(
        [
            f"Source: {upload_filename}",
            f"Clip window: {clip.start_seconds:.1f}s - {clip.end_seconds:.1f}s",
            "",
            clip.hook_text.strip(),
        ]
    )


def _validate_youtube_config(settings: Settings) -> None:
    missing = [
        key
        for key, value in {
            "YOUTUBE_CLIENT_ID": settings.youtube_client_id,
            "YOUTUBE_CLIENT_SECRET": settings.youtube_client_secret,
            "YOUTUBE_REFRESH_TOKEN": settings.youtube_refresh_token,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(f"Missing YouTube configuration: {', '.join(missing)}")


def _build_youtube_client(settings: Settings):
    credentials = Credentials(
        token=None,
        refresh_token=settings.youtube_refresh_token,
        token_uri=settings.youtube_token_uri,
        client_id=settings.youtube_client_id,
        client_secret=settings.youtube_client_secret,
        scopes=YOUTUBE_UPLOAD_SCOPES,
    )
    try:
        credentials.refresh(Request())
    except RefreshError as exc:
        raise ValueError(
            "Unable to refresh YouTube OAuth token. Recreate YOUTUBE_REFRESH_TOKEN "
            "with scope https://www.googleapis.com/auth/youtube.upload."
        ) from exc
    return build("youtube", "v3", credentials=credentials, cache_discovery=False)


def _render_assets(*, settings: Settings, clip: Clip) -> YouTubeUploadArtifacts:
    os.makedirs(settings.youtube_videos_dir, exist_ok=True)
    os.makedirs(settings.youtube_thumbnails_dir, exist_ok=True)

    thumbnail_path = os.path.join(settings.youtube_thumbnails_dir, f"{clip.id}.png")
    output_video_path = os.path.join(settings.youtube_videos_dir, f"{clip.id}.mp4")

    _create_thumbnail_image(path=thumbnail_path, title=clip.title, hook_text=clip.hook_text)
    _render_vertical_video(
        thumbnail_path=thumbnail_path,
        source_audio_path=clip.clip_path,
        output_video_path=output_video_path,
    )
    return YouTubeUploadArtifacts(video_path=output_video_path, thumbnail_path=thumbnail_path)


def _create_thumbnail_image(*, path: str, title: str, hook_text: str) -> None:
    width, height = 1280, 720
    image = Image.new("RGB", (width, height), color=(17, 24, 39))
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.load_default()
    body_font = ImageFont.load_default()

    safe_title = (title or "Newsroom Clip").strip()
    safe_hook = (hook_text or "").strip()
    wrapped_title = textwrap.fill(safe_title[:140], width=36)
    wrapped_hook = textwrap.fill(safe_hook[:280], width=48)

    draw.rectangle([(40, 40), (width - 40, height - 40)], outline=(59, 130, 246), width=4)
    draw.text((80, 90), "NEWSROOM CLIP", fill=(148, 163, 184), font=body_font)
    draw.text((80, 150), wrapped_title, fill=(255, 255, 255), font=title_font)
    draw.text((80, 300), wrapped_hook, fill=(203, 213, 225), font=body_font)
    draw.text((80, height - 90), "Generated automatically", fill=(148, 163, 184), font=body_font)
    image.save(path, "PNG")


def _render_vertical_video(*, thumbnail_path: str, source_audio_path: str, output_video_path: str) -> None:
    filter_chain = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    command = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-framerate",
        "30",
        "-i",
        thumbnail_path,
        "-i",
        source_audio_path,
        "-vf",
        filter_chain,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        "-c:a",
        "aac",
        "-ar",
        "44100",
        "-ac",
        "2",
        "-shortest",
        output_video_path,
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Failed to render YouTube MP4 for clip {output_video_path}") from exc


def _execute_resumable(request):
    response = None
    try:
        while response is None:
            _, response = request.next_chunk()
        return response
    except ResumableUploadError as exc:
        raise ValueError(_friendly_youtube_error(exc)) from exc
    except HttpError as exc:
        raise ValueError(_friendly_youtube_error(exc)) from exc


def _friendly_youtube_error(exc: Exception) -> str:
    details = str(exc)
    if "youtubeSignupRequired" in details:
        return (
            "YouTube API is authorized, but the Google account does not have an active "
            "YouTube channel. Sign in to YouTube with this same account, create/activate a "
            "channel, accept terms, then retry."
        )
    if "Unauthorized" in details:
        return (
            "YouTube API request was unauthorized. Confirm the OAuth client, refresh token, "
            "and Google account all belong to the same project/account."
        )
    return f"YouTube API error: {details}"
