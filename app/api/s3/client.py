"""S3 access layer with in-memory TTL cache.

Generic over media type config — all operations are parameterized by bucket name.
"""

import time
from functools import lru_cache
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.api.config.settings import get_settings

_cache: dict[str, tuple[float, Any]] = {}
CACHE_TTL = 60  # seconds


@lru_cache(maxsize=1)
def _get_s3_client():
    """Create a boto3 S3 client using the configured AWS region."""
    settings = get_settings()
    return boto3.client("s3", region_name=settings.AWS_REGION)


def _cache_get(key: str) -> Any | None:
    """Return cached value if present and not expired, else None."""
    if key in _cache:
        timestamp, value = _cache[key]
        if time.time() - timestamp < CACHE_TTL:
            return value
        del _cache[key]
    return None


def _cache_set(key: str, value: Any) -> None:
    """Store a value in the cache with the current timestamp."""
    _cache[key] = (time.time(), value)


def clear_cache() -> None:
    """Clear the entire TTL cache. Useful for testing."""
    _cache.clear()


def list_prefixes(bucket_name: str, delimiter: str = "/") -> list[str]:
    """List top-level prefixes (year folders) in a bucket.

    Returns a list of prefix strings, e.g. ["2014/", "2020/", "unknown_year/"].
    Results are cached for CACHE_TTL seconds.
    """
    cache_key = f"prefixes:{bucket_name}:{delimiter}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    client = _get_s3_client()
    prefixes: list[str] = []
    paginator = client.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket_name, Delimiter=delimiter):
        for cp in page.get("CommonPrefixes", []):
            prefixes.append(cp["Prefix"])

    _cache_set(cache_key, prefixes)
    return prefixes


def list_objects(bucket_name: str, prefix: str) -> list[str]:
    """List object keys under a given prefix in a bucket.

    Returns a list of full object keys, e.g. ["2020/abc.mp4", "2020/abc.jpg"].
    Results are cached for CACHE_TTL seconds.
    """
    cache_key = f"objects:{bucket_name}:{prefix}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    client = _get_s3_client()
    keys: list[str] = []
    paginator = client.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])

    _cache_set(cache_key, keys)
    return keys


def generate_presigned_url(
    bucket_name: str, key: str, expiration: int = 3600
) -> str:
    """Generate a presigned URL for an S3 object.

    Args:
        bucket_name: The S3 bucket name.
        key: The object key.
        expiration: URL expiration in seconds (max 3600).

    Returns:
        A presigned URL string.
    """
    expiration = min(expiration, 3600)
    client = _get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket_name, "Key": key},
        ExpiresIn=expiration,
    )


def object_exists(bucket_name: str, key: str) -> bool:
    """Check whether an S3 object exists using head_object.

    Returns True if the object exists, False otherwise.
    """
    client = _get_s3_client()
    try:
        client.head_object(Bucket=bucket_name, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        raise


def get_object_content(bucket_name: str, key: str) -> str:
    """Read an S3 object and return its body as a UTF-8 string.

    Used for metadata JSON and transcript markdown files.

    Raises:
        ClientError: If the object does not exist or cannot be read.
    """
    client = _get_s3_client()
    response = client.get_object(Bucket=bucket_name, Key=key)
    return response["Body"].read().decode("utf-8")
