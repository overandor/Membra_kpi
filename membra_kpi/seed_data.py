"""Seed data and demo fixtures for MEMBRA KPI."""
from __future__ import annotations

from typing import Any

DEMO_PHOTOS = [
    {
        "photo_id": "photo_demo_living_001",
        "owner_id": "owner_apartment_demo",
        "filename": "living-room-window-shelf.jpg",
        "room_type": "living room",
        "monetization_goal": "apartment space, window ads, storage, local handoff",
        "user_notes": "Couch, street-facing first-floor window, shelf, and small package handoff area.",
        "location_hint": "downtown street-facing apartment",
    },
    {
        "photo_id": "photo_demo_car_001",
        "owner_id": "owner_vehicle_demo",
        "filename": "vehicle-rear-window.jpg",
        "room_type": "car",
        "monetization_goal": "car ad space and mobile campaign route",
        "user_notes": "Rear window and side window available for removable QR decals.",
        "location_hint": "urban commute route",
    },
    {
        "photo_id": "photo_demo_closet_001",
        "owner_id": "owner_closet_demo",
        "filename": "closet-clothing-boxes.jpg",
        "room_type": "closet",
        "monetization_goal": "storage, resale, sorting task, wearable ad inventory",
        "user_notes": "Closet with clothing, bins, bags, and open shelf space.",
        "location_hint": "local residential",
    },
]

DEMO_OWNER_PROMPTS = [
    "I have a first-floor window facing a busy street. Can MEMBRA turn it into ad space?",
    "Can my car rear window become a QR ad placement?",
    "I uploaded a closet photo. What can be turned into inventory?",
    "Which draft listings are safe to make visible after owner approval?",
]

DEMO_POLICY_BANNERS = {
    "earnings": "AI-generated estimates are not guaranteed. Eligibility depends on permission, proof, review, local rules, and external settlement rails.",
    "proof": "Do not upload private keys, seed phrases, raw financial credentials, or unconsented personal material.",
    "visibility": "AI may draft inventory. Owner confirmation is required before marketplace visibility.",
    "settlement": "MEMBRA records payout eligibility only. External rails settle money.",
}


def demo_bundle() -> dict[str, Any]:
    return {
        "bundle_id": "membra_kpi_assetification_demo_001",
        "photos": DEMO_PHOTOS,
        "owner_prompts": DEMO_OWNER_PROMPTS,
        "policy_banners": DEMO_POLICY_BANNERS,
        "acceptance_flow": [
            "upload_photo",
            "map_inventory",
            "assign_skus",
            "create_listing_drafts",
            "create_kpi_cards",
            "write_proofbook_entries",
            "request_visibility",
            "confirm_visibility",
            "show_marketplace_listing",
        ],
    }
