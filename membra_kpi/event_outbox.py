"""Persistent event outbox helpers for MEMBRA KPI.

Production pattern:
1. create canonical MEMBRA event
2. write event to local outbox in the same workflow as domain writes
3. deliver asynchronously/best-effort to downstream module sinks
4. preserve failed events for replay and audit
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from .events import make_event


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def ensure_event_outbox(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS event_outbox (
          outbox_id TEXT PRIMARY KEY,
          event_id TEXT UNIQUE NOT NULL,
          event_type TEXT NOT NULL,
          source_module TEXT NOT NULL,
          subject_type TEXT NOT NULL,
          subject_id TEXT NOT NULL,
          owner_id TEXT,
          payload_json TEXT NOT NULL,
          proof_hash TEXT,
          signature TEXT,
          status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','delivered','failed','dead_letter')),
          attempt_count INTEGER NOT NULL DEFAULT 0,
          last_attempt_at TEXT,
          last_error TEXT,
          created_at TEXT NOT NULL,
          delivered_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_event_outbox_status_created ON event_outbox(status, created_at);
        CREATE INDEX IF NOT EXISTS idx_event_outbox_subject ON event_outbox(subject_type, subject_id);
        CREATE INDEX IF NOT EXISTS idx_event_outbox_owner ON event_outbox(owner_id);
        """
    )


def enqueue_event(
    conn: sqlite3.Connection,
    event_type: str,
    *,
    subject_type: str,
    subject_id: str,
    owner_id: str | None = None,
    payload: dict[str, Any] | None = None,
    consent_scope: str | None = None,
    risk_level: str = "normal",
    correlation_id: str | None = None,
    causation_id: str | None = None,
) -> dict[str, Any]:
    ensure_event_outbox(conn)
    event = make_event(
        event_type,
        subject_type=subject_type,
        subject_id=subject_id,
        owner_id=owner_id,
        payload=payload or {},
        consent_scope=consent_scope,
        risk_level=risk_level,
        correlation_id=correlation_id,
        causation_id=causation_id,
    )
    conn.execute(
        """
        INSERT INTO event_outbox(
          outbox_id,event_id,event_type,source_module,subject_type,subject_id,owner_id,
          payload_json,proof_hash,signature,status,attempt_count,created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            new_id("outbox"),
            event["event_id"],
            event["event_type"],
            event["source_module"],
            event["subject_type"],
            event["subject_id"],
            event.get("owner_id"),
            json.dumps(event, sort_keys=True, default=str),
            event.get("proof_hash"),
            event.get("signature"),
            "pending",
            0,
            utc_now(),
        ),
    )
    return event


def pending_events(conn: sqlite3.Connection, *, limit: int = 50) -> list[dict[str, Any]]:
    ensure_event_outbox(conn)
    rows = conn.execute(
        "SELECT * FROM event_outbox WHERE status IN ('pending','failed') ORDER BY created_at ASC LIMIT ?",
        (limit,),
    ).fetchall()
    events = []
    for row in rows:
        item = dict(row) if not isinstance(row, tuple) else None
        if item is None:
            columns = [d[0] for d in conn.execute("SELECT * FROM event_outbox LIMIT 0").description]
            item = dict(zip(columns, row))
        event = json.loads(item["payload_json"])
        event["_outbox_id"] = item["outbox_id"]
        event["_attempt_count"] = item["attempt_count"]
        events.append(event)
    return events


def mark_delivered(conn: sqlite3.Connection, outbox_id: str) -> None:
    conn.execute(
        "UPDATE event_outbox SET status='delivered', delivered_at=?, last_attempt_at=?, last_error=NULL, attempt_count=attempt_count+1 WHERE outbox_id=?",
        (utc_now(), utc_now(), outbox_id),
    )


def mark_failed(conn: sqlite3.Connection, outbox_id: str, error: str, *, dead_letter_after: int = 10) -> None:
    row = conn.execute("SELECT attempt_count FROM event_outbox WHERE outbox_id=?", (outbox_id,)).fetchone()
    attempts = int(row[0] if isinstance(row, tuple) else row["attempt_count"]) if row else 0
    status = "dead_letter" if attempts + 1 >= dead_letter_after else "failed"
    conn.execute(
        "UPDATE event_outbox SET status=?, last_error=?, last_attempt_at=?, attempt_count=attempt_count+1 WHERE outbox_id=?",
        (status, error[:1000], utc_now(), outbox_id),
    )


def outbox_stats(conn: sqlite3.Connection) -> dict[str, int]:
    ensure_event_outbox(conn)
    rows = conn.execute("SELECT status, COUNT(*) FROM event_outbox GROUP BY status").fetchall()
    return {str(row[0]): int(row[1]) for row in rows}


def open_db(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    ensure_event_outbox(conn)
    return conn
