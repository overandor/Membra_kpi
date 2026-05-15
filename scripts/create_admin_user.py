"""Create or rotate a MEMBRA KPI admin user in SQLite.

Usage:
    ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD='long-password' python scripts/create_admin_user.py

Environment:
    DB_PATH=./data/membra.db
"""
from __future__ import annotations

import datetime as dt
import os
import sqlite3
import uuid
from pathlib import Path

from membra_kpi.auth import hash_password, normalize_email

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv("DB_PATH", str(ROOT / "data" / "membra.db")))


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def main() -> None:
    email = normalize_email(os.getenv("ADMIN_EMAIL", ""))
    password = os.getenv("ADMIN_PASSWORD", "")
    display_name = os.getenv("ADMIN_DISPLAY_NAME", "MEMBRA Admin")
    if not email or not password:
        raise SystemExit("Set ADMIN_EMAIL and ADMIN_PASSWORD")
    password_hash = hash_password(password)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS users(user_id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,display_name TEXT NOT NULL,role TEXT NOT NULL,password_hash TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)")
        existing = conn.execute("SELECT user_id FROM users WHERE email=?", (email,)).fetchone()
        if existing:
            conn.execute("UPDATE users SET password_hash=?, role='admin', status='active', updated_at=? WHERE email=?", (password_hash, now(), email))
            print(f"rotated admin user: {email}")
        else:
            conn.execute("INSERT INTO users VALUES(?,?,?,?,?,?,?,?)", (f"user_{uuid.uuid4().hex[:12]}", email, display_name, "admin", password_hash, "active", now(), now()))
            print(f"created admin user: {email}")
        conn.commit()


if __name__ == "__main__":
    main()
