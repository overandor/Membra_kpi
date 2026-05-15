"""Deterministic photo-to-SKU assetification engine.

This module is intentionally useful without external vision APIs. It converts
room type, monetization goal, user notes, filename, and image metadata into
normalized MEMBRA inventory objects.
"""
from __future__ import annotations

import datetime as dt
import re
import uuid
from dataclasses import dataclass, asdict
from typing import Any

from .kpi_engine import generate_item_kpis
from .pricing import price_band_for


@dataclass(frozen=True)
class AssetTemplate:
    category: str
    detected_name: str
    asset_type: str
    visual_evidence: str
    monetization_type: str
    listing_type: str
    description: str
    confidence: float
    proof_required: list[str]
    risk_flags: list[str]
    recommended_action: str


@dataclass(frozen=True)
class InventoryItem:
    sku: str
    source_photo_id: str
    inventory_item_id: str
    detected_name: str
    asset_type: str
    visual_evidence: str
    monetization_type: str
    listing_type: str
    description: str
    suggested_price_low: float
    suggested_price_high: float
    pricing_unit: str
    confidence: float
    kpi_score: int
    proof_required: list[str]
    risk_flags: list[str]
    recommended_action: str
    status: str = "draft"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def short_id() -> str:
    return uuid.uuid4().hex[:4].upper()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def make_sku(category: str) -> str:
    return f"MEMBRA-{category.upper()}-{short_id()}"


def normalize_context(*parts: str | None) -> str:
    return " ".join([p or "" for p in parts]).lower()


