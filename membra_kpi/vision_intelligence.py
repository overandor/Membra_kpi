"""MEMBRA Vision Intelligence Layer.

This module converts raw image evidence, optional OCR text, optional vision-model
labels, and MEMBRA SKU context into a proprietary visual intelligence report.

It is designed to run today without external dependencies while being ready for
future integrations:

- Ollama/LLaVA or other local multimodal models
- OpenAI/Groq vision adapters
- OCR engines
- object detection models
- CLIP/SigLIP embeddings

The output is not a generic caption. It is a MEMBRA commercial evidence packet:
visual asset thesis, monetization surfaces, proof gaps, compliance concerns,
operator prompts, and listing-conversion guidance.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class VisualEvidenceClass(str, Enum):
    SURFACE = "surface"
    VEHICLE = "vehicle"
    STORAGE = "storage"
    WORKSPACE = "workspace"
    TOOL = "tool"
    WEARABLE = "wearable"
    RESALE = "resale"
    HANDOFF = "handoff"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class VisionAdapterInput:
    filename: str
    width: int
    height: int
    content_type: str = ""
    image_quality: dict[str, Any] = field(default_factory=dict)
    sku_identification: dict[str, Any] = field(default_factory=dict)
    ocr_text: str = ""
    vision_labels: list[str] = field(default_factory=list)
    model_caption: str = ""
    user_context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MembraVisionReport:
    report_id: str
    visual_evidence_class: str
    visual_thesis: str
    confidence: float
    confidence_grade: str
    detected_commercial_surfaces: list[dict[str, Any]]
    extracted_text_signals: list[str]
    object_signals: list[str]
    proof_opportunities: list[str]
    proof_gaps: list[str]
    compliance_alerts: list[str]
    operator_questions: list[str]
    listing_conversion_guidance: dict[str, Any]
    model_readiness: dict[str, Any]
    report_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SURFACE_TERMS = {
    VisualEvidenceClass.SURFACE: ["window", "glass", "wall", "poster", "sign", "storefront", "door", "surface", "street", "display"],
    VisualEvidenceClass.VEHICLE: ["car", "vehicle", "truck", "van", "rear", "bumper", "windshield", "mileage", "route"],
    VisualEvidenceClass.STORAGE: ["closet", "shelf", "storage", "garage", "basement", "box", "bin", "cabinet", "empty"],
    VisualEvidenceClass.WORKSPACE: ["desk", "chair", "monitor", "office", "workspace", "studio", "lamp", "wifi", "table"],
    VisualEvidenceClass.TOOL: ["tool", "drill", "ladder", "vacuum", "saw", "camera", "tripod", "equipment", "kit"],
    VisualEvidenceClass.WEARABLE: ["shirt", "hoodie", "jacket", "hat", "bag", "backpack", "wearable", "clothing"],
    VisualEvidenceClass.RESALE: ["bundle", "clothes", "shoes", "resale", "lot", "items", "declutter", "donation"],
    VisualEvidenceClass.HANDOFF: ["pickup", "handoff", "delivery", "package", "entry", "lobby", "dropoff", "route"],
}

COMMERCIAL_SURFACE_MAP = {
    VisualEvidenceClass.SURFACE: ["QR poster placement", "window campaign", "local lead-generation surface", "NFC sticker surface"],
    VisualEvidenceClass.VEHICLE: ["mobile QR decal", "route-based campaign", "rear-window ad placement"],
    VisualEvidenceClass.STORAGE: ["closet micro-storage", "shelf storage", "package staging capacity"],
    VisualEvidenceClass.WORKSPACE: ["desk booking", "creator station", "remote work micro-access"],
    VisualEvidenceClass.TOOL: ["tool rental", "creator equipment rental", "repair kit access"],
    VisualEvidenceClass.WEARABLE: ["wearable QR campaign", "street-team proof surface", "brand sponsorship surface"],
    VisualEvidenceClass.RESALE: ["bundle resale", "liquidation lot", "declutter-to-resale packet"],
    VisualEvidenceClass.HANDOFF: ["local pickup point", "relay handoff", "package staging point"],
}

PROOF_GAP_MAP = {
    VisualEvidenceClass.SURFACE: ["outside visibility photo", "surface dimensions", "permission confirmation", "creative placement rules"],
    VisualEvidenceClass.VEHICLE: ["non-obstruction confirmation", "route/mileage estimate", "surface dimensions", "vehicle owner confirmation"],
    VisualEvidenceClass.STORAGE: ["dimensions", "access rules", "weight limit", "prohibited items policy"],
    VisualEvidenceClass.WORKSPACE: ["availability schedule", "house rules", "wifi/equipment terms", "access control"],
    VisualEvidenceClass.TOOL: ["condition proof", "replacement value", "safe-use rules", "return proof"],
    VisualEvidenceClass.WEARABLE: ["surface dimensions", "campaign consent", "wear frequency", "brand-safety restrictions"],
    VisualEvidenceClass.RESALE: ["item count", "condition grade", "ownership confirmation", "private item screen"],
    VisualEvidenceClass.HANDOFF: ["package limits", "restricted-item policy", "handoff availability", "proof method"],
}

COMPLIANCE_MAP = {
    VisualEvidenceClass.SURFACE: ["building/lease signage rules", "local advertising rules", "creative approval required"],
    VisualEvidenceClass.VEHICLE: ["vehicle safety rules", "visibility obstruction risk", "local mobile advertising rules"],
    VisualEvidenceClass.STORAGE: ["liability review", "lease/building storage rules", "prohibited goods policy"],
    VisualEvidenceClass.WORKSPACE: ["privacy/access control", "lease/building rules", "occupancy and safety review"],
    VisualEvidenceClass.TOOL: ["safe-use limitation", "damage/loss handling", "regulated work exclusion"],
    VisualEvidenceClass.WEARABLE: ["brand-safety review", "campaign consent", "performance not guaranteed"],
    VisualEvidenceClass.RESALE: ["condition accuracy", "counterfeit screening if branded", "privacy screening"],
    VisualEvidenceClass.HANDOFF: ["security review", "restricted items policy", "liability review"],
}


TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(*parts: str) -> list[str]:
    return TOKEN_RE.findall(" ".join(parts).lower())


def stable_hash(payload: Any, length: int = 24) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:length]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def confidence_grade(value: float) -> str:
    if value >= 0.88:
        return "A+"
    if value >= 0.78:
        return "A"
    if value >= 0.66:
        return "B"
    if value >= 0.52:
        return "C"
    if value >= 0.38:
        return "D"
    return "F"


def normalize_input(payload: dict[str, Any]) -> VisionAdapterInput:
    return VisionAdapterInput(
        filename=str(payload.get("filename", "")),
        width=int(payload.get("width") or payload.get("image_metadata", {}).get("width") or 0),
        height=int(payload.get("height") or payload.get("image_metadata", {}).get("height") or 0),
        content_type=str(payload.get("content_type") or payload.get("image_metadata", {}).get("content_type") or ""),
        image_quality=payload.get("image_quality") or {},
        sku_identification=payload.get("sku_identification") or {},
        ocr_text=str(payload.get("ocr_text") or ""),
        vision_labels=[str(x).lower() for x in payload.get("vision_labels", []) if str(x).strip()],
        model_caption=str(payload.get("model_caption") or ""),
        user_context=payload.get("user_context") or {},
    )


def infer_visual_class(data: VisionAdapterInput) -> tuple[VisualEvidenceClass, float, list[str]]:
    sku_top = data.sku_identification.get("top_candidate", {}) if isinstance(data.sku_identification, dict) else {}
    context = json.dumps(data.user_context, default=str)
    text = " ".join([
        data.filename,
        data.ocr_text,
        data.model_caption,
        " ".join(data.vision_labels),
        str(sku_top.get("asset_type", "")),
        str(sku_top.get("marketplace_category", "")),
        str(sku_top.get("title", "")),
        context,
    ]).lower()
    tokens = set(tokenize(text))
    scored: list[tuple[VisualEvidenceClass, float, list[str]]] = []
    for klass, terms in SURFACE_TERMS.items():
        matched = [term for term in terms if term in tokens or term in text]
        score = len(matched) / max(len(terms), 1)
        if sku_top.get("marketplace_category") and klass.value in str(sku_top.get("marketplace_category")):
            score += 0.25
        if sku_top.get("asset_type") and any(term in str(sku_top.get("asset_type")) for term in terms):
            score += 0.25
        if matched:
            scored.append((klass, score, matched))
    if not scored:
        return VisualEvidenceClass.UNKNOWN, 0.25, []
    scored.sort(key=lambda x: x[1], reverse=True)
    klass, score, matched = scored[0]
    quality_bonus = 0.05 if int(data.image_quality.get("listing_quality_score") or 0) >= 70 else 0
    label_bonus = min(0.10, len(data.vision_labels) * 0.015)
    return klass, round(clamp(0.42 + score + quality_bonus + label_bonus, 0.05, 0.98), 4), matched


def commercial_surfaces_for(klass: VisualEvidenceClass, confidence: float, matched: list[str]) -> list[dict[str, Any]]:
    surfaces = COMMERCIAL_SURFACE_MAP.get(klass, ["manual review candidate"])
    out = []
    for index, surface in enumerate(surfaces, start=1):
        out.append(
            {
                "surface_id": f"surface_{klass.value}_{index}",
                "surface_type": surface,
                "confidence": round(clamp(confidence - (index - 1) * 0.06, 0.15, 0.96), 4),
                "evidence_terms": matched[:8],
                "monetization_status": "private_draft_candidate" if confidence >= 0.5 else "manual_review_required",
            }
        )
    return out


def extract_text_signals(ocr_text: str, model_caption: str) -> list[str]:
    text = " ".join([ocr_text, model_caption]).strip()
    if not text:
        return []
    chunks = re.split(r"[\n.;]+", text)
    signals = []
    for chunk in chunks:
        cleaned = " ".join(chunk.split())
        if 3 <= len(cleaned) <= 120:
            signals.append(cleaned)
        if len(signals) >= 12:
            break
    return signals


def operator_questions_for(klass: VisualEvidenceClass, proof_gaps: list[str]) -> list[str]:
    base = [
        "Do you own or control this asset/surface?",
        "Are lease, building, HOA, local rules, and consent requirements satisfied?",
        "Should this remain private draft until all proof fields are complete?",
    ]
    specific = {
        VisualEvidenceClass.SURFACE: ["What are the usable surface dimensions?", "Can you provide an outside visibility angle?"],
        VisualEvidenceClass.VEHICLE: ["What is the normal weekly mileage or route?", "Can placement be done without obstructing visibility?"],
        VisualEvidenceClass.STORAGE: ["What are the dimensions and access windows?", "What items are prohibited?"],
        VisualEvidenceClass.WORKSPACE: ["What hours is the workspace available?", "What privacy and house rules apply?"],
        VisualEvidenceClass.TOOL: ["What is the tool condition and replacement value?", "What pickup/return proof is required?"],
        VisualEvidenceClass.WEARABLE: ["What campaign categories are allowed?", "How often will the wearable be used?"],
        VisualEvidenceClass.RESALE: ["How many items are in the bundle?", "What condition grade applies?"],
        VisualEvidenceClass.HANDOFF: ["What are package limits?", "What proof method confirms pickup/dropoff?"],
    }.get(klass, ["What commercial use should MEMBRA evaluate first?"])
    return [*specific, *base, *[f"Provide proof for: {gap}" for gap in proof_gaps[:4]]]


def build_listing_guidance(klass: VisualEvidenceClass, confidence: float, quality_score: int) -> dict[str, Any]:
    if confidence >= 0.72 and quality_score >= 70:
        readiness = "draft_ready"
        next_step = "Create private listing draft and request missing owner fields."
    elif confidence >= 0.52:
        readiness = "operator_review_ready"
        next_step = "Keep private; collect proof fields and operator review before visibility."
    else:
        readiness = "manual_review_required"
        next_step = "Request clearer photo, more context, or model labels before listing."
    return {
        "readiness": readiness,
        "recommended_next_step": next_step,
        "default_visibility": "private_draft",
        "publication_policy": "owner confirmation and MEMBRA proof/compliance gates required",
        "commercial_category": klass.value,
    }


def generate_membra_vision_report(payload: dict[str, Any]) -> dict[str, Any]:
    data = normalize_input(payload)
    klass, confidence, matched = infer_visual_class(data)
    quality_score = int(data.image_quality.get("listing_quality_score") or 0)
    text_signals = extract_text_signals(data.ocr_text, data.model_caption)
    proof_gaps = PROOF_GAP_MAP.get(klass, ["manual classification", "owner confirmation", "clearer photo"])
    compliance = COMPLIANCE_MAP.get(klass, ["manual compliance review"])
    visual_thesis = (
        f"MEMBRA visual intelligence classifies this image as {klass.value}. "
        f"Matched evidence terms: {', '.join(matched) or 'none'}. "
        f"Quality score: {quality_score}. Confidence: {confidence:.2f}."
    )
    report_core = {
        "klass": klass.value,
        "confidence": confidence,
        "filename": data.filename,
        "width": data.width,
        "height": data.height,
        "matched": matched,
        "quality_score": quality_score,
    }
    report_id = f"vreport_{stable_hash(report_core, 16)}"
    report = MembraVisionReport(
        report_id=report_id,
        visual_evidence_class=klass.value,
        visual_thesis=visual_thesis,
        confidence=confidence,
        confidence_grade=confidence_grade(confidence),
        detected_commercial_surfaces=commercial_surfaces_for(klass, confidence, matched),
        extracted_text_signals=text_signals,
        object_signals=sorted(set([*matched, *data.vision_labels]))[:24],
        proof_opportunities=[f"Collect {gap}" for gap in proof_gaps[:6]],
        proof_gaps=proof_gaps,
        compliance_alerts=compliance,
        operator_questions=operator_questions_for(klass, proof_gaps),
        listing_conversion_guidance=build_listing_guidance(klass, confidence, quality_score),
        model_readiness={
            "external_vision_labels_supplied": bool(data.vision_labels),
            "ocr_text_supplied": bool(data.ocr_text),
            "model_caption_supplied": bool(data.model_caption),
            "ready_for_multimodal_upgrade": True,
            "recommended_next_model_adapter": "ollama_llava_or_clip_siglip_adapter",
        },
        report_hash=stable_hash({"report_id": report_id, **report_core}, 64),
    )
    return report.to_dict()


def merge_vision_report_into_owner_fields(report: dict[str, Any], owner_fields: dict[str, Any] | None = None) -> dict[str, Any]:
    """Use a vision report to prefill non-sensitive owner proof hints.

    This does not mark legal permission as satisfied. It only inserts evidence
    hints that help the proprietary listing packet request the right fields.
    """
    owner_fields = dict(owner_fields or {})
    owner_fields.setdefault("visual_evidence_class", report.get("visual_evidence_class"))
    owner_fields.setdefault("visual_confidence_grade", report.get("confidence_grade"))
    owner_fields.setdefault("visual_report_id", report.get("report_id"))
    for surface in report.get("detected_commercial_surfaces", [])[:3]:
        key = f"candidate_{surface.get('surface_id')}"
        owner_fields.setdefault(key, surface.get("surface_type"))
    return owner_fields
