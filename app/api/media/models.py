"""Pydantic models for media API request/response shapes."""

from pydantic import BaseModel


class MetadataAttributes(BaseModel):
    """Metadata attributes from the Bedrock KB metadata JSON file.

    Uses extra="allow" to preserve unknown fields (Req 6.6).
    Includes future fields last_modified_by and schema_version (Req 7.5).
    """

    video_id: str
    title: str
    url: str  # Original YouTube URL, never overwritten (Req 6.5)
    upload_date: str  # YYYYMMDD string, not ISO date (Req 6.4)
    playlists: str | None = None
    transcript_language: str | None = None
    processed_timestamp: str | None = None
    description: str | None = None
    # Future fields (Req 7.5)
    last_modified_by: str | None = None
    schema_version: str | None = None

    model_config = {"extra": "allow"}


class MetadataFile(BaseModel):
    """Top-level wrapper matching the Bedrock KB metadata JSON structure."""

    metadataAttributes: MetadataAttributes


class MediaItemSummary(BaseModel):
    """Media item in list context."""

    id: str
    title: str
    year: str
    upload_date: str
    media_type: str
    thumbnail_url: str | None
    has_thumbnail: bool


class MediaItemDetail(BaseModel):
    """Full media item detail with presigned URL, metadata, and transcript."""

    id: str
    title: str
    year: str
    media_type: str
    presigned_url: str
    thumbnail_url: str | None
    metadata: MetadataAttributes | None
    transcript: str | None
    transcript_available: bool


class MetadataUpdateRequest(BaseModel):
    """Request body for metadata update stub endpoint (Req 7.4)."""

    description: str


class YearsResponse(BaseModel):
    """Response for year listing endpoint."""

    years: list[str]


class MediaListResponse(BaseModel):
    """Paginated response for media listing endpoint."""

    items: list[MediaItemSummary]
    page: int
    page_size: int
    total: int
    next_page: int | None
