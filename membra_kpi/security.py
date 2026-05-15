"""Production security helpers for MEMBRA KPI.

These helpers are intentionally dependency-light so they work on Replit and in
container deployments. They provide upload validation, rate limiting primitives,
admin-token verification, response security headers, and Vercel frontend CORS.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Deque

from fastapi import HTTPException, Request
from PIL import Image

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_DATA_EXTENSIONS = {".csv", ".xlsx", ".xls"}
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "12"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "120"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
CORS_ALLOWED_ORIGINS = [origin.strip().rstrip("/") for origin in os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",") if origin.strip()]
SENSITIVE_UPLOAD_WARNING = "Do not upload private keys, seed phrases, raw financial credentials, or unconsented personal material."

_rate_windows: dict[str, Deque[float]] = defaultdict(deque)


def client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request) -> None:
    key = client_key(request)
    now = time.monotonic()
    window = _rate_windows[key]
    while window and now - window[0] > RATE_LIMIT_WINDOW_SECONDS:
        window.popleft()
    if len(window) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    window.append(now)


def verify_admin_token(provided: str | None, *, plain_token: str, token_hash: str | None = None) -> bool:
    provided = provided or ""
    if token_hash:
        digest = hashlib.sha256(provided.encode("utf-8")).hexdigest()
        return hmac.compare_digest(digest, token_hash)
    return bool(plain_token) and hmac.compare_digest(provided, plain_token)


def validate_upload_size(data: bytes) -> None:
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"Upload too large. Limit is {MAX_UPLOAD_MB} MB")


def validate_image_upload(filename: str, content_type: str | None, data: bytes) -> None:
    validate_upload_size(data)
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported image extension. Allowed: {sorted(ALLOWED_IMAGE_EXTENSIONS)}")
    if content_type and content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported image content type: {content_type}")
    try:
        from io import BytesIO
        with Image.open(BytesIO(data)) as image:
            image.verify()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid image upload: {exc}")


def validate_data_upload(filename: str, data: bytes) -> None:
    validate_upload_size(data)
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_DATA_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported data extension. Allowed: {sorted(ALLOWED_DATA_EXTENSIONS)}")


def cors_origin_for(response) -> str:
    # Without the request object in this helper, use an explicit deployment allowlist.
    # If CORS_ALLOWED_ORIGINS is "*", the backend is intentionally public-readable for dashboard APIs.
    if not CORS_ALLOWED_ORIGINS or CORS_ALLOWED_ORIGINS == ["*"]:
        return "*"
    return CORS_ALLOWED_ORIGINS[0]


def apply_security_headers(response) -> None:
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Access-Control-Allow-Origin"] = cors_origin_for(response)
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, x-admin-token"
    response.headers["Vary"] = "Origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )
