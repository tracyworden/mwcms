"""Auth router — login and logout endpoints."""

from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, HTTPException
from jose import jwt
from pydantic import BaseModel

from app.api.auth.models import get_user
from app.api.config.settings import get_settings

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginRequest):
    """Verify credentials against DynamoDB, return HS256 JWT."""
    user = get_user(body.username)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not bcrypt.checkpw(
        body.password.encode("utf-8"), user.password_hash.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.username,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=24)).timestamp()),
    }
    token = jwt.encode(payload, settings.SESSION_SECRET, algorithm="HS256")
    return {"token": token}


@router.post("/logout")
def logout():
    """Client-side token clearing — just return 200."""
    return {"detail": "Logged out"}
