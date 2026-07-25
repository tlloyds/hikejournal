from __future__ import annotations

from pathlib import Path


VIDEO_EXTENSIONS = {"mp4", "mov", "m4v", "3gp", "webm"}
VIDEO_CONTENT_TYPES = {
    "mp4": "video/mp4",
    "mov": "video/quicktime",
    "m4v": "video/x-m4v",
    "3gp": "video/3gpp",
    "webm": "video/webm",
}


def media_extension(filename: str) -> str:
    return Path(filename or "").suffix.lower().lstrip(".")


def is_video(photo: dict) -> bool:
    return str(photo.get("content_type") or "").lower().startswith("video/")


def is_supported_video_upload(filename: str, content_type: str | None = None) -> bool:
    return media_extension(filename) in VIDEO_EXTENSIONS or str(content_type or "").lower().startswith("video/")


def video_content_type(filename: str, reported_content_type: str | None = None) -> str:
    content_type = str(reported_content_type or "").lower().strip()
    if content_type.startswith("video/"):
        return content_type
    return VIDEO_CONTENT_TYPES.get(media_extension(filename), "video/mp4")
