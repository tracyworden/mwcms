"""Health check endpoint — verifies S3 and DynamoDB connectivity."""

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.api.auth.models import _get_table
from app.api.config.media_config import MEDIA_SOURCES
from app.api.config.settings import get_settings
from app.api.s3.client import _get_s3_client

router = APIRouter()


@router.get("/health")
def health_check() -> JSONResponse:
    """Check S3 head_bucket and DynamoDB describe_table.

    Returns 200 with {"s3": "ok", "dynamodb": "ok"} when both pass,
    or 503 with details on which dependency failed.
    """
    result: dict[str, str] = {}
    bucket_name = MEDIA_SOURCES["video"].bucket_name
    settings = get_settings()

    # S3 check — use shared cached client
    try:
        _get_s3_client().head_bucket(Bucket=bucket_name)
        result["s3"] = "ok"
    except (ClientError, BotoCoreError):
        result["s3"] = "unreachable"

    # DynamoDB check — use shared cached table's underlying client
    try:
        _get_table().meta.client.describe_table(
            TableName=settings.DYNAMODB_TABLE_NAME
        )
        result["dynamodb"] = "ok"
    except (ClientError, BotoCoreError):
        result["dynamodb"] = "unreachable"

    all_ok = all(v == "ok" for v in result.values())
    return JSONResponse(content=result, status_code=200 if all_ok else 503)