TEMPLATES: dict[str, list[AssetTemplate]] = {
    "clutter": [
        AssetTemplate("RESALE", "Clothing resale bundle", "resale_bundle", "visible clothing pile, bag, closet, or soft goods", "sell/bundle", "clothing resale bundle", "Owner-approved bundle of clothing or soft goods that may be sorted, photographed, and prepared for resale or donation routing.", 0.74, ["clear item photo", "owner confirmation", "condition notes"], ["quality review recommended"], "Sort into keep/sell/donate groups and photograph each bundle."),
        AssetTemplate("STORAGE", "Closet shelf storage", "storage_space", "visible shelf, closet, bin, or storage area", "store/rent", "closet or shelf storage", "Small owner-controlled storage slot for light household goods, subject to lease and safety rules.", 0.82, ["clear shelf photo", "dimensions", "access rules", "owner confirmation"], ["liability review recommended"], "Measure shelf dimensions and create a private draft listing."),
        AssetTemplate("RELAY", "Package holding point", "handoff_point", "visible entryway, bags, boxes, or pickup area", "relay", "local handoff point", "Potential local package holding or pickup point for approved relay jobs.", 0.68, ["handoff rules", "secure placement photo", "owner availability"], ["security review recommended"], "Define package size limits, hours, and proof steps."),
        AssetTemplate("WEAR", "Wearable media candidate", "wearable_media", "visible hoodie, shirt, backpack, hat, or bag", "advertise", "wearable ad space", "Wearable surface candidate for QR/NFC campaign media after owner approval and kit production.", 0.66, ["wearable photo", "surface measurement", "campaign consent"], ["brand safety review"], "Identify clean, visible surface area for QR/NFC creative."),
        AssetTemplate("TASK", "Sorting or decluttering task", "local_task", "visible clutter, boxes, bags, or mixed household items", "task", "sorting task listing", "Owner-approved task listing for sorting, staging, or decluttering support.", 0.62, ["task scope", "before photo", "owner confirmation"], ["privacy review recommended"], "Create a bounded task scope and exclude private items."),
    ],
    "living": [
        AssetTemplate("SEAT", "Couch seat and Wi-Fi workspace", "seating_or_workspace", "visible couch, chair, table, or living room seating", "rent/access", "couch seat rental", "Short-duration owner-approved seating or workspace access, subject to house rules and local regulations.", 0.72, ["space photo", "house rules", "time windows", "owner confirmation"], ["lease/building rule review required"], "Confirm permissions and define access hours."),
        AssetTemplate("WINDOW", "Window ad surface", "window_ad_surface", "visible window, glass door, or street-facing light source", "advertise", "window ad surface", "Street-facing or visible interior window candidate for QR/NFC physical media placement.", 0.78, ["window photo", "visibility angle", "building rules", "owner confirmation"], ["building/HOA review required"], "Photograph window from inside and outside if permitted."),
        AssetTemplate("WALLAD", "Wall QR poster surface", "wall_qr_surface", "visible wall, poster area, door, or smooth vertical surface", "advertise", "wall QR surface", "Owner-approved wall/poster surface for local QR campaign placement.", 0.70, ["wall photo", "surface dimensions", "creative approval"], ["damage/liability review"], "Measure the surface and define removable media rules."),
        AssetTemplate("STORAGE", "Shelf storage slot", "storage_space", "visible shelf, cabinet, closet, or empty storage gap", "store/rent", "shelf storage slot", "Small storage slot for owner-approved local storage use.", 0.69, ["dimensions", "weight limit", "access rules"], ["liability review recommended"], "Measure dimensions and specify prohibited items."),
        AssetTemplate("RELAY", "Local pickup point", "handoff_point", "visible entrance, lobby, shelf, or staging zone", "relay", "local handoff pickup point", "A local handoff point for approved pickup/dropoff activity.", 0.66, ["pickup proof", "handoff rules", "availability"], ["security review recommended"], "Define handoff windows and proof requirements."),
    ],
    "car": [
        AssetTemplate("CARAD", "Rear window ad space", "car_ad_space", "visible rear window or vehicle glass", "advertise", "rear window ad space", "Vehicle rear-window campaign surface for QR/NFC physical media.", 0.84, ["vehicle photo", "owner confirmation", "route/mileage estimate", "creative approval"], ["local vehicle advertising rules review"], "Capture rear-window photo and define driving region."),
        AssetTemplate("CARAD", "Side window QR decal", "car_ad_space", "visible side window or vehicle side surface", "advertise", "side window QR decal", "Side-window or side-panel QR campaign placement candidate.", 0.78, ["side photo", "decal size", "owner confirmation"], ["visibility and safety review"], "Choose a non-obstructive placement area."),
        AssetTemplate("STORAGE", "Trunk storage capacity", "storage_space", "visible trunk, cargo space, or vehicle storage", "store/rent", "trunk storage capacity", "Short-term storage or courier staging candidate inside owner-controlled vehicle space.", 0.64, ["trunk photo", "size limit", "item restrictions"], ["insurance/liability review required"], "Define prohibited goods and access terms."),
        AssetTemplate("RELAY", "Local delivery handoff route", "handoff_point", "vehicle available for local movement", "relay", "local delivery handoff route", "Owner-approved local route capacity for relay or campaign kit delivery.", 0.69, ["route scope", "availability", "proof steps"], ["delivery compliance review"], "Define radius, time windows, and proof events."),
        AssetTemplate("CAMPAIGN", "Mobile campaign route", "campaign_route", "vehicle route or recurring movement pattern", "advertise", "mobile campaign route", "Route-based mobile media campaign opportunity.", 0.66, ["route estimate", "vehicle photo", "campaign approval"], ["performance estimate not guaranteed"], "Log typical routes and mileage before matching campaigns."),
    ],
    "tools": [
        AssetTemplate("TOOL", "Tool rental", "local_tool", "visible drill, vacuum, ladder, tool, or equipment", "lend/rent", "tool rental", "Owner-controlled tool that may be lent or rented locally after condition and safety review.", 0.80, ["tool photo", "condition notes", "owner confirmation"], ["damage/security deposit recommended"], "Photograph tool model and condition."),
        AssetTemplate("TOOL", "Local borrowing kit", "local_tool", "visible household equipment", "lend/rent", "local borrowing", "Bundle of tools or equipment for short-duration local borrowing.", 0.72, ["bundle photo", "included items", "return rules"], ["loss/damage review"], "List included items and replacement value."),
        AssetTemplate("TOOL", "Repair kit access", "local_tool", "visible repair tools or maintenance kit", "rent/access", "repair kit access", "Owner-approved repair kit access for local users.", 0.68, ["kit photo", "safe-use rules", "return proof"], ["safety review required"], "Add safe-use instructions and proof requirements."),
        AssetTemplate("RELAY", "Tool pickup/dropoff listing", "handoff_point", "pickup/dropoff needed for tool access", "relay", "pickup/dropoff listing", "Local relay wrapper for tool pickup and return.", 0.64, ["handoff proof", "time windows", "condition photos"], ["dispute review recommended"], "Define pickup, return, and condition proof events."),
        AssetTemplate("TASK", "Task assistance listing", "local_task", "tools imply possible household task assistance", "task", "task assistance listing", "Owner-approved local task opportunity tied to tools or equipment.", 0.58, ["task scope", "before/after proof", "owner approval"], ["labor rules review"], "Define a bounded task and exclude regulated work."),
    ],
    "office": [
        AssetTemplate("WORK", "Workspace access", "workspace", "visible desk, chair, monitor, lamp, or office setup", "rent/access", "workspace access", "Owner-approved desk or workspace access opportunity.", 0.80, ["workspace photo", "Wi-Fi rules", "time windows", "owner confirmation"], ["lease/building review required"], "Confirm permission and define booking windows."),
        AssetTemplate("WORK", "Content creator setup", "workspace", "visible desk, lighting, backdrop, monitor, or camera area", "rent/access", "creator station access", "Creator station candidate for short-duration content production.", 0.72, ["setup photo", "equipment list", "house rules"], ["privacy review recommended"], "List equipment and allowed content categories."),
        AssetTemplate("TOOL", "Ring light rental", "local_tool", "visible ring light, lamp, tripod, or creator accessory", "lend/rent", "ring light rental", "Creator accessory rental candidate.", 0.66, ["equipment photo", "condition notes", "return proof"], ["damage review recommended"], "Photograph condition and accessories."),
        AssetTemplate("WORK", "Remote work station", "workspace", "visible desk or office setup suitable for remote work", "rent/access", "remote work station", "Short-use remote work station listing draft.", 0.70, ["desk photo", "noise rules", "availability"], ["local permission review"], "Define quiet hours and occupancy rules."),
        AssetTemplate("TOOL", "Creator kit rental", "local_tool", "visible creator tools or office accessories", "lend/rent", "creator kit rental", "Bundle of creator tools available for owner-approved rental.", 0.64, ["kit inventory", "condition photos", "return rules"], ["loss/damage review"], "Create an itemized kit checklist."),
    ],
}


