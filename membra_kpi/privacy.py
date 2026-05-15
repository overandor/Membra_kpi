"""Privacy/export/delete helpers for MEMBRA KPI.

The functions here define the data surfaces tied to an owner/account identifier.
They are intentionally explicit so operators can audit what is exported,
anonymized, or removed.
"""
from __future__ import annotations

from dataclasses import dataclass

OWNER_SCOPED_TABLES = {
    "photos": "owner_id",
    "inventory_items": "owner_id",
    "wallet_events": "user_id",
    "payout_eligibility": "user_id",
    "ai_chat_events": "owner_id",
}

INDIRECT_OWNER_TABLES = {
    "listing_drafts": ("inventory_items", "inventory_item_id", "inventory_item_id"),
    "public_listings": ("listing_drafts", "listing_id", "listing_id"),
    "kpi_cards": ("inventory_items", "inventory_item_id", "inventory_item_id"),
}

PRIVACY_REQUEST_STATUSES = {"submitted", "verified", "exported", "completed", "rejected"}


@dataclass(frozen=True)
class PrivacyRequest:
    request_id: str
    owner_id: str
    request_type: str
    status: str
    reason: str
    created_at: str


def validate_privacy_status(status: str) -> str:
    if status not in PRIVACY_REQUEST_STATUSES:
        raise ValueError(f"status must be one of {sorted(PRIVACY_REQUEST_STATUSES)}")
    return status


def owner_export_queries(owner_id: str) -> list[tuple[str, str, tuple[str, ...]]]:
    queries: list[tuple[str, str, tuple[str, ...]]] = []
    for table, owner_col in OWNER_SCOPED_TABLES.items():
        queries.append((table, f"SELECT * FROM {table} WHERE {owner_col}=?", (owner_id,)))
    queries.extend(
        [
            (
                "listing_drafts",
                """
                SELECT d.* FROM listing_drafts d
                JOIN inventory_items i ON i.inventory_item_id=d.inventory_item_id
                WHERE i.owner_id=?
                """,
                (owner_id,),
            ),
            (
                "public_listings",
                """
                SELECT p.* FROM public_listings p
                JOIN listing_drafts d ON d.listing_id=p.listing_id
                JOIN inventory_items i ON i.inventory_item_id=d.inventory_item_id
                WHERE i.owner_id=?
                """,
                (owner_id,),
            ),
            (
                "kpi_cards",
                """
                SELECT k.* FROM kpi_cards k
                JOIN inventory_items i ON i.inventory_item_id=k.inventory_item_id
                WHERE i.owner_id=?
                """,
                (owner_id,),
            ),
            (
                "proofbook_entries",
                """
                SELECT * FROM proofbook_entries
                WHERE metadata_json LIKE ? OR subject_id IN (
                  SELECT inventory_item_id FROM inventory_items WHERE owner_id=?
                  UNION SELECT photo_id FROM photos WHERE owner_id=?
                  UNION SELECT listing_id FROM listing_drafts d JOIN inventory_items i ON i.inventory_item_id=d.inventory_item_id WHERE i.owner_id=?
                )
                """,
                (f"%{owner_id}%", owner_id, owner_id, owner_id),
            ),
        ]
    )
    return queries


def anonymize_owner_label(owner_id: str) -> str:
    return f"deleted_owner_{abs(hash(owner_id)) % 10_000_000}"
