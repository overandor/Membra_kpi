"""Authentication primitives for MEMBRA KPI.

This module is framework-light and production-oriented:
- PBKDF2-HMAC password hashing
- constant-time password verification
- opaque session token generation
- SHA-256 session token storage
- role checks for owner/operator/admin flows

The FastAPI app can use these helpers directly or migrate to a managed identity
provider later without changing the MEMBRA domain model.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from typing import Literal

PasswordAlgorithm = Literal["pbkdf2_sha256"]
Role = Literal["owner", "operator", "admin"]

PBKDF2_ITERATIONS = int(os.getenv("PBKDF2_ITERATIONS", "390000"))
SESSION_TOKEN_BYTES = int(os.getenv("SESSION_TOKEN_BYTES", "32"))


@dataclass(frozen=True)
class PasswordHash:
    algorithm: PasswordAlgorithm
    iterations: int
    salt_b64: str
    digest_b64: str

    def encode(self) -> str:
        return f"{self.algorithm}${self.iterations}${self.salt_b64}${self.digest_b64}"


@dataclass(frozen=True)
class SessionToken:
    plain: str
    digest: str


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def hash_password(password: str, *, iterations: int = PBKDF2_ITERATIONS) -> str:
    if not password or len(password) < 10:
        raise ValueError("Password must be at least 10 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return PasswordHash("pbkdf2_sha256", iterations, _b64(salt), _b64(digest)).encode()


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iter_text, salt_b64, digest_b64 = encoded_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iter_text)
        salt = _unb64(salt_b64)
        expected = _unb64(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def create_session_token() -> SessionToken:
    plain = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
    digest = hashlib.sha256(plain.encode("utf-8")).hexdigest()
    return SessionToken(plain=plain, digest=digest)


def digest_session_token(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def validate_role(role: str) -> Role:
    if role not in {"owner", "operator", "admin"}:
        raise ValueError("role must be owner, operator, or admin")
    return role  # type: ignore[return-value]


def can_review(role: str) -> bool:
    return role in {"operator", "admin"}


def can_admin(role: str) -> bool:
    return role == "admin"
