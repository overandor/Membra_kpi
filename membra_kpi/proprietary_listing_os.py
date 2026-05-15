"""MEMBRA Proprietary Listing Operating System.

This module is intentionally product-specific and opinionated. It converts MEMBRA's
image/SKU/proof signals into a proprietary listing packet that can be used for:

- internal marketplace publication
- operator review
- asset appraisal
- owner onboarding
- QR/NFC campaign preparation
- buyer/investor diligence
- listing packet export

Design principles:

1. Owner-first control. AI and rules may draft; owners must approve visibility.
2. Proof before promotion. A listing can be valuable only if its proof package is measurable.
3. Non-custodial economics. MEMBRA records eligibility and external settlement intent only.
4. Traceable transformation. Every listing should explain how photo evidence became SKU inventory.
5. Proprietary taxonomy. MEMBRA SKU classes encode commercial use, proof burden, risk, and operator action.

This is not a generic CRUD helper. It is the MEMBRA-specific layer that turns a
photo-derived inventory candidate into a marketplace-grade commercial object.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class MembraAssetClass(str, Enum):
    LOCAL_MEDIA_SURFACE = "local_media_surface"
    MOBILE_MEDIA_SURFACE = "mobile_media_surface"
    STORAGE_ACCESS = "storage_access"
    WORKSPACE_ACCESS = "workspace_access"
    TOOL_ACCESS = "tool_access"
    WEARABLE_MEDIA_SURFACE = "wearable_media_surface"
    RESALE_INVENTORY = "resale_inventory"
    LOCAL_RELAY = "local_relay"
    SERVICE_TASK = "service_task"
    UNKNOWN = "unknown"


class MembraRiskTier(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    ORANGE = "orange"
    RED = "red"
    BLOCKED = "blocked"


class MembraReviewAction(str, Enum):
    AUTO_PRIVATE_DRAFT = "auto_private_draft"
    OWNER_FIELDS_REQUIRED = "owner_fields_required"
    OPERATOR_REVIEW_REQUIRED = "operator_review_required"
    PROOF_RETAKE_REQUIRED = "proof_retake_required"
    COMPLIANCE_REVIEW_REQUIRED = "compliance_review_required"
    BLOCK_PUBLICATION = "block_publication"


@dataclass(frozen=True)
class ProprietaryScoreBand:
    label: str
    min_score: int
    max_score: int
    interpretation: str
    operator_action: MembraReviewAction


@dataclass(frozen=True)
class MembraCommercialProfile:
    asset_class: MembraAssetClass
    revenue_model: str
    buyer_persona: str
    seller_persona: str
    commercial_use_cases: list[str]
    pricing_logic: str
    fulfillment_model: str
    compliance_burden: str
    defensibility_note: str


@dataclass(frozen=True)
class ProofRequirementSpec:
    key: str
    label: str
    description: str
    weight: int
    blocks_publication_if_missing: bool = False


@dataclass(frozen=True)
class ListingPacket:
    packet_id: str
    listing_id: str
    inventory_item_id: str
    sku: str
    sku_family: str
    proprietary_asset_class: str
    title: str
    subtitle: str
    description: str
    commercial_profile: dict[str, Any]
    pricing: dict[str, Any]
    proof_score: int
    proof_grade: str
    liquidity_score: int
    compliance_score: int
    operator_score: int
    valuation_score: int
    risk_tier: str
    review_actions: list[str]
    missing_proof: list[str]
    required_owner_fields: list[str]
    diligence_metadata: dict[str, Any]
    seo: dict[str, Any]
    proof_manifest: list[dict[str, Any]]
    proprietary_tags: list[str]
    packet_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SCORE_BANDS: list[ProprietaryScoreBand] = [
    ProprietaryScoreBand("institutional_ready", 90, 100, "Strong proof, clean risk profile, high marketplace readiness.", MembraReviewAction.AUTO_PRIVATE_DRAFT),
    ProprietaryScoreBand("marketplace_ready", 78, 89, "Good proof and commercial shape; owner fields may still be needed.", MembraReviewAction.OWNER_FIELDS_REQUIRED),
    ProprietaryScoreBand("operator_review", 62, 77, "Potentially valuable but requires operator review before visibility.", MembraReviewAction.OPERATOR_REVIEW_REQUIRED),
    ProprietaryScoreBand("proof_retake", 45, 61, "Commercial thesis exists but evidence quality or proof is weak.", MembraReviewAction.PROOF_RETAKE_REQUIRED),
    ProprietaryScoreBand("blocked_or_immature", 0, 44, "Insufficient proof or unacceptable risk for marketplace visibility.", MembraReviewAction.BLOCK_PUBLICATION),
]


COMMERCIAL_PROFILES: dict[MembraAssetClass, MembraCommercialProfile] = {
    MembraAssetClass.LOCAL_MEDIA_SURFACE: MembraCommercialProfile(
        asset_class=MembraAssetClass.LOCAL_MEDIA_SURFACE,
        revenue_model="monthly local advertising placement, QR/NFC campaign placement, or sponsored surface rental",
        buyer_persona="local business, event promoter, creator, political/nonprofit campaign subject to rules, neighborhood service provider",
        seller_persona="owner or tenant with permitted visible window/wall/surface inventory",
        commercial_use_cases=["QR poster placement", "neighborhood campaign landing page", "local lead generation", "foot-traffic attribution", "micro-sponsorship"],
        pricing_logic="visibility angle, foot traffic proxy, surface dimensions, permission certainty, campaign duration, proof completeness",
        fulfillment_model="owner confirms surface rules; operator reviews creative; QR/NFC artifact routes visitors to tracked gateway",
        compliance_burden="building rules, lease terms, local advertising/signage rules, content restrictions",
        defensibility_note="MEMBRA owns the proof-backed translation from private surface to controlled local media inventory.",
    ),
    MembraAssetClass.MOBILE_MEDIA_SURFACE: MembraCommercialProfile(
        asset_class=MembraAssetClass.MOBILE_MEDIA_SURFACE,
        revenue_model="mobile ad surface subscription, route-based campaign exposure, QR/NFC decal sponsorship",
        buyer_persona="local advertiser, gig network, event sponsor, creator campaign",
        seller_persona="vehicle owner with permitted surface and predictable route pattern",
        commercial_use_cases=["rear window QR campaign", "mobile neighborhood exposure", "event route promotion", "fleet-lite campaign"],
        pricing_logic="mileage, route density, surface visibility, vehicle condition, campaign safety restrictions, proof cadence",
        fulfillment_model="owner supplies route/mileage; operator approves placement; scans and proof photos record campaign activity",
        compliance_burden="vehicle safety, obstruction rules, local advertising regulations, insurance considerations",
        defensibility_note="MEMBRA converts individual movement patterns into auditable mobile media inventory without fleet ownership.",
    ),
    MembraAssetClass.STORAGE_ACCESS: MembraCommercialProfile(
        asset_class=MembraAssetClass.STORAGE_ACCESS,
        revenue_model="short-term storage fee, neighborhood micro-storage subscription, overflow storage access",
        buyer_persona="neighbor, student, micro-seller, traveler, local operator needing small storage",
        seller_persona="owner/tenant with permitted closet, shelf, garage, or storage capacity",
        commercial_use_cases=["closet storage", "package staging", "micro-warehouse shelf", "seasonal goods holding"],
        pricing_logic="dimensions, access frequency, weight limit, security, permission certainty, prohibited item scope",
        fulfillment_model="owner defines rules and access windows; proof photos establish condition and item boundaries",
        compliance_burden="lease/building rules, liability, prohibited goods, insurance, privacy",
        defensibility_note="MEMBRA structures unused spatial capacity into bounded, proof-controlled inventory.",
    ),
    MembraAssetClass.WORKSPACE_ACCESS: MembraCommercialProfile(
        asset_class=MembraAssetClass.WORKSPACE_ACCESS,
        revenue_model="hourly workspace access, creator station rental, remote-work micro-booking",
        buyer_persona="remote worker, creator, freelancer, student, local professional",
        seller_persona="owner/tenant with permitted desk, room, studio corner, or creator setup",
        commercial_use_cases=["desk booking", "creator backdrop", "quiet work session", "equipment-assisted content session"],
        pricing_logic="availability, equipment, privacy, internet, noise level, location convenience, proof completeness",
        fulfillment_model="owner confirms rules and schedule; operator may require identity/booking controls before public use",
        compliance_burden="access control, privacy, building rules, safety, insurance",
        defensibility_note="MEMBRA packages informal workspace into reviewable access inventory with owner-controlled terms.",
    ),
    MembraAssetClass.TOOL_ACCESS: MembraCommercialProfile(
        asset_class=MembraAssetClass.TOOL_ACCESS,
        revenue_model="tool rental, borrowing kit access, equipment deposit-and-return workflow",
        buyer_persona="neighbor, DIY user, creator, micro-contractor for non-regulated tasks",
        seller_persona="owner of tools/equipment willing to lend/rent locally",
        commercial_use_cases=["drill rental", "ladder access", "creator kit", "cleaning equipment", "repair kit"],
        pricing_logic="replacement value, condition, demand, deposit requirement, handoff rules, return proof",
        fulfillment_model="owner lists condition; borrower follows pickup/return proof; damage policy handled outside custody",
        compliance_burden="safe use, regulated work exclusion, liability, damage, loss",
        defensibility_note="MEMBRA converts household equipment into structured tool access with proof and review fields.",
    ),
    MembraAssetClass.WEARABLE_MEDIA_SURFACE: MembraCommercialProfile(
        asset_class=MembraAssetClass.WEARABLE_MEDIA_SURFACE,
        revenue_model="wearable campaign surface sponsorship, QR/NFC clothing activation, creator street-team placement",
        buyer_persona="creator, brand, local campaign, event promoter",
        seller_persona="person with permitted wearable surface and campaign consent",
        commercial_use_cases=["hoodie QR campaign", "backpack decal", "hat sponsorship", "event street-team proof"],
        pricing_logic="wear frequency, location density, surface size, brand-safety risk, proof cadence",
        fulfillment_model="owner confirms consent; operator approves creative; QR gateway records scans; proof photos verify placement",
        compliance_burden="brand safety, campaign content, consent, performance non-guarantee",
        defensibility_note="MEMBRA creates a controlled bridge from individual wearable surfaces to measurable campaign inventory.",
    ),
    MembraAssetClass.RESALE_INVENTORY: MembraCommercialProfile(
        asset_class=MembraAssetClass.RESALE_INVENTORY,
        revenue_model="resale bundle, liquidation packet, sorting task plus resale routing",
        buyer_persona="reseller, local buyer, donation/logistics operator, bundle liquidator",
        seller_persona="owner with items to sell, sort, donate, or liquidate",
        commercial_use_cases=["clothing bundle", "household goods lot", "moving liquidation", "declutter-to-resale"],
        pricing_logic="item count, condition, brands, category mix, proof photos, pickup/shipping constraints",
        fulfillment_model="owner supplies bundle proof; operator may request itemization; external buyer handles settlement",
        compliance_burden="condition accuracy, counterfeit screening, privacy, prohibited goods",
        defensibility_note="MEMBRA creates SKU discipline around messy household reality, making resale inventory reviewable.",
    ),
    MembraAssetClass.LOCAL_RELAY: MembraCommercialProfile(
        asset_class=MembraAssetClass.LOCAL_RELAY,
        revenue_model="pickup/dropoff capacity, local handoff fee, package staging eligibility",
        buyer_persona="local seller, neighbor, micro-logistics operator, event team",
        seller_persona="owner/tenant with permitted, secure handoff availability",
        commercial_use_cases=["package pickup point", "local relay", "event kit handoff", "neighborhood staging"],
        pricing_logic="availability, security, package size, location, proof rules, restricted item policy",
        fulfillment_model="owner defines handoff windows and proof events; operator reviews restricted-item policy",
        compliance_burden="security, liability, restricted items, building rules",
        defensibility_note="MEMBRA packages local trust and availability into auditable relay capacity.",
    ),
}


PROOF_REQUIREMENTS: dict[MembraAssetClass, list[ProofRequirementSpec]] = {
    MembraAssetClass.LOCAL_MEDIA_SURFACE: [
        ProofRequirementSpec("inside_photo", "Inside surface photo", "Photo showing the usable surface from inside or owner-controlled position.", 16, True),
        ProofRequirementSpec("outside_visibility", "Outside visibility angle", "Photo or note proving that the surface can be seen by intended audience.", 18, True),
        ProofRequirementSpec("dimensions", "Surface dimensions", "Width and height of usable placement area.", 14, True),
        ProofRequirementSpec("permission", "Permission confirmation", "Lease/building/owner rule confirmation.", 22, True),
        ProofRequirementSpec("creative_rules", "Creative/media restrictions", "Allowed media type, removable adhesive, campaign rules.", 10, False),
        ProofRequirementSpec("campaign_window", "Campaign availability", "Dates or time window when surface can be used.", 8, False),
    ],
    MembraAssetClass.MOBILE_MEDIA_SURFACE: [
        ProofRequirementSpec("vehicle_photo", "Vehicle photo", "Clear vehicle/surface photo.", 16, True),
        ProofRequirementSpec("placement_area", "Placement area", "Photo or measurement of usable non-obstructive placement area.", 18, True),
        ProofRequirementSpec("route_mileage", "Route/mileage estimate", "Normal route, region, or weekly mileage estimate.", 16, False),
        ProofRequirementSpec("owner_permission", "Owner permission", "Vehicle owner/control confirmation.", 22, True),
        ProofRequirementSpec("safety_check", "Safety/non-obstruction check", "Owner confirms placement will not obstruct driver view or violate safety rules.", 18, True),
    ],
    MembraAssetClass.STORAGE_ACCESS: [
        ProofRequirementSpec("space_photo", "Storage photo", "Clear photo of storage area.", 15, True),
        ProofRequirementSpec("dimensions", "Dimensions", "Width, height, depth, and access constraints.", 18, True),
        ProofRequirementSpec("weight_limit", "Weight limit", "Maximum weight or category limits.", 8, False),
        ProofRequirementSpec("access_rules", "Access rules", "Pickup/dropoff hours and entry method.", 16, True),
        ProofRequirementSpec("prohibited_items", "Prohibited items", "Restricted goods and safety limitations.", 18, True),
        ProofRequirementSpec("permission", "Permission confirmation", "Lease/building/owner permission.", 20, True),
    ],
    MembraAssetClass.WORKSPACE_ACCESS: [
        ProofRequirementSpec("workspace_photo", "Workspace photo", "Clear desk/work area photo.", 15, True),
        ProofRequirementSpec("availability", "Availability", "Hours and booking windows.", 15, True),
        ProofRequirementSpec("house_rules", "House rules", "Rules for access, guests, noise, privacy.", 18, True),
        ProofRequirementSpec("internet", "Internet/equipment", "Wi-Fi/equipment availability and restrictions.", 8, False),
        ProofRequirementSpec("permission", "Permission confirmation", "Lease/building/owner permission.", 22, True),
        ProofRequirementSpec("access_control", "Access control", "How visitor access is managed.", 14, True),
    ],
    MembraAssetClass.TOOL_ACCESS: [
        ProofRequirementSpec("tool_photo", "Tool photo", "Clear photo of exact tool/equipment.", 14, True),
        ProofRequirementSpec("condition", "Condition notes", "Working condition, defects, accessories.", 16, True),
        ProofRequirementSpec("replacement_value", "Replacement value", "Estimated value for deposit/dispute handling.", 12, False),
        ProofRequirementSpec("pickup_return", "Pickup/return rules", "Time, location, return proof.", 18, True),
        ProofRequirementSpec("safe_use", "Safe-use restrictions", "Allowed uses and excluded regulated/professional work.", 18, True),
        ProofRequirementSpec("owner_confirmation", "Owner confirmation", "Owner control and lending approval.", 18, True),
    ],
    MembraAssetClass.WEARABLE_MEDIA_SURFACE: [
        ProofRequirementSpec("wearable_photo", "Wearable photo", "Clear photo of wearable surface.", 14, True),
        ProofRequirementSpec("surface_dimensions", "Surface dimensions", "Usable QR/decal/poster area.", 14, True),
        ProofRequirementSpec("wear_frequency", "Wear frequency", "Expected wear/use cadence.", 10, False),
        ProofRequirementSpec("campaign_consent", "Campaign consent", "Consent to campaign categories and creative.", 22, True),
        ProofRequirementSpec("brand_safety", "Brand-safety rules", "Excluded categories or messaging.", 14, True),
        ProofRequirementSpec("proof_cadence", "Proof cadence", "How placement/use is verified.", 10, False),
    ],
    MembraAssetClass.RESALE_INVENTORY: [
        ProofRequirementSpec("bundle_photo", "Bundle photo", "Photo of full bundle or lot.", 14, True),
        ProofRequirementSpec("item_count", "Item count", "Approximate item count or itemization.", 14, True),
        ProofRequirementSpec("condition", "Condition notes", "Condition grade and defects.", 18, True),
        ProofRequirementSpec("ownership", "Ownership confirmation", "Owner confirms authority to sell/route items.", 22, True),
        ProofRequirementSpec("brand_screening", "Brand/counterfeit screening", "Brand notes if relevant.", 10, False),
        ProofRequirementSpec("privacy_screen", "Private-item screen", "Owner confirms no private/sensitive items included.", 16, True),
    ],
    MembraAssetClass.LOCAL_RELAY: [
        ProofRequirementSpec("handoff_area", "Handoff area photo", "Photo of pickup/dropoff staging area.", 14, True),
        ProofRequirementSpec("availability", "Availability", "Time windows and response expectations.", 14, True),
        ProofRequirementSpec("package_limits", "Package limits", "Size, weight, and category restrictions.", 16, True),
        ProofRequirementSpec("restricted_items", "Restricted items", "Prohibited item policy.", 20, True),
        ProofRequirementSpec("proof_method", "Proof method", "Photo, QR scan, or code exchange proof.", 16, True),
        ProofRequirementSpec("permission", "Permission confirmation", "Owner/building permission for handoff use.", 18, True),
    ],
}


ASSET_CLASS_ALIASES: dict[str, MembraAssetClass] = {
    "local_media_surface": MembraAssetClass.LOCAL_MEDIA_SURFACE,
    "window_ad_surface": MembraAssetClass.LOCAL_MEDIA_SURFACE,
    "wall_qr_surface": MembraAssetClass.LOCAL_MEDIA_SURFACE,
    "mobile_media_surface": MembraAssetClass.MOBILE_MEDIA_SURFACE,
    "car_ad_space": MembraAssetClass.MOBILE_MEDIA_SURFACE,
    "campaign_route": MembraAssetClass.MOBILE_MEDIA_SURFACE,
    "storage_access": MembraAssetClass.STORAGE_ACCESS,
    "storage_space": MembraAssetClass.STORAGE_ACCESS,
    "workspace_access": MembraAssetClass.WORKSPACE_ACCESS,
    "workspace": MembraAssetClass.WORKSPACE_ACCESS,
    "seating_or_workspace": MembraAssetClass.WORKSPACE_ACCESS,
    "tool_access": MembraAssetClass.TOOL_ACCESS,
    "local_tool": MembraAssetClass.TOOL_ACCESS,
    "wearable_media_surface": MembraAssetClass.WEARABLE_MEDIA_SURFACE,
    "wearable_media": MembraAssetClass.WEARABLE_MEDIA_SURFACE,
    "resale_inventory": MembraAssetClass.RESALE_INVENTORY,
    "resale_bundle": MembraAssetClass.RESALE_INVENTORY,
    "local_relay": MembraAssetClass.LOCAL_RELAY,
    "handoff_point": MembraAssetClass.LOCAL_RELAY,
    "service_task": MembraAssetClass.SERVICE_TASK,
    "local_task": MembraAssetClass.SERVICE_TASK,
}


PROPRIETARY_TAG_PREFIX = "MEMBRA_OS"


def normalize_asset_class(value: str | None) -> MembraAssetClass:
    if not value:
        return MembraAssetClass.UNKNOWN
    key = value.strip().lower()
    return ASSET_CLASS_ALIASES.get(key, MembraAssetClass(key) if key in MembraAssetClass._value2member_map_ else MembraAssetClass.UNKNOWN)


def stable_hash(payload: Any, length: int = 20) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:length]


def sku_family_from_sku(sku: str) -> str:
    parts = (sku or "").split("-")
    if len(parts) >= 2:
        return parts[1].upper()
    return "UNKNOWN"


def clamp_int(value: float, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, int(round(value))))


def grade(score: int) -> str:
    if score >= 90:
        return "A+"
    if score >= 82:
        return "A"
    if score >= 74:
        return "B"
    if score >= 62:
        return "C"
    if score >= 45:
        return "D"
    return "F"


def score_band(score: int) -> ProprietaryScoreBand:
    for band in SCORE_BANDS:
        if band.min_score <= score <= band.max_score:
            return band
    return SCORE_BANDS[-1]


def text_has_any(text: str, phrases: list[str]) -> bool:
    haystack = text.lower()
    return any(p.lower() in haystack for p in phrases)


def collect_text(*objects: Any) -> str:
    parts: list[str] = []
    for obj in objects:
        if obj is None:
            continue
        if isinstance(obj, str):
            parts.append(obj)
        elif isinstance(obj, dict):
            parts.append(json.dumps(obj, default=str))
        elif isinstance(obj, list):
            parts.append(json.dumps(obj, default=str))
        else:
            parts.append(str(obj))
    return " ".join(parts).lower()


def proof_specs_for(asset_class: MembraAssetClass) -> list[ProofRequirementSpec]:
    return PROOF_REQUIREMENTS.get(asset_class, [])


def build_proof_manifest(
    *,
    asset_class: MembraAssetClass,
    inventory_item: dict[str, Any],
    sku_identification: dict[str, Any] | None,
    image_quality: dict[str, Any] | None,
    owner_fields: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], int, list[str]]:
    owner_fields = owner_fields or {}
    text = collect_text(inventory_item, sku_identification, image_quality, owner_fields)
    manifest: list[dict[str, Any]] = []
    earned = 0
    possible = 0
    missing: list[str] = []

    synonym_map: dict[str, list[str]] = {
        "inside_photo": ["inside", "photo", "image", "surface"],
        "outside_visibility": ["outside", "visibility", "street", "view", "angle"],
        "dimensions": ["dimension", "width", "height", "depth", "surface_width", "surface_height"],
        "permission": ["permission", "lease", "building", "owner", "confirmation"],
        "owner_permission": ["owner", "permission", "vehicle owner", "confirmation"],
        "creative_rules": ["creative", "media", "allowed", "removable", "rules"],
        "campaign_window": ["campaign", "availability", "dates", "window"],
        "vehicle_photo": ["vehicle", "car", "photo", "image"],
        "placement_area": ["placement", "surface", "window", "decal", "area"],
        "route_mileage": ["route", "mileage", "commute", "weekly"],
        "safety_check": ["safety", "non-obstruction", "obstruction", "driver"],
        "space_photo": ["storage", "space", "closet", "photo", "image"],
        "weight_limit": ["weight", "limit", "lb", "pounds"],
        "access_rules": ["access", "hours", "rules", "pickup"],
        "prohibited_items": ["prohibited", "restricted", "items", "goods"],
        "workspace_photo": ["workspace", "desk", "photo", "office"],
        "availability": ["availability", "hours", "schedule", "time"],
        "house_rules": ["house", "rules", "guest", "noise", "privacy"],
        "internet": ["wifi", "internet", "monitor", "equipment"],
        "access_control": ["access", "control", "entry", "visitor"],
        "tool_photo": ["tool", "photo", "drill", "ladder", "equipment"],
        "condition": ["condition", "defect", "working", "grade"],
        "replacement_value": ["replacement", "value", "deposit", "price"],
        "pickup_return": ["pickup", "return", "handoff", "rules"],
        "safe_use": ["safe", "safety", "use", "restricted", "regulated"],
        "owner_confirmation": ["owner", "confirmation", "control"],
        "wearable_photo": ["wearable", "shirt", "hoodie", "photo", "image"],
        "surface_dimensions": ["surface", "dimensions", "width", "height"],
        "wear_frequency": ["wear", "frequency", "daily", "weekly"],
        "campaign_consent": ["campaign", "consent", "creative", "approval"],
        "brand_safety": ["brand", "safety", "excluded", "categories"],
        "proof_cadence": ["proof", "cadence", "verify", "photo"],
        "bundle_photo": ["bundle", "photo", "lot", "image"],
        "item_count": ["item_count", "count", "items", "quantity"],
        "ownership": ["ownership", "owner", "authority", "sell"],
        "brand_screening": ["brand", "counterfeit", "authentic"],
        "privacy_screen": ["privacy", "private", "sensitive", "excluded"],
        "handoff_area": ["handoff", "pickup", "area", "lobby", "entry"],
        "package_limits": ["package", "size", "weight", "limits"],
        "restricted_items": ["restricted", "prohibited", "items"],
        "proof_method": ["proof", "qr", "scan", "code", "photo"],
    }

    for spec in proof_specs_for(asset_class):
        possible += spec.weight
        aliases = synonym_map.get(spec.key, [spec.key])
        owner_value_present = bool(owner_fields.get(spec.key))
        text_present = text_has_any(text, aliases)
        present = owner_value_present or text_present
        confidence = 1.0 if owner_value_present else 0.72 if text_present else 0.0
        points = int(round(spec.weight * confidence)) if present else 0
        earned += points
        if not present:
            missing.append(spec.key)
        manifest.append(
            {
                "key": spec.key,
                "label": spec.label,
                "description": spec.description,
                "weight": spec.weight,
                "present": present,
                "confidence": confidence,
                "points_awarded": points,
                "blocks_publication_if_missing": spec.blocks_publication_if_missing,
            }
        )

    proof_score = clamp_int((earned / possible) * 100 if possible else 30)
    return manifest, proof_score, missing


def compute_liquidity_score(asset_class: MembraAssetClass, inventory_item: dict[str, Any], sku_identification: dict[str, Any] | None) -> int:
    text = collect_text(inventory_item, sku_identification)
    base = {
        MembraAssetClass.LOCAL_MEDIA_SURFACE: 70,
        MembraAssetClass.MOBILE_MEDIA_SURFACE: 66,
        MembraAssetClass.STORAGE_ACCESS: 74,
        MembraAssetClass.WORKSPACE_ACCESS: 68,
        MembraAssetClass.TOOL_ACCESS: 72,
        MembraAssetClass.WEARABLE_MEDIA_SURFACE: 56,
        MembraAssetClass.RESALE_INVENTORY: 64,
        MembraAssetClass.LOCAL_RELAY: 58,
        MembraAssetClass.SERVICE_TASK: 52,
        MembraAssetClass.UNKNOWN: 35,
    }.get(asset_class, 35)
    confidence = float(inventory_item.get("confidence") or (sku_identification or {}).get("confidence") or 0.5)
    price_low = float(inventory_item.get("suggested_price_low") or 0)
    price_high = float(inventory_item.get("suggested_price_high") or 0)
    price_signal = 0
    if price_high > price_low > 0:
        midpoint = (price_low + price_high) / 2
        price_signal = clamp_int(math.log10(max(midpoint, 1)) * 8, 0, 18)
    context_bonus = 0
    if text_has_any(text, ["window", "street", "storage", "tool", "desk", "vehicle", "route", "closet"]):
        context_bonus += 7
    return clamp_int(base + (confidence - 0.5) * 30 + price_signal + context_bonus)


def compute_compliance_score(asset_class: MembraAssetClass, proof_score: int, risk_flags: list[str], missing_proof: list[str]) -> int:
    base = 80
    high_risk_terms = ["permission", "building", "lease", "safety", "vehicle", "liability", "restricted", "prohibited", "privacy"]
    joined = " ".join(risk_flags + missing_proof).lower()
    penalty = 0
    for term in high_risk_terms:
        if term in joined:
            penalty += 5
    if proof_score < 60:
        penalty += 12
    if asset_class in {MembraAssetClass.MOBILE_MEDIA_SURFACE, MembraAssetClass.WORKSPACE_ACCESS, MembraAssetClass.STORAGE_ACCESS}:
        penalty += 4
    return clamp_int(base - penalty + proof_score * 0.18)


def compute_operator_score(*, proof_score: int, liquidity_score: int, compliance_score: int, image_quality: dict[str, Any] | None) -> int:
    image_score = int((image_quality or {}).get("listing_quality_score") or 60)
    return clamp_int(proof_score * 0.32 + liquidity_score * 0.28 + compliance_score * 0.25 + image_score * 0.15)


def compute_valuation_score(operator_score: int, liquidity_score: int, proof_score: int, asset_class: MembraAssetClass) -> int:
    strategic_bonus = {
        MembraAssetClass.LOCAL_MEDIA_SURFACE: 8,
        MembraAssetClass.MOBILE_MEDIA_SURFACE: 7,
        MembraAssetClass.STORAGE_ACCESS: 6,
        MembraAssetClass.TOOL_ACCESS: 5,
        MembraAssetClass.WORKSPACE_ACCESS: 5,
        MembraAssetClass.WEARABLE_MEDIA_SURFACE: 3,
        MembraAssetClass.RESALE_INVENTORY: 4,
        MembraAssetClass.LOCAL_RELAY: 4,
    }.get(asset_class, 0)
    return clamp_int(operator_score * 0.50 + liquidity_score * 0.28 + proof_score * 0.22 + strategic_bonus)


def determine_risk_tier(compliance_score: int, proof_score: int, risk_flags: list[str], missing_proof: list[str]) -> MembraRiskTier:
    text = " ".join(risk_flags + missing_proof).lower()
    if text_has_any(text, ["private key", "weapon", "illegal", "unconsented", "raw credential"]):
        return MembraRiskTier.BLOCKED
    if compliance_score < 45 or proof_score < 35:
        return MembraRiskTier.RED
    if compliance_score < 60 or text_has_any(text, ["permission", "safety", "restricted", "prohibited"]):
        return MembraRiskTier.ORANGE
    if compliance_score < 78 or risk_flags:
        return MembraRiskTier.YELLOW
    return MembraRiskTier.GREEN


def determine_review_actions(
    *,
    risk_tier: MembraRiskTier,
    proof_score: int,
    compliance_score: int,
    image_quality: dict[str, Any] | None,
    missing_proof: list[str],
    proof_manifest: list[dict[str, Any]],
) -> list[str]:
    actions: set[MembraReviewAction] = set()
    image_score = int((image_quality or {}).get("listing_quality_score") or 60)
    if risk_tier in {MembraRiskTier.BLOCKED, MembraRiskTier.RED}:
        actions.add(MembraReviewAction.BLOCK_PUBLICATION)
    if risk_tier in {MembraRiskTier.ORANGE, MembraRiskTier.YELLOW}:
        actions.add(MembraReviewAction.OPERATOR_REVIEW_REQUIRED)
    if compliance_score < 70:
        actions.add(MembraReviewAction.COMPLIANCE_REVIEW_REQUIRED)
    if proof_score < 78 or missing_proof:
        actions.add(MembraReviewAction.OWNER_FIELDS_REQUIRED)
    if image_score < 55:
        actions.add(MembraReviewAction.PROOF_RETAKE_REQUIRED)
    blocking_missing = [p for p in proof_manifest if p["blocks_publication_if_missing"] and not p["present"]]
    if blocking_missing:
        actions.add(MembraReviewAction.BLOCK_PUBLICATION)
    if not actions:
        actions.add(MembraReviewAction.AUTO_PRIVATE_DRAFT)
    priority = [
        MembraReviewAction.BLOCK_PUBLICATION,
        MembraReviewAction.PROOF_RETAKE_REQUIRED,
        MembraReviewAction.COMPLIANCE_REVIEW_REQUIRED,
        MembraReviewAction.OPERATOR_REVIEW_REQUIRED,
        MembraReviewAction.OWNER_FIELDS_REQUIRED,
        MembraReviewAction.AUTO_PRIVATE_DRAFT,
    ]
    return [a.value for a in priority if a in actions]


def build_pricing_packet(inventory_item: dict[str, Any], liquidity_score: int, proof_score: int, risk_tier: MembraRiskTier) -> dict[str, Any]:
    low = float(inventory_item.get("suggested_price_low") or 0)
    high = float(inventory_item.get("suggested_price_high") or 0)
    unit = inventory_item.get("pricing_unit") or "monthly"
    midpoint = round((low + high) / 2, 2) if high or low else 0
    confidence_multiplier = 1.0
    if liquidity_score >= 80 and proof_score >= 75:
        confidence_multiplier = 1.12
    elif liquidity_score < 55 or proof_score < 55:
        confidence_multiplier = 0.82
    if risk_tier in {MembraRiskTier.ORANGE, MembraRiskTier.RED, MembraRiskTier.BLOCKED}:
        confidence_multiplier *= 0.72
    appraisal_low = round(low * confidence_multiplier, 2)
    appraisal_high = round(high * confidence_multiplier, 2)
    return {
        "suggested_price_low": low,
        "suggested_price_high": high,
        "pricing_unit": unit,
        "midpoint": midpoint,
        "confidence_multiplier": round(confidence_multiplier, 3),
        "appraisal_adjusted_low": appraisal_low,
        "appraisal_adjusted_high": appraisal_high,
        "appraisal_midpoint": round((appraisal_low + appraisal_high) / 2, 2) if appraisal_high or appraisal_low else 0,
        "pricing_disclaimer": "Estimate only. Earnings are not guaranteed. External settlement rails required.",
    }


def build_seo_packet(title: str, asset_class: MembraAssetClass, location_hint: str | None, tags: list[str]) -> dict[str, Any]:
    location = (location_hint or "local").strip() or "local"
    slug_base = re.sub(r"[^a-z0-9]+", "-", f"{title}-{location}".lower()).strip("-")[:90]
    keywords = list(dict.fromkeys([asset_class.value.replace("_", " "), location, *tags, "MEMBRA", "owner controlled", "proof backed"]))
    meta_title = f"{title} | MEMBRA {location}"[:70]
    meta_description = (
        f"Proof-backed {asset_class.value.replace('_', ' ')} listing in {location}. Owner-controlled visibility, QR-ready artifact, and MEMBRA audit trail."
    )[:155]
    return {
        "slug": slug_base,
        "meta_title": meta_title,
        "meta_description": meta_description,
        "keywords": keywords,
    }


def build_proprietary_tags(asset_class: MembraAssetClass, sku_family: str, risk_tier: MembraRiskTier, proof_grade: str) -> list[str]:
    return [
        f"{PROPRIETARY_TAG_PREFIX}:{asset_class.value}",
        f"{PROPRIETARY_TAG_PREFIX}:SKU:{sku_family}",
        f"{PROPRIETARY_TAG_PREFIX}:RISK:{risk_tier.value}",
        f"{PROPRIETARY_TAG_PREFIX}:PROOF:{proof_grade}",
        "MEMBRA_OWNER_CONTROLLED",
        "MEMBRA_PROOFBOOK_ELIGIBLE",
    ]


def build_diligence_metadata(
    *,
    inventory_item: dict[str, Any],
    listing_draft: dict[str, Any] | None,
    sku_identification: dict[str, Any] | None,
    image_quality: dict[str, Any] | None,
    owner_fields: dict[str, Any] | None,
    risk_tier: MembraRiskTier,
) -> dict[str, Any]:
    return {
        "inventory_item_id": inventory_item.get("inventory_item_id"),
        "listing_id": (listing_draft or {}).get("listing_id"),
        "source_photo_id": inventory_item.get("source_photo_id"),
        "sku_confidence": (sku_identification or {}).get("confidence"),
        "sku_confidence_grade": (sku_identification or {}).get("confidence_grade"),
        "image_quality_score": (image_quality or {}).get("listing_quality_score"),
        "image_quality_grade": (image_quality or {}).get("quality_grade"),
        "image_sha256": (image_quality or {}).get("exact_sha256"),
        "average_hash": (image_quality or {}).get("average_hash"),
        "owner_field_count": len(owner_fields or {}),
        "risk_tier": risk_tier.value,
        "non_custodial": True,
        "owner_visibility_required": True,
        "external_settlement_required": True,
    }


def commercial_profile_for(asset_class: MembraAssetClass) -> MembraCommercialProfile:
    return COMMERCIAL_PROFILES.get(
        asset_class,
        MembraCommercialProfile(
            asset_class=MembraAssetClass.UNKNOWN,
            revenue_model="manual review required",
            buyer_persona="unknown",
            seller_persona="unknown",
            commercial_use_cases=[],
            pricing_logic="insufficient data",
            fulfillment_model="operator review required",
            compliance_burden="unknown",
            defensibility_note="Unclassified asset requires manual taxonomy assignment.",
        ),
    )


def generate_listing_packet(
    *,
    inventory_item: dict[str, Any],
    listing_draft: dict[str, Any] | None = None,
    sku_identification: dict[str, Any] | None = None,
    image_quality: dict[str, Any] | None = None,
    owner_fields: dict[str, Any] | None = None,
    location_hint: str | None = None,
) -> ListingPacket:
    """Generate a proprietary MEMBRA commercial packet for a listing candidate."""
    sku = inventory_item.get("sku") or (sku_identification or {}).get("sku") or "MEMBRA-UNKNOWN-0000"
    sku_family = sku_family_from_sku(sku)
    raw_asset_class = (
        (sku_identification or {}).get("marketplace_category")
        or inventory_item.get("asset_type")
        or inventory_item.get("monetization_type")
    )
    asset_class = normalize_asset_class(raw_asset_class)
    profile = commercial_profile_for(asset_class)

    risk_flags = list(inventory_item.get("risk_flags") or [])
    if isinstance(inventory_item.get("risk_flags_json"), str):
        try:
            risk_flags.extend(json.loads(inventory_item["risk_flags_json"]))
        except Exception:
            pass
    risk_flags.extend((sku_identification or {}).get("risk_flags") or [])

    proof_manifest, proof_score, missing_proof = build_proof_manifest(
        asset_class=asset_class,
        inventory_item=inventory_item,
        sku_identification=sku_identification,
        image_quality=image_quality,
        owner_fields=owner_fields,
    )
    liquidity_score = compute_liquidity_score(asset_class, inventory_item, sku_identification)
    compliance_score = compute_compliance_score(asset_class, proof_score, risk_flags, missing_proof)
    operator_score = compute_operator_score(
        proof_score=proof_score,
        liquidity_score=liquidity_score,
        compliance_score=compliance_score,
        image_quality=image_quality,
    )
    valuation_score = compute_valuation_score(operator_score, liquidity_score, proof_score, asset_class)
    risk_tier = determine_risk_tier(compliance_score, proof_score, risk_flags, missing_proof)
    review_actions = determine_review_actions(
        risk_tier=risk_tier,
        proof_score=proof_score,
        compliance_score=compliance_score,
        image_quality=image_quality,
        missing_proof=missing_proof,
        proof_manifest=proof_manifest,
    )

    title = (
        (sku_identification or {}).get("suggested_listing_title")
        or (listing_draft or {}).get("title")
        or inventory_item.get("detected_name")
        or profile.asset_class.value.replace("_", " ").title()
    )
    subtitle = f"{profile.asset_class.value.replace('_', ' ').title()} • MEMBRA {sku_family} • Proof grade {grade(proof_score)}"
    description = (
        (sku_identification or {}).get("suggested_listing_description")
        or (listing_draft or {}).get("description")
        or inventory_item.get("description")
        or profile.defensibility_note
    )
    owner_required_fields = list(dict.fromkeys((sku_identification or {}).get("requested_owner_fields") or []))
    if not owner_required_fields:
        owner_required_fields = missing_proof

    tags = list(dict.fromkeys((sku_identification or {}).get("suggested_tags") or []))
    proprietary_tags = build_proprietary_tags(asset_class, sku_family, risk_tier, grade(proof_score))
    seo = build_seo_packet(title, asset_class, location_hint, tags)
    diligence_metadata = build_diligence_metadata(
        inventory_item=inventory_item,
        listing_draft=listing_draft,
        sku_identification=sku_identification,
        image_quality=image_quality,
        owner_fields=owner_fields,
        risk_tier=risk_tier,
    )
    pricing = build_pricing_packet(inventory_item, liquidity_score, proof_score, risk_tier)

    packet_core = {
        "sku": sku,
        "asset_class": asset_class.value,
        "title": title,
        "proof_score": proof_score,
        "liquidity_score": liquidity_score,
        "compliance_score": compliance_score,
        "operator_score": operator_score,
        "valuation_score": valuation_score,
        "risk_tier": risk_tier.value,
        "missing_proof": missing_proof,
        "pricing": pricing,
        "diligence": diligence_metadata,
    }
    packet_id = f"mpacket_{stable_hash(packet_core, 14)}"
    packet_hash = stable_hash({"packet_id": packet_id, **packet_core}, 64)

    return ListingPacket(
        packet_id=packet_id,
        listing_id=(listing_draft or {}).get("listing_id") or inventory_item.get("listing_id") or "",
        inventory_item_id=inventory_item.get("inventory_item_id") or "",
        sku=sku,
        sku_family=sku_family,
        proprietary_asset_class=asset_class.value,
        title=title,
        subtitle=subtitle,
        description=description,
        commercial_profile=asdict(profile),
        pricing=pricing,
        proof_score=proof_score,
        proof_grade=grade(proof_score),
        liquidity_score=liquidity_score,
        compliance_score=compliance_score,
        operator_score=operator_score,
        valuation_score=valuation_score,
        risk_tier=risk_tier.value,
        review_actions=review_actions,
        missing_proof=missing_proof,
        required_owner_fields=owner_required_fields,
        diligence_metadata=diligence_metadata,
        seo=seo,
        proof_manifest=proof_manifest,
        proprietary_tags=proprietary_tags,
        packet_hash=packet_hash,
    )


def summarize_packet_for_operator(packet: ListingPacket) -> dict[str, Any]:
    """Return an operator-console-friendly summary."""
    band = score_band(packet.operator_score)
    return {
        "packet_id": packet.packet_id,
        "sku": packet.sku,
        "title": packet.title,
        "asset_class": packet.proprietary_asset_class,
        "operator_score": packet.operator_score,
        "valuation_score": packet.valuation_score,
        "proof_grade": packet.proof_grade,
        "risk_tier": packet.risk_tier,
        "score_band": band.label,
        "interpretation": band.interpretation,
        "next_action": packet.review_actions[0] if packet.review_actions else band.operator_action.value,
        "missing_proof_count": len(packet.missing_proof),
        "required_owner_fields": packet.required_owner_fields[:8],
        "appraisal_midpoint": packet.pricing.get("appraisal_midpoint"),
        "packet_hash": packet.packet_hash,
    }


def export_listing_packet_json(packet: ListingPacket, *, pretty: bool = True) -> str:
    return json.dumps(packet.to_dict(), indent=2 if pretty else None, sort_keys=True, default=str)
