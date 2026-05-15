"""Generate a strong MEMBRA admin token and SHA-256 hash.

Use the plain token only when making admin requests. Store the hash in
ADMIN_TOKEN_SHA256 for production.
"""
from __future__ import annotations

import hashlib
import secrets


def main() -> None:
    token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    print("MEMBRA_ADMIN_TOKEN_PLAIN=")
    print(token)
    print("\nADMIN_TOKEN_SHA256=")
    print(token_hash)
    print("\nStore only ADMIN_TOKEN_SHA256 in production secrets. Keep the plain token in your password manager.")


if __name__ == "__main__":
    main()
