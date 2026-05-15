"""Restore a MEMBRA KPI SQLite backup.

Usage:
    python scripts/restore_sqlite.py backups/membra-YYYYMMDDTHHMMSSZ.db

Environment:
    DB_PATH=./data/membra.db
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/restore_sqlite.py <backup-db-path>")
    source = Path(sys.argv[1])
    target = Path(os.getenv("DB_PATH", "./data/membra.db"))
    if not source.exists():
        raise SystemExit(f"Backup not found: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        safety_copy = target.with_suffix(target.suffix + ".pre-restore")
        shutil.copy2(target, safety_copy)
        print(f"Existing database copied to {safety_copy}")
    shutil.copy2(source, target)
    print(f"Restored {source} -> {target}")


if __name__ == "__main__":
    main()
