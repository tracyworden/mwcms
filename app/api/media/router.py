"""Media listing endpoints."""

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, Depends, HTTPException, Query, status
from botocore.exceptions import ClientError

from app.api.auth.dependencies import require_auth
from app.api.config.media_config import MEDIA_SOURCES
from app.api.media.models import (
    MediaItemDetail,
    MediaItemSummary,
    MediaListResponse,
    MetadataAttributes,
    MetadataUpdateRequest,
    YearsResponse,
)
from app.api.s3.client import (
    generate_presigned_url,
    get_object_content,
    list_objects,
    list_prefixes,
    object_exists,
)

logger = logging.getLogger(__name__)


router = APIRouter(tags=["media"])


def _sort_years(raw_prefixes: list[str]) -> list[str]:
    """Sort year names: numeric years reverse chronological, unknown_year last."""
    years = [p.strip("/") for p in raw_prefixes]
    numeric = sorted([y for y in years if y.isdigit()], reverse=True)
    non_numeric = [y for y in years if not y.isdigit()]
    # Put unknown_year at the very end, other non-numeric before it
    unknown = [y for y in non_numeric if y == "unknown_year"]
    other = [y for y in non_numeric if y != "unknown_year"]
    return numeric + other + unknown


@router.get("/years", response_model=YearsResponse)
def list_years(username: str = Depends(require_auth)) -> YearsResponse:
    """List year-folder prefixes from the media bucket, sorted reverse chronological."""
    video_config = MEDIA_SOURCES.get("video")
    if video_config is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No video media source configured",
        )

    try:
        raw_prefixes = list_prefixes(video_config.bucket_name)
    except ClientError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Media storage unavailable",
        )

    return YearsResponse(years=_sort_years(raw_prefixes))


def _read_metadata(bucket_name: str, year: str, item_id: str, metadata_suffix: str) -> dict:
    """Try to read metadata JSON for an item. Returns dict with title/upload_date or defaults."""
    metadata_key = f"{year}/{item_id}{metadata_suffix}"
    try:
        raw = get_object_content(bucket_name, metadata_key)
        data = json.loads(raw)
        attrs = data.get("metadataAttributes", {})
        return {
            "title": attrs.get("title", item_id),
            "upload_date": attrs.get("upload_date", ""),
        }
    except (ClientError, json.JSONDecodeError, Exception):
        return {"title": item_id, "upload_date": ""}


@router.get("/years/{year}", response_model=MediaListResponse)
def list_media_by_year(
    year: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = Query("date"),
    type: str = Query("video"),
    username: str = Depends(require_auth),
) -> MediaListResponse:
    """Paginated listing of media items in a year folder."""
    # Validate sort param
    if sort != "date":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported sort value. Supported: date",
        )

    video_config = MEDIA_SOURCES.get(type)
    if video_config is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported media type: {type}",
        )

    try:
        all_keys = list_objects(video_config.bucket_name, f"{year}/")
    except ClientError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Media storage unavailable",
        )

    # Build a set of all keys for quick thumbnail lookup
    key_set = set(all_keys)

    # Filter for media files by extension (e.g. .mp4)
    ext = video_config.file_extension
    media_keys = [k for k in all_keys if k.endswith(ext)]

    # Sort by key for consistent ordering
    media_keys.sort()

    total = len(media_keys)

    # Paginate
    start = (page - 1) * page_size
    end = start + page_size
    page_keys = media_keys[start:end]

    # Build items for this page — fetch thumbnails + metadata in parallel
    def _build_summary(key: str) -> MediaItemSummary:
        filename = key.split("/", 1)[1]
        item_id = filename[: -len(ext)]

        thumb_key = f"{year}/{item_id}{video_config.thumbnail_suffix}"
        has_thumbnail = thumb_key in key_set
        thumbnail_url = None
        if has_thumbnail:
            try:
                thumbnail_url = generate_presigned_url(
                    video_config.bucket_name, thumb_key
                )
            except ClientError:
                has_thumbnail = False

        meta = _read_metadata(
            video_config.bucket_name, year, item_id, video_config.metadata_suffix
        )

        return MediaItemSummary(
            id=item_id,
            title=meta["title"],
            year=year,
            upload_date=meta["upload_date"],
            media_type=type,
            thumbnail_url=thumbnail_url,
            has_thumbnail=has_thumbnail,
        )

    with ThreadPoolExecutor(max_workers=min(len(page_keys), 10)) as pool:
        futures = {pool.submit(_build_summary, key): i for i, key in enumerate(page_keys)}
        items: list[MediaItemSummary | None] = [None] * len(page_keys)
        for future in as_completed(futures):
            items[futures[future]] = future.result()
    items = [item for item in items if item is not None]

    next_page = page + 1 if end < total else None

    return MediaListResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        next_page=next_page,
    )


