from membra_kpi.assetification import assetify_from_context
from membra_kpi.marketplace import confirm_visibility, create_listing_draft, request_visibility, VISIBLE_INTERNAL_MARKETPLACE
from membra_kpi.proofbook import create_proof_entry


def test_fallback_assetification_creates_required_records():
    result = assetify_from_context(
        photo_id="photo_test_001",
        room_type="living room",
        monetization_goal="window ads and storage",
        user_notes="first-floor window, couch, shelf, entryway",
        location_hint="downtown street-facing",
        filename="living-room-window.jpg",
        width=1200,
        height=800,
    )
    assert result["success"] is True
    assert result["inventory_items_created"] >= 5
    assert result["sku_records_created"] >= 5
    assert result["listing_drafts_created"] >= 5
    assert result["kpi_cards_created"] >= 10
    assert result["proofbook_entries_created"] >= 4
    assert all(item["sku"].startswith("MEMBRA-") for item in result["detected_inventory"])


def test_marketplace_visibility_lifecycle():
    item = assetify_from_context(photo_id="photo_test_002", user_notes="car rear window")['detected_inventory'][0]
    draft = create_listing_draft(item).to_dict()
    assert draft["status"] == "draft"
    pending = request_visibility(draft)
    assert pending["status"] == "pending_owner_confirmation"
    confirmed, public = confirm_visibility(pending)
    assert confirmed["status"] == VISIBLE_INTERNAL_MARKETPLACE
    assert public.visibility_status == VISIBLE_INTERNAL_MARKETPLACE


def test_proofbook_hash_is_created():
    entry = create_proof_entry("photo", "photo_test_003", "photo_analyzed", {"filename": "test.jpg"})
    assert entry.proof_id.startswith("proof_")
    assert len(entry.proof_hash) == 64
