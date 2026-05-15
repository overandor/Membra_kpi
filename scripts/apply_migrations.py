"""Apply SQL migrations for MEMBRA KPI.

Usage:
    python scripts/apply_migrations.py

Environment:
    DB_PATH=./data/membra.db
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"
DB_PATH = Path(os.getenv("DB_PATH", str(ROOT / "data" / "membra.db")))


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations(version TEXT PRIMARY KEY, applied_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()}
        for path in sorted(MIGRATIONS.glob("*.sql")):
            if path.name in applied:
                print(f"skip {path.name}")
                continue
            print(f"apply {path.name}")
            conn.executescript(path.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations(version) VALUES(?)", (path.name,))
        conn.commit()
    print(f"migrations complete: {DB_PATH}")


if __name__ == "__main__":
    main()