def _read_full_metadata(
    bucket_name: str, year: str, item_id: str, metadata_suffix: str
) -> MetadataAttributes | None:
    """Read and parse the full metadata JSON for an item.

    Returns MetadataAttributes on success, None on any failure (graceful degradation).
    """
    metadata_key = f"{year}/{item_id}{metadata_suffix}"
    try:
        raw = get_object_content(bucket_name, metadata_key)
        data = json.loads(raw)
        attrs = data.get("metadataAttributes", {})
        return MetadataAttributes(**attrs)
    except (ClientError, json.JSONDecodeError, Exception) as exc:
        logger.warning("Failed to read metadata %s: %s", metadata_key, exc)
        return None


def _read_transcript(
    bucket_name: str, year: str, item_id: str, transcript_suffix: str
) -> tuple[str | None, bool]:
    """Read transcript markdown for an item.

    Returns (content, available). On failure returns (None, False).
    """
    transcript_key = f"{year}/{item_id}{transcript_suffix}"
    try:
        content = get_object_content(bucket_name, transcript_key)
        return content, True
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code == "NoSuchKey":
            logger.debug("No transcript found: %s", transcript_key)
        else:
            logger.warning("Failed to read transcript %s: %s", transcript_key, exc)
        return None, False
    except Exception as exc:
        logger.warning("Failed to read transcript %s: %s", transcript_key, exc)
        return None, False


@router.get("/items/{item_id}", response_model=MediaItemDetail)
def get_media_item_detail(
    item_id: str,
    year: str = Query(..., description="Year folder containing the media item"),
    username: str = Depends(require_auth),
) -> MediaItemDetail:
    """Full detail for a single media item: presigned URL, metadata, transcript, thumbnail."""
    video_config = MEDIA_SOURCES.get("video")
    if video_config is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No video media source configured",
        )

    bucket = video_config.bucket_name
    ext = video_config.file_extension
    media_key = f"{year}/{item_id}{ext}"

    # Check .mp4 exists — 404 if not
    try:
        if not object_exists(bucket, media_key):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Media item not found",
            )
    except ClientError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Media storage unavailable",
        )

    # Generate presigned URL for the video
    presigned_url = generate_presigned_url(bucket, media_key)

    # Thumbnail (optional)
    thumb_key = f"{year}/{item_id}{video_config.thumbnail_suffix}"
    thumbnail_url = None
    try:
        if object_exists(bucket, thumb_key):
            thumbnail_url = generate_presigned_url(bucket, thumb_key)
    except ClientError:
        pass  # graceful — no thumbnail

    # Metadata (graceful degradation → null)
    metadata = _read_full_metadata(
        bucket, year, item_id, video_config.metadata_suffix
    )

    # Transcript (graceful degradation → null, false)
    transcript: str | None = None
    transcript_available = False
    if video_config.transcript_suffix:
        transcript, transcript_available = _read_transcript(
            bucket, year, item_id, video_config.transcript_suffix
        )

    # Derive title from metadata or fall back to item_id
    title = metadata.title if metadata else item_id

    return MediaItemDetail(
        id=item_id,
        title=title,
        year=year,
        media_type="video",
        presigned_url=presigned_url,
        thumbnail_url=thumbnail_url,
        metadata=metadata,
        transcript=transcript,
        transcript_available=transcript_available,
    )


@router.patch("/items/{item_id}/metadata", status_code=501)
def update_media_metadata(
    item_id: str,
    body: MetadataUpdateRequest,
    username: str = Depends(require_auth),
):
    """Stub endpoint for metadata editing. Validates payload, then returns 501."""
    return {"detail": "Metadata editing not yet implemented"}
