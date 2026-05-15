"""Image-driven SKU identification for MEMBRA listings.

This module turns an uploaded picture plus lightweight context into concrete,
marketplace-ready SKU candidates. It is intentionally deterministic and auditable:
no fake computer-vision claims, no hidden external API dependency, and no mock rows.

When a real CV model is added later, its labels can be passed as `vision_labels`
and this engine will merge them with filename/context/image-metadata signals.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ImageSignals:
    filename: str
    width: int
    height: int
    aspect_ratio: float
    orientation: str
    megapixels: float
    context_text: str
    tokens: list[str]
    vision_labels: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SkuIdentification:
    sku: str
    sku_family: str
    title: str
    asset_type: str
    listing_type: str
    marketplace_category: str
    confidence: float
    confidence_grade: str
    evidence: list[str]
    proof_required: list[str]
    risk_flags: list[str]
    suggested_listing_title: str
    suggested_listing_description: str
    suggested_tags: list[str]
    requested_owner_fields: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SkuRule:
    sku_family: str
    title: str
    asset_type: str
    listing_type: str
    marketplace_category: str
    token_weights: dict[str, float]
    base_confidence: float
    proof_required: list[str]
    risk_flags: list[str]
    owner_fields: list[str]
    tags: list[str]


SKU_RULES: list[SkuRule] = [
    SkuRule(
        sku_family="WINDOW",
        title="Window ad surface",
        asset_type="window_ad_surface",
        listing_type="window QR/NFC ad surface",
        marketplace_category="local_media_surface",
        token_weights={"window": 0.34, "glass": 0.24, "street": 0.19, "storefront": 0.24, "first": 0.12, "floor": 0.12, "view": 0.10, "poster": 0.08, "qr": 0.08},
        base_confidence=0.50,
        proof_required=["inside window photo", "outside visibility angle", "surface dimensions", "owner or lease permission", "removable media rules"],
        risk_flags=["building_rules_review", "local_advertising_rules_review", "visibility_not_guaranteed"],
        owner_fields=["window_width_in", "window_height_in", "street_visibility", "allowed_media_type", "available_dates"],
        tags=["window", "qr", "local ads", "street visibility"],
    ),
    SkuRule(
        sku_family="CARAD",
        title="Vehicle ad surface",
        asset_type="car_ad_space",
        listing_type="mobile QR/NFC ad surface",
        marketplace_category="mobile_media_surface",
        token_weights={"car": 0.34, "vehicle": 0.34, "truck": 0.30, "rear": 0.18, "side": 0.12, "window": 0.12, "bumper": 0.14, "commute": 0.14, "route": 0.16, "mileage": 0.12},
        base_confidence=0.50,
        proof_required=["vehicle photo", "surface placement photo", "owner confirmation", "route or mileage estimate", "non-obstruction confirmation"],
        risk_flags=["vehicle_safety_review", "local_vehicle_ad_rules_review", "campaign_performance_not_guaranteed"],
        owner_fields=["vehicle_make_model", "weekly_mileage", "primary_routes", "surface_width_in", "surface_height_in"],
        tags=["vehicle", "mobile ads", "qr", "commute"],
    ),
    SkuRule(
        sku_family="STORAGE",
        title="Storage space",
        asset_type="storage_space",
        listing_type="owner-controlled storage slot",
        marketplace_category="storage_access",
        token_weights={"closet": 0.32, "storage": 0.34, "shelf": 0.24, "garage": 0.25, "basement": 0.22, "bin": 0.15, "box": 0.10, "empty": 0.08, "space": 0.08},
        base_confidence=0.52,
        proof_required=["clear storage photo", "dimensions", "weight limit", "access rules", "prohibited items list", "owner confirmation"],
        risk_flags=["liability_review", "lease_or_building_rules_review", "prohibited_goods_required"],
        owner_fields=["width_in", "height_in", "depth_in", "max_weight_lb", "access_hours", "prohibited_items"],
        tags=["storage", "shelf", "closet", "local access"],
    ),
    SkuRule(
        sku_family="WORK",
        title="Workspace access",
        asset_type="workspace",
        listing_type="desk or creator workspace access",
        marketplace_category="workspace_access",
        token_weights={"desk": 0.34, "office": 0.30, "workspace": 0.34, "monitor": 0.18, "chair": 0.14, "wifi": 0.12, "lamp": 0.10, "studio": 0.16, "creator": 0.16},
        base_confidence=0.51,
        proof_required=["workspace photo", "availability schedule", "house rules", "wifi terms", "owner confirmation"],
        risk_flags=["building_rules_review", "privacy_review", "access_control_required"],
        owner_fields=["available_hours", "wifi_available", "max_occupancy", "noise_rules", "equipment_included"],
        tags=["workspace", "desk", "creator", "wifi"],
    ),
    SkuRule(
        sku_family="TOOL",
        title="Tool rental",
        asset_type="local_tool",
        listing_type="local tool rental",
        marketplace_category="tool_access",
        token_weights={"tool": 0.32, "drill": 0.35, "vacuum": 0.28, "ladder": 0.34, "saw": 0.30, "camera": 0.20, "tripod": 0.20, "ring": 0.10, "light": 0.10, "equipment": 0.22},
        base_confidence=0.50,
        proof_required=["tool photo", "model or description", "condition notes", "replacement value", "return proof rules", "owner confirmation"],
        risk_flags=["damage_deposit_recommended", "safe_use_required", "regulated_work_excluded"],
        owner_fields=["tool_brand_model", "condition", "replacement_value_usd", "pickup_rules", "return_rules"],
        tags=["tools", "rental", "local", "equipment"],
    ),
    SkuRule(
        sku_family="WEAR",
        title="Wearable ad surface",
        asset_type="wearable_media",
        listing_type="wearable QR/NFC campaign surface",
        marketplace_category="wearable_media_surface",
        token_weights={"shirt": 0.28, "hoodie": 0.32, "jacket": 0.24, "hat": 0.24, "backpack": 0.28, "bag": 0.16, "wear": 0.20, "clothing": 0.18, "qr": 0.12},
        base_confidence=0.49,
        proof_required=["wearable photo", "surface dimensions", "clean condition confirmation", "campaign consent", "owner confirmation"],
        risk_flags=["brand_safety_review", "campaign_performance_not_guaranteed", "creative_approval_required"],
        owner_fields=["wearable_type", "surface_width_in", "surface_height_in", "wear_frequency", "campaign_categories_allowed"],
        tags=["wearable", "qr", "campaign", "clothing"],
    ),
    SkuRule(
        sku_family="RESALE",
        title="Resale bundle",
        asset_type="resale_bundle",
        listing_type="resale or liquidation bundle",
        marketplace_category="resale_inventory",
        token_weights={"clothes": 0.24, "clothing": 0.24, "shoes": 0.20, "bundle": 0.24, "resale": 0.34, "sell": 0.14, "box": 0.12, "bag": 0.10, "declutter": 0.22},
        base_confidence=0.48,
        proof_required=["bundle photo", "item count", "condition notes", "owner confirmation", "excluded private items"],
        risk_flags=["condition_review", "counterfeit_screening_if_branded", "privacy_review"],
        owner_fields=["item_count", "condition_grade", "brand_notes", "pickup_or_shipping", "minimum_price_usd"],
        tags=["resale", "bundle", "declutter", "local"],
    ),
    SkuRule(
        sku_family="RELAY",
        title="Local handoff point",
        asset_type="handoff_point",
        listing_type="local pickup and handoff capacity",
        marketplace_category="local_relay",
        token_weights={"entry": 0.18, "lobby": 0.25, "pickup": 0.30, "handoff": 0.34, "delivery": 0.24, "package": 0.28, "door": 0.10, "shelf": 0.10, "route": 0.14},
        base_confidence=0.46,
        proof_required=["handoff area photo", "availability schedule", "package size limits", "proof-of-pickup rules", "owner confirmation"],
        risk_flags=["security_review", "liability_review", "restricted_items_required"],
        owner_fields=["available_hours", "max_package_size", "handoff_method", "restricted_items", "proof_required"],
        tags=["handoff", "pickup", "local", "delivery"],
    ),
]


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize(*parts: str | None) -> list[str]:
    joined = " ".join(p or "" for p in parts).lower()
    return TOKEN_PATTERN.findall(joined)


def extract_image_signals(
    *,
    filename: str,
    width: int,
    height: int,
    room_type: str = "",
    monetization_goal: str = "",
    user_notes: str = "",
    location_hint: str = "",
    requested_asset_type: str = "",
    vision_labels: list[str] | None = None,
) -> ImageSignals:
    labels = [x.strip().lower() for x in (vision_labels or []) if x and x.strip()]
    context_text = " ".join(
        part for part in [filename, room_type, monetization_goal, user_notes, location_hint, requested_asset_type, " ".join(labels)] if part
    ).lower()
    tokens = tokenize(context_text, Path(filename).stem.replace("_", " ").replace("-", " "))
    aspect_ratio = round(width / height, 4) if height else 0.0
    if width and height:
        orientation = "landscape" if width > height else "portrait" if height > width else "square"
    else:
        orientation = "unknown"
    megapixels = round((width * height) / 1_000_000, 3) if width and height else 0.0
    return ImageSignals(
        filename=filename,
        width=width,
        height=height,
        aspect_ratio=aspect_ratio,
        orientation=orientation,
        megapixels=megapixels,
        context_text=context_text,
        tokens=tokens,
        vision_labels=labels,
    )


def stable_suffix(*parts: Any, length: int = 4) -> str:
    raw = "|".join(str(p) for p in parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:length].upper()


def confidence_grade(confidence: float) -> str:
    if confidence >= 0.82:
        return "A"
    if confidence >= 0.70:
        return "B"
    if confidence >= 0.58:
        return "C"
    if confidence >= 0.45:
        return "D"
    return "F"


def score_rule(rule: SkuRule, signals: ImageSignals) -> tuple[float, list[str]]:
    token_set = set(signals.tokens)
    evidence: list[str] = []
    score = rule.base_confidence
    for token, weight in rule.token_weights.items():
        if token in token_set or token in signals.context_text:
            score += weight
            evidence.append(f"matched:{token}")

    if signals.megapixels >= 1.0:
        score += 0.04
        evidence.append("image_quality:>=1MP")
    if signals.orientation == "portrait" and rule.sku_family in {"WINDOW", "WEAR", "WORK"}:
        score += 0.03
        evidence.append("orientation:portrait")
    if signals.orientation == "landscape" and rule.sku_family in {"CARAD", "STORAGE", "WORK"}:
        score += 0.03
        evidence.append("orientation:landscape")
    if signals.vision_labels:
        score += min(0.08, 0.02 * len(signals.vision_labels))
        evidence.append("vision_labels_supplied")

    return min(round(score, 4), 0.98), evidence


def listing_copy(rule: SkuRule, signals: ImageSignals, confidence: float) -> tuple[str, str]:
    title = f"{rule.title} - MEMBRA {rule.sku_family} candidate"
    detail_bits = []
    if signals.width and signals.height:
        detail_bits.append(f"source image {signals.width}x{signals.height}px")
    if signals.orientation != "unknown":
        detail_bits.append(f"{signals.orientation} orientation")
    detail = "; ".join(detail_bits) or "source image received"
    description = (
        f"Owner-controlled {rule.listing_type} identified from uploaded iPhone/photo context. "
        f"MEMBRA assigned this as a {rule.marketplace_category} candidate with confidence {confidence:.2f}. "
        f"Evidence: {detail}. Owner confirmation, proof requirements, and compliance review are required before external promotion or settlement."
    )
    return title, description


def identify_sku_candidates(
    *,
    filename: str,
    width: int,
    height: int,
    room_type: str = "",
    monetization_goal: str = "",
    user_notes: str = "",
    location_hint: str = "",
    requested_asset_type: str = "",
    vision_labels: list[str] | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    signals = extract_image_signals(
        filename=filename,
        width=width,
        height=height,
        room_type=room_type,
        monetization_goal=monetization_goal,
        user_notes=user_notes,
        location_hint=location_hint,
        requested_asset_type=requested_asset_type,
        vision_labels=vision_labels,
    )

    candidates: list[SkuIdentification] = []
    for rule in SKU_RULES:
        confidence, evidence = score_rule(rule, signals)
        if not evidence and confidence < 0.52:
            continue
        sku = f"MEMBRA-{rule.sku_family}-{stable_suffix(filename, width, height, rule.sku_family)}"
        title, description = listing_copy(rule, signals, confidence)
        candidates.append(
            SkuIdentification(
                sku=sku,
                sku_family=rule.sku_family,
                title=rule.title,
                asset_type=rule.asset_type,
                listing_type=rule.listing_type,
                marketplace_category=rule.marketplace_category,
                confidence=confidence,
                confidence_grade=confidence_grade(confidence),
                evidence=evidence or ["low_context_generic_candidate"],
                proof_required=rule.proof_required,
                risk_flags=rule.risk_flags,
                suggested_listing_title=title,
                suggested_listing_description=description,
                suggested_tags=rule.tags,
                requested_owner_fields=rule.owner_fields,
            )
        )

    candidates.sort(key=lambda x: (x.confidence, x.sku_family), reverse=True)
    if not candidates:
        fallback = SKU_RULES[2]  # storage is the safest generic private-draft candidate
        sku = f"MEMBRA-{fallback.sku_family}-{stable_suffix(filename, width, height, 'fallback')}"
        title, description = listing_copy(fallback, signals, fallback.base_confidence)
        candidates.append(
            SkuIdentification(
                sku=sku,
                sku_family=fallback.sku_family,
                title=fallback.title,
                asset_type=fallback.asset_type,
                listing_type=fallback.listing_type,
                marketplace_category=fallback.marketplace_category,
                confidence=fallback.base_confidence,
                confidence_grade=confidence_grade(fallback.base_confidence),
                evidence=["fallback_private_review_required"],
                proof_required=fallback.proof_required,
                risk_flags=[*fallback.risk_flags, "manual_review_required"],
                suggested_listing_title=title,
                suggested_listing_description=description,
                suggested_tags=fallback.tags,
                requested_owner_fields=fallback.owner_fields,
            )
        )

    return {
        "signals": signals.to_dict(),
        "top_candidate": candidates[0].to_dict(),
        "candidates": [c.to_dict() for c in candidates[: max(1, limit)]],
    }


def sku_to_inventory_item(
    *,
    sku_identification: dict[str, Any],
    photo_id: str,
    inventory_item_id: str,
    price_low: float,
    price_high: float,
    pricing_unit: str,
) -> dict[str, Any]:
    """Convert a SKU identification result into the app's inventory item shape."""
    return {
        "sku": sku_identification["sku"],
        "source_photo_id": photo_id,
        "inventory_item_id": inventory_item_id,
        "detected_name": sku_identification["title"],
        "asset_type": sku_identification["asset_type"],
        "visual_evidence": "; ".join(sku_identification.get("evidence", [])),
        "monetization_type": sku_identification["marketplace_category"],
        "listing_type": sku_identification["listing_type"],
        "description": sku_identification["suggested_listing_description"],
        "suggested_price_low": price_low,
        "suggested_price_high": price_high,
        "pricing_unit": pricing_unit,
        "confidence": sku_identification["confidence"],
        "kpi_score": int(min(98, max(40, math.floor(sku_identification["confidence"] * 100)))),
        "proof_required": sku_identification["proof_required"],
        "risk_flags": sku_identification["risk_flags"],
        "recommended_action": "Collect requested owner fields, verify permissions, then request marketplace visibility.",
        "status": "draft",
    }
