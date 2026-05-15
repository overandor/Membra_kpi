"""Create a timestamped SQLite backup for MEMBRA KPI.

Usage:
    python scripts/backup_sqlite.py

Environment:
    DB_PATH=./data/membra.db
    BACKUP_DIR=./backups
"""
from __future__ import annotations

import datetime as dt
import os
import shutil
from pathlib import Path


def main() -> None:
    db_path = Path(os.getenv("DB_PATH", "./data/membra.db"))
    backup_dir = Path(os.getenv("BACKUP_DIR", "./backups"))
    backup_dir.mkdir(parents=True, exist_ok=True)
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = backup_dir / f"membra-{stamp}.db"
    shutil.copy2(db_path, target)
    print(str(target))


if __name__ == "__main__":
    main()
