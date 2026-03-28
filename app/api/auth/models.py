"""DynamoDB User_Table model and helper functions."""

from functools import lru_cache

import boto3
from pydantic import BaseModel

from app.api.config.settings import get_settings


class UserRecord(BaseModel):
    username: str
    password_hash: str


@lru_cache(maxsize=1)
def _get_table():
    """Return a boto3 DynamoDB Table resource for User_Table."""
    settings = get_settings()
    dynamodb = boto3.resource("dynamodb", region_name=settings.AWS_REGION)
    return dynamodb.Table(settings.DYNAMODB_TABLE_NAME)


def get_user(username: str) -> UserRecord | None:
    """Fetch a user by username from DynamoDB. Returns None if not found."""
    table = _get_table()
    response = table.get_item(Key={"username": username})
    item = response.get("Item")
    if item is None:
        return None
    return UserRecord(username=item["username"], password_hash=item["password_hash"])


def put_user(user: UserRecord) -> None:
    """Write a user record to DynamoDB."""
    table = _get_table()
    table.put_item(Item={"username": user.username, "password_hash": user.password_hash})
