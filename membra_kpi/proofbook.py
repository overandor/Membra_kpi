"""ProofBook helpers for MEMBRA KPI.

ProofBook records are SHA-256 hashes over canonical JSON payloads. They are
proof/audit records only; they do not authorize external visibility or payments.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Any


PROOF_EVENTS = {
    "photo_analyzed",
    "picture_inventory_mapped",
    "sku_map_created",
    "inventory_items_created",
    "listing_drafts_created",
    "kpis_generated",
    "visibility_requested",
    "visibility_confirmed",
    "qr_artifact_created",
    "scan_recorded",
    "payout_eligibility_created",
}


@dataclass(frozen=True)
class ProofBookEntry:
    proof_id: str
    subject_type: str
    subject_id: str
    event_type: str
    proof_hash: str
    metadata: dict[str, Any]
    created_at: str

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["metadata_json"] = json.dumps(row.pop("metadata"), ensure_ascii=False, sort_keys=True, default=str)
        return row


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_payload(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def make_proof_id(subject_type: str, subject_id: str, event_type: str) -> str:
    digest = sha256_payload({"subject_type": subject_type, "subject_id": subject_id, "event_type": event_type, "salt": utc_now()})
    return f"proof_{digest[:12]}"


def create_proof_entry(subject_type: str, subject_id: str, event_type: str, metadata: dict[str, Any] | None = None) -> ProofBookEntry:
    if event_type not in PROOF_EVENTS:
        raise ValueError(f"Unsupported ProofBook event_type: {event_type}")
    metadata = metadata or {}
    created_at = utc_now()
    payload = {
        "subject_type": subject_type,
        "subject_id": subject_id,
        "event_type": event_type,
        "metadata": metadata,
        "created_at": created_at,
    }
    return ProofBookEntry(
        proof_id=make_proof_id(subject_type, subject_id, event_type),
        subject_type=subject_type,
        subject_id=subject_id,
        event_type=event_type,
        proof_hash=sha256_payload(payload),
        metadata=metadata,
        created_at=created_at,
    )


def create_batch_entries(subject_type: str, subject_id: str, event_types: list[str], base_metadata: dict[str, Any] | None = None) -> list[ProofBookEntry]:
    return [create_proof_entry(subject_type, subject_id, event_type, base_metadata or {}) for event_type in event_types]