def choose_scenario(text: str) -> str:
    text = text.lower()
    if any(word in text for word in ["car", "vehicle", "truck", "tesla", "rear window", "side window", "trunk"]):
        return "car"
    if any(word in text for word in ["tool", "drill", "vacuum", "ladder", "repair", "equipment"]):
        return "tools"
    if any(word in text for word in ["desk", "office", "monitor", "lamp", "workspace", "creator", "ring light"]):
        return "office"
    if any(word in text for word in ["closet", "clutter", "clothing", "clothes", "bags", "boxes", "bin", "storage"]):
        return "clutter"
    return "living"


def scenario_summary(scenario: str, *, room_type: str | None, monetization_goal: str | None) -> str:
    label = {
        "car": "Vehicle / mobile media inventory",
        "tools": "Household tools and local utility inventory",
        "office": "Workspace and creator-station inventory",
        "clutter": "Closet, storage, resale, and sorting inventory",
        "living": "Apartment living-space inventory",
    }.get(scenario, "Apartment inventory")
    return f"{label} detected from context. Goal: {monetization_goal or 'general assetification'}. Room/type: {room_type or 'unspecified'}. AI may draft; owner approval is required before visibility."


def assetify_from_context(
    *,
    photo_id: str,
    owner_id: str | None = None,
    room_type: str | None = None,
    monetization_goal: str | None = None,
    user_notes: str | None = None,
    location_hint: str | None = None,
    filename: str | None = None,
    width: int | None = None,
    height: int | None = None,
) -> dict[str, Any]:
    text = normalize_context(room_type, monetization_goal, user_notes, location_hint, filename)
    scenario = choose_scenario(text)
    templates = TEMPLATES[scenario]
    detected: list[dict[str, Any]] = []
    all_kpis: list[dict[str, Any]] = []
    for template in templates:
        band = price_band_for(template.category, location_hint=location_hint, confidence=template.confidence)
        kpis = generate_item_kpis(
            category=template.category,
            detected_name=template.detected_name,
            confidence=template.confidence,
            price_low=band.low,
            price_high=band.high,
            pricing_unit=band.unit,
            proof_required=template.proof_required,
            risk_flags=template.risk_flags,
            location_hint=location_hint,
        )
        kpi_score = next((card.score for card in kpis if card.title == "SKU readiness score"), 70)
        item = InventoryItem(
            sku=make_sku(template.category),
            source_photo_id=photo_id,
            inventory_item_id=new_id("inv"),
            detected_name=template.detected_name,
            asset_type=template.asset_type,
            visual_evidence=template.visual_evidence,
            monetization_type=template.monetization_type,
            listing_type=template.listing_type,
            description=template.description,
            suggested_price_low=band.low,
            suggested_price_high=band.high,
            pricing_unit=band.unit,
            confidence=template.confidence,
            kpi_score=kpi_score,
            proof_required=template.proof_required,
            risk_flags=template.risk_flags,
            recommended_action=template.recommended_action,
        )
        detected.append(item.to_dict())
        all_kpis.extend([card.to_dict() | {"inventory_item_id": item.inventory_item_id, "source_photo_id": photo_id} for card in kpis])
    return {
        "success": True,
        "photo_id": photo_id,
        "owner_id": owner_id or "owner_demo",
        "scenario": scenario,
        "room_summary": scenario_summary(scenario, room_type=room_type, monetization_goal=monetization_goal),
        "image_metadata": {"filename": filename, "width": width, "height": height},
        "inventory_items_created": len(detected),
        "sku_records_created": len(detected),
        "listing_drafts_created": len(detected),
        "kpi_cards_created": len(all_kpis),
        "proofbook_entries_created": 4,
        "detected_inventory": detected,
        "kpi_cards": all_kpis,
    }
