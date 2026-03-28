"""Application settings loaded from environment variables via pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    S3_BUCKET_NAME: str = "mw-family-videos-1"
    AWS_REGION: str = "us-east-1"
    SESSION_SECRET: str  # Required, no default
    DYNAMODB_TABLE_NAME: str = "User_Table"
    CORS_ALLOWED_ORIGINS: str = "http://localhost:5173"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Factory for use as a FastAPI dependency."""
    return Settings()
