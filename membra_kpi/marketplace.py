"""Marketplace lifecycle helpers for MEMBRA KPI.

Drafts remain private until owner visibility is requested and confirmed.
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, asdict
from typing import Any

DRAFT = "draft"
PENDING_OWNER_CONFIRMATION = "pending_owner_confirmation"
VISIBLE_INTERNAL_MARKETPLACE = "visible_internal_marketplace"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass(frozen=True)
class ListingDraft:
    listing_id: str
    inventory_item_id: str
    sku: str
    title: str
    description: str
    listing_type: str
    suggested_price_low: float
    suggested_price_high: float
    pricing_unit: str
    status: str = DRAFT
    owner_visibility_requested_at: str | None = None
    owner_confirmed_at: str | None = None
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if not data["created_at"]:
            data["created_at"] = utc_now()
        return data


@dataclass(frozen=True)
class PublicListing:
    public_listing_id: str
    listing_id: str
    sku: str
    title: str
    description: str
    price_low: float
    price_high: float
    pricing_unit: str
    visibility_status: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def create_listing_draft(item: dict[str, Any]) -> ListingDraft:
    return ListingDraft(
        listing_id=new_id("listing"),
        inventory_item_id=item["inventory_item_id"],
        sku=item["sku"],
        title=item["detected_name"],
        description=item.get("description", ""),
        listing_type=item.get("listing_type", "asset listing"),
        suggested_price_low=float(item.get("suggested_price_low", 0)),
        suggested_price_high=float(item.get("suggested_price_high", 0)),
        pricing_unit=item.get("pricing_unit", "monthly"),
        created_at=utc_now(),
    )


def request_visibility(draft: dict[str, Any]) -> dict[str, Any]:
    if draft.get("status") not in {DRAFT, PENDING_OWNER_CONFIRMATION}:
        raise ValueError("Only draft listings can request visibility")
    updated = dict(draft)
    updated["status"] = PENDING_OWNER_CONFIRMATION
    updated["owner_visibility_requested_at"] = utc_now()
    return updated


def confirm_visibility(draft: dict[str, Any]) -> tuple[dict[str, Any], PublicListing]:
    if draft.get("status") != PENDING_OWNER_CONFIRMATION:
        raise ValueError("Listing must be pending_owner_confirmation before public visibility")
    updated = dict(draft)
    updated["status"] = VISIBLE_INTERNAL_MARKETPLACE
    updated["owner_confirmed_at"] = utc_now()
    public = PublicListing(
        public_listing_id=new_id("public"),
        listing_id=updated["listing_id"],
        sku=updated["sku"],
        title=updated["title"],
        description=updated.get("description", ""),
        price_low=float(updated.get("suggested_price_low", 0)),
        price_high=float(updated.get("suggested_price_high", 0)),
        pricing_unit=updated.get("pricing_unit", "monthly"),
        visibility_status=VISIBLE_INTERNAL_MARKETPLACE,
        created_at=utc_now(),
    )
    return updated, public


def is_public_visible(row: dict[str, Any]) -> bool:
    return row.get("visibility_status") == VISIBLE_INTERNAL_MARKETPLACE or row.get("status") == VISIBLE_INTERNAL_MARKETPLACE
