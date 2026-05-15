"""Production smoke test for a running MEMBRA KPI instance.

Usage:
    APP_BASE_URL=http://localhost:8000 python scripts/smoke_test.py
"""
from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request

BASE = os.getenv("APP_BASE_URL", "http://localhost:8000").rstrip("/")
ENDPOINTS = [
    "/api/health",
    "/api/ready",
    "/api/dashboard",
    "/",
    "/assetify",
    "/kpi",
    "/marketplace",
    "/proofbook",
    "/wallet",
    "/api-docs",
]


def get(path: str) -> tuple[int, str]:
    url = f"{BASE}{path}"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.status, response.read(500).decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(500).decode("utf-8", errors="ignore")


def main() -> None:
    failures: list[str] = []
    for endpoint in ENDPOINTS:
        status, body = get(endpoint)
        print(f"{status} {endpoint}")
        if status >= 400:
            failures.append(f"{endpoint} returned {status}: {body[:120]}")
    if failures:
        print("\nFAILURES:")
        for failure in failures:
            print(f"- {failure}")
        sys.exit(1)
    print("\nMEMBRA KPI smoke test passed.")


if __name__ == "__main__":
    main()
