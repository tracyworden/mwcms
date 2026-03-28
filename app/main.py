"""FastAPI application entry point."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.api.auth.router import router as auth_router
from app.api.config.settings import get_settings
from app.api.health.router import router as health_router
from app.api.media.router import router as media_router

app = FastAPI(title="Our Media Viewer")

app.include_router(auth_router, prefix="/api/auth")
app.include_router(health_router)
app.include_router(media_router, prefix="/api/media")

# CORS — origins from settings (comma-separated), locked down from wildcard
settings = get_settings()
origins = [o.strip() for o in settings.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HSTSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app.add_middleware(HSTSMiddleware)

# Serve React frontend build output (after API routers so API routes take priority)
_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="static")
