"""Media source configuration mapping media types to S3 bucket details."""

import os
from dataclasses import dataclass


@dataclass
class MediaSourceConfig:
    bucket_name: str
    file_extension: str  # e.g. ".mp4"
    metadata_suffix: str  # e.g. ".mp4.metadata.json"
    thumbnail_suffix: str  # e.g. ".jpg"
    transcript_suffix: str | None  # e.g. ".md", None if not applicable


def _load_media_sources() -> dict[str, MediaSourceConfig]:
    """Load media source config. Currently hardcoded for video;
    bucket name can be overridden via S3_BUCKET_NAME env var."""
    bucket = os.environ.get("S3_BUCKET_NAME", "mw-family-videos-1")
    return {
        "video": MediaSourceConfig(
            bucket_name=bucket,
            file_extension=".mp4",
            metadata_suffix=".mp4.metadata.json",
            thumbnail_suffix=".jpg",
            transcript_suffix=".md",
        )
    }


MEDIA_SOURCES: dict[str, MediaSourceConfig] = _load_media_sources()
