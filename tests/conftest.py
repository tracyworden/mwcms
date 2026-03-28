"""Shared test fixtures — mocked AWS services, FastAPI TestClient, auth helpers.

Moto mocks are started BEFORE importing the app to ensure all boto3 clients
hit the mock endpoints. Environment variables are set before pydantic-settings
reads them.
"""

import json
import os

import bcrypt
import boto3
import pytest
from moto import mock_aws

# ---------------------------------------------------------------------------
# 1. Fake AWS credentials (autouse — always active)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def aws_credentials():
    """Set fake AWS credentials so boto3 never hits real AWS."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    yield
    for key in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SECURITY_TOKEN",
        "AWS_SESSION_TOKEN",
        "AWS_DEFAULT_REGION",
    ):
        os.environ.pop(key, None)


# ---------------------------------------------------------------------------
# 2. Application settings via env vars
# ---------------------------------------------------------------------------

TEST_JWT_SECRET = "test-secret-key-for-jwt"
TEST_BUCKET = "mw-family-videos-1"
TEST_REGION = "us-east-1"
TEST_TABLE = "User_Table"
TEST_USERNAME = "testuser"
TEST_PASSWORD = "testpass123"


@pytest.fixture()
def test_settings():
    """Set env vars that pydantic-settings and media_config read."""
    os.environ["SESSION_SECRET"] = TEST_JWT_SECRET
    os.environ["S3_BUCKET_NAME"] = TEST_BUCKET
    os.environ["AWS_REGION"] = TEST_REGION
    os.environ["DYNAMODB_TABLE_NAME"] = TEST_TABLE
    yield
    for key in ("SESSION_SECRET", "S3_BUCKET_NAME", "AWS_REGION", "DYNAMODB_TABLE_NAME"):
        os.environ.pop(key, None)


# ---------------------------------------------------------------------------
# 3. Metadata helpers
# ---------------------------------------------------------------------------

_VIDEO_1_METADATA = {
    "metadataAttributes": {
        "video_id": "test-video-1",
        "title": "Test Video One",
        "url": "https://www.youtube.com/watch?v=test-video-1",
        "upload_date": "20200315",
        "playlists": "Family",
        "transcript_language": "en",
        "processed_timestamp": "2020-03-20T10:00:00Z",
        "description": "A test video description",
    }
}

_VIDEO_2_METADATA = {
    "metadataAttributes": {
        "video_id": "test-video-2",
        "title": "Test Video Two",
        "url": "https://www.youtube.com/watch?v=test-video-2",
        "upload_date": "20200410",
        "playlists": "",
        "transcript_language": "en",
        "processed_timestamp": "2020-04-15T12:00:00Z",
        "description": "Second test video",
    }
}

_OLD_VIDEO_METADATA = {
    "metadataAttributes": {
        "video_id": "old-video",
        "title": "Old Video",
        "url": "https://www.youtube.com/watch?v=old-video",
        "upload_date": "20140601",
        "playlists": "Archive",
        "transcript_language": "en",
        "processed_timestamp": "2014-06-05T08:00:00Z",
        "description": "An old video",
    }
}

_MYSTERY_METADATA = {
    "metadataAttributes": {
        "video_id": "mystery",
        "title": "Mystery Video",
        "url": "https://www.youtube.com/watch?v=mystery",
        "upload_date": "",
        "playlists": "",
        "transcript_language": "en",
        "processed_timestamp": "2023-01-01T00:00:00Z",
        "description": "Unknown year video",
    }
}


# ---------------------------------------------------------------------------
# 4. Mocked S3 with pre-populated test bucket
# ---------------------------------------------------------------------------

@pytest.fixture()
def s3_mock(aws_credentials, test_settings):
    """Start moto S3 mock and populate the test bucket with test data."""
    with mock_aws():
        s3 = boto3.client("s3", region_name=TEST_REGION)
        s3.create_bucket(Bucket=TEST_BUCKET)

        # --- 2020/ folder ---
        # test-video-1: has .mp4, .metadata.json, .md (transcript), .jpg (thumbnail)
        s3.put_object(Bucket=TEST_BUCKET, Key="2020/test-video-1.mp4", Body=b"")
        s3.put_object(
            Bucket=TEST_BUCKET,
            Key="2020/test-video-1.mp4.metadata.json",
            Body=json.dumps(_VIDEO_1_METADATA).encode(),
        )
        s3.put_object(
            Bucket=TEST_BUCKET,
            Key="2020/test-video-1.md",
            Body=b"## Transcript\n\nHello from test video one.",
        )
        s3.put_object(
            Bucket=TEST_BUCKET,
            Key="2020/test-video-1.jpg",
            Body=b"\xff\xd8\xff\xe0fake-jpeg-bytes",
        )

        # test-video-2: has .mp4 and .metadata.json only (no thumbnail, no transcript)
        s3.put_object(Bucket=TEST_BUCKET, Key="2020/test-video-2.mp4", Body=b"")
        s3.put_object(
            Bucket=TEST_BUCKET,
            Key="2020/test-video-2.mp4.metadata.json",
            Body=json.dumps(_VIDEO_2_METADATA).encode(),
        )

        # --- 2014/ folder ---
        s3.put_object(Bucket=TEST_BUCKET, Key="2014/old-video.mp4", Body=b"")
        s3.put_object(
            Bucket=TEST_BUCKET,
            Key="2014/old-video.mp4.metadata.json",
            Body=json.dumps(_OLD_VIDEO_METADATA).encode(),
        )
        s3.put_object(
            Bucket=TEST_BUCKET,
            Key="2014/old-video.jpg",
            Body=b"\xff\xd8\xff\xe0fake-jpeg-bytes",
        )

        # --- unknown_year/ folder ---
        s3.put_object(Bucket=TEST_BUCKET, Key="unknown_year/mystery.mp4", Body=b"")
        s3.put_object(
            Bucket=TEST_BUCKET,
            Key="unknown_year/mystery.mp4.metadata.json",
            Body=json.dumps(_MYSTERY_METADATA).encode(),
        )

        yield s3


# ---------------------------------------------------------------------------
# 5. Mocked DynamoDB with User_Table and test user
# ---------------------------------------------------------------------------

@pytest.fixture()
def dynamodb_mock(aws_credentials, test_settings):
    """Start moto DynamoDB mock, create User_Table, insert test user."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name=TEST_REGION)
        dynamodb.create_table(
            TableName=TEST_TABLE,
            KeySchema=[{"AttributeName": "username", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "username", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        # Insert test user with bcrypt-hashed password
        hashed = bcrypt.hashpw(TEST_PASSWORD.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        table = dynamodb.Table(TEST_TABLE)
        table.put_item(Item={"username": TEST_USERNAME, "password_hash": hashed})

        yield dynamodb


# ---------------------------------------------------------------------------
# 6. Combined AWS mock (S3 + DynamoDB in one context)
# ---------------------------------------------------------------------------

@pytest.fixture()
def aws_mocks(aws_credentials, test_settings):
    """Single mock_aws context with both S3 and DynamoDB populated.

    Use this when tests need both services simultaneously (e.g. TestClient
    hitting endpoints that touch S3 and auth/DynamoDB).
    """
    with mock_aws():
        # --- S3 ---
        s3 = boto3.client("s3", region_name=TEST_REGION)
        s3.create_bucket(Bucket=TEST_BUCKET)

        s3.put_object(Bucket=TEST_BUCKET, Key="2020/test-video-1.mp4", Body=b"")
        s3.put_object(
            Bucket=TEST_BUCKET,
            Key="2020/test-video-1.mp4.metadata.json",
            Body=json.dumps(_VIDEO_1_METADATA).encode(),
        )
        s3.put_object(
            Bucket=TEST_BUCKET,
            Key="2020/test-video-1.md",
            Body=b"## Transcript\n\nHello from test video one.",
        )
        s3.put_object(
            Bucket=TEST_BUCKET,
            Key="2020/test-video-1.jpg",
            Body=b"\xff\xd8\xff\xe0fake-jpeg-bytes",
        )
        s3.put_object(Bucket=TEST_BUCKET, Key="2020/test-video-2.mp4", Body=b"")
        s3.put_object(
            Bucket=TEST_BUCKET,
            Key="2020/test-video-2.mp4.metadata.json",
            Body=json.dumps(_VIDEO_2_METADATA).encode(),
        )
        s3.put_object(Bucket=TEST_BUCKET, Key="2014/old-video.mp4", Body=b"")
        s3.put_object(
            Bucket=TEST_BUCKET,
            Key="2014/old-video.mp4.metadata.json",
            Body=json.dumps(_OLD_VIDEO_METADATA).encode(),
        )
        s3.put_object(
            Bucket=TEST_BUCKET,
            Key="2014/old-video.jpg",
            Body=b"\xff\xd8\xff\xe0fake-jpeg-bytes",
        )
        s3.put_object(Bucket=TEST_BUCKET, Key="unknown_year/mystery.mp4", Body=b"")
        s3.put_object(
            Bucket=TEST_BUCKET,
            Key="unknown_year/mystery.mp4.metadata.json",
            Body=json.dumps(_MYSTERY_METADATA).encode(),
        )

        # --- DynamoDB ---
        dynamodb = boto3.resource("dynamodb", region_name=TEST_REGION)
        dynamodb.create_table(
            TableName=TEST_TABLE,
            KeySchema=[{"AttributeName": "username", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "username", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        hashed = bcrypt.hashpw(TEST_PASSWORD.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        table = dynamodb.Table(TEST_TABLE)
        table.put_item(Item={"username": TEST_USERNAME, "password_hash": hashed})

        yield {"s3": s3, "dynamodb": dynamodb}


# ---------------------------------------------------------------------------
# 7. FastAPI TestClient (requires aws_mocks for both S3 + DynamoDB)
# ---------------------------------------------------------------------------

@pytest.fixture()
def test_client(aws_mocks):
    """FastAPI TestClient with mocked AWS services.

    Clears the S3 TTL cache before each test so stale data doesn't leak.
    Reloads MEDIA_SOURCES so it picks up the test bucket env var.
    """
    from app.api.s3.client import clear_cache
    clear_cache()

    # Reload media config so MEDIA_SOURCES reads the test env var
    import app.api.config.media_config as media_config_mod
    media_config_mod.MEDIA_SOURCES = media_config_mod._load_media_sources()

    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        yield client

    clear_cache()


# ---------------------------------------------------------------------------
# 8. Auth token helper
# ---------------------------------------------------------------------------

@pytest.fixture()
def auth_token(test_client):
    """Log in as the test user and return the JWT token string."""
    response = test_client.post(
        "/api/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["token"]


@pytest.fixture()
def auth_headers(auth_token):
    """Return Authorization headers dict for authenticated requests."""
    return {"Authorization": f"Bearer {auth_token}"}
