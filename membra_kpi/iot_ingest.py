from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from .deep_backend import BackendContext, append_chain_event, canonical_json, new_id, utc_now


ALLOWED_EVENT_TYPES = {
    "qr_scan",
    "nfc_tap",
    "beacon_seen",
    "device_heartbeat",
    "proof_capture",
    "location_ping",
}



def token_configured() -> bool:
    return bool(os.getenv("MEMBRA_IOT_INGEST_TOKEN"))



def verify_ingest_token(token: str | None) -> bool:
    expected = os.getenv("MEMBRA_IOT_INGEST_TOKEN", "")
    if not expected:
        return False
    return bool(token) and token == expected



def normalize_iot_payload(payload: dict[str, Any]) -> dict[str, Any]:
    event_type = str(payload.get("event_type", "unknown")).strip().lower()
    if event_type not in ALLOWED_EVENT_TYPES:
        raise ValueError(f"unsupported IoT event type: {event_type}")

    normalized = {
        "event_id": payload.get("event_id") or new_id("iot"),
        "device_id": str(payload.get("device_id", "unknown-device")),
        "subject_type": str(payload.get("subject_type", "listing")),
        "subject_id": str(payload.get("subject_id", "unknown-subject")),
        "event_type": event_type,
        "latitude": payload.get("latitude"),
        "longitude": payload.get("longitude"),
        "signal_strength": payload.get("signal_strength"),
        "metadata": payload.get("metadata", {}),
        "created_at": payload.get("created_at") or utc_now(),
    }

    normalized["payload_hash"] = hashlib.sha256(
        canonical_json(normalized).encode("utf-8")
    ).hexdigest()

    return normalized



def ingest_iot_event(conn, context: BackendContext, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_iot_payload(payload)

    append_chain_event(
        conn,
        context,
        normalized["subject_type"],
        normalized["subject_id"],
        f"iot.{normalized['event_type']}",
        normalized,
    )

    return {
        "success": True,
        "event": normalized,
    }
