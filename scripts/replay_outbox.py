"""Replay pending MEMBRA KPI event outbox records to configured sinks.

Usage:
    MEMBRA_EVENT_SINKS=http://localhost:8002/api/events/ingest python scripts/replay_outbox.py

Environment:
    DB_PATH=./data/membra.db
    MEMBRA_EVENT_SINKS=http://service-a/api/events/ingest,http://service-b/api/events/ingest
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from membra_kpi.event_outbox import mark_delivered, mark_failed, open_db, pending_events
from membra_kpi.events import deliver_event

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv("DB_PATH", str(ROOT / "data" / "membra.db")))
LIMIT = int(os.getenv("OUTBOX_REPLAY_LIMIT", "50"))


async def main() -> None:
    with open_db(DB_PATH) as conn:
        events = pending_events(conn, limit=LIMIT)
        if not events:
            print("No pending events.")
            return
        for event in events:
            outbox_id = event.pop("_outbox_id")
            event.pop("_attempt_count", None)
            results = await deliver_event(event)
            if not results:
                mark_failed(conn, outbox_id, "No MEMBRA_EVENT_SINKS configured")
                print(f"failed {event['event_id']}: no sinks")
                continue
            if all(result.get("ok") for result in results):
                mark_delivered(conn, outbox_id)
                print(f"delivered {event['event_id']} -> {len(results)} sink(s)")
            else:
                mark_failed(conn, outbox_id, str(results))
                print(f"failed {event['event_id']}: {results}")


if __name__ == "__main__":
    asyncio.run(main())
