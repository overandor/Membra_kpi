"""Hugging Face endpoint integration layer for MEMBRA KPI.

This module adds safe, token-aware Hugging Face integration metadata and
execution plans for Inference API / Inference Endpoints / Spaces.

It does not expose HF tokens and does not pretend live inference happened.
Live execution must be performed by a worker or route that validates HF_TOKEN,
rate limits calls, records latency/cost metadata, and appends ProofBook events.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any

from .deep_backend import BackendContext, append_chain_event, canonical_json, sha256_text, utc_now
from .microoverworker import build_microoverworker_plan


HF_API_BASE_DEFAULT = "https://api-inference.huggingface.co"


@dataclass(frozen=True, slots=True)
class HuggingFaceModelSpec:
    model_id: str
    task: str
    role: str
    endpoint_kind: str
    memebra_use: list[str]
    default_enabled: bool
    notes: str


HF_MODEL_REGISTRY: list[HuggingFaceModelSpec] = [
    HuggingFaceModelSpec(
        "sentence-transformers/all-MiniLM-L6-v2",
        "feature-extraction",
        "embedding_worker",
        "inference_api_or_local_transformersjs",
        ["semantic_listing_search", "databit_similarity", "sentence_memory", "duplicate_detection"],
        True,
        "Small, useful embedding model. Also compatible conceptually with Transformers.js alternatives.",
    ),
    HuggingFaceModelSpec(
        "BAAI/bge-small-en-v1.5",
        "feature-extraction",
        "embedding_worker",
        "inference_api",
        ["higher_quality_embeddings", "retrieval", "KPI_similarity"],
        True,
        "Good compact retrieval embedding model.",
    ),
    HuggingFaceModelSpec(
        "facebook/bart-large-mnli",
        "zero-shot-classification",
        "classification_worker",
        "inference_api",
        ["candidate_type_classification", "risk_tagging", "buyer_category_mapping"],
        True,
        "Useful for labels without training data.",
    ),
    HuggingFaceModelSpec(
        "google/flan-t5-base",
        "text2text-generation",
        "listing_copy_worker",
        "inference_api",
        ["listing_copy", "permission_checklist", "KPI_explanation"],
        False,
        "General text2text fallback. Prefer stronger hosted LLM when configured.",
    ),
    HuggingFaceModelSpec(
        "Salesforce/blip-image-captioning-base",
        "image-to-text",
        "vision_caption_worker",
        "inference_api",
        ["image_caption", "photo_context", "candidate_generation_hint"],
        True,
        "Assistive captioning only; not verification.",
    ),
    HuggingFaceModelSpec(
        "openai/clip-vit-base-patch32",
        "zero-shot-image-classification",
        "vision_classification_worker",
        "inference_api",
        ["surface_type_hint", "candidate_region_hint", "listing_visual_similarity"],
        True,
        "Useful for visual similarity/classification if endpoint supports it.",
    ),
    HuggingFaceModelSpec(
        "microsoft/table-transformer-detection",
        "object-detection",
        "structure_detection_worker",
        "inference_api_or_endpoint",
        ["table_surface_detection", "layout_hinting", "visual_region_decomposition"],
        False,
        "Specialized; only enable when endpoint support is confirmed.",
    ),
    HuggingFaceModelSpec(
        "distilbert-base-uncased-finetuned-sst-2-english",
        "text-classification",
        "risk_sentiment_worker",
        "inference_api_or_transformersjs",
        ["risk_sentiment", "review_note_tone", "buyer_pitch_tone"],
        True,
        "Lightweight classification baseline.",
    ),
]


def hf_config_status() -> dict[str, Any]:
    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_API_TOKEN")
    base = os.getenv("HF_API_BASE", HF_API_BASE_DEFAULT)
    return {
        "provider": "huggingface",
        "configured": bool(token),
        "token_value_exposed": False,
        "api_base": base,
        "spaces_token_configured": bool(os.getenv("HF_TOKEN")),
        "endpoint_url_configured": bool(os.getenv("HF_ENDPOINT_URL")),
        "default_timeout_seconds": int(os.getenv("HF_TIMEOUT_SECONDS", "45")),
        "safety": {
            "no_fake_inference_claims": True,
            "worker_execution_required_for_live_calls": True,
            "assistive_outputs_require_review": True,
        },
    }


def hf_model_catalog() -> dict[str, Any]:
    models = [asdict(model) for model in HF_MODEL_REGISTRY]
    return {
        "provider": "huggingface",
        "models": models,
        "enabled_defaults": [m for m in models if m["default_enabled"]],
        "task_groups": sorted({m.task for m in HF_MODEL_REGISTRY}),
        "configured": hf_config_status()["configured"],
    }


def model_by_id(model_id: str) -> dict[str, Any] | None:
    for model in HF_MODEL_REGISTRY:
        if model.model_id == model_id:
            return asdict(model)
    return None


def build_hf_inference_plan(*, model_id: str, inputs: Any, parameters: dict[str, Any] | None = None, listing: dict[str, Any] | None = None, purpose: str = "membra_hf_inference") -> dict[str, Any]:
    model = model_by_id(model_id)
    if not model:
        raise ValueError(f"unknown Hugging Face model_id: {model_id}")
    listing = listing or {}
    parameters = parameters or {}
    seed = {
        "model_id": model_id,
        "task": model["task"],
        "inputs_hash": sha256_text(str(inputs))[:24],
        "parameters": parameters,
        "listing": listing,
        "purpose": purpose,
        "created_at": utc_now(),
    }
    return {
        "hf_plan_id": "hfplan_" + sha256_text(canonical_json(seed))[:24],
        "created_at": seed["created_at"],
        "provider": "huggingface",
        "model": model,
        "purpose": purpose,
        "inputs_preview": str(inputs)[:500],
        "inputs_hash": seed["inputs_hash"],
        "parameters": parameters,
        "listing_context": listing,
        "configured": hf_config_status()["configured"],
        "execution_mode": "live_worker_required_if_configured_else_plan_only",
        "microoverworker_plan": build_microoverworker_plan(listing=listing) if listing else None,
        "review_required": True,
        "caveats": [
            "This plan does not prove live Hugging Face inference executed.",
            "Model output is assistive until reviewed.",
            "Deterministic KPI values must not be overwritten by model text.",
        ],
    }


def build_hf_bundle_for_listing(listing: dict[str, Any]) -> dict[str, Any]:
    title = listing.get("title") or listing.get("detected_name") or "MEMBRA listing"
    description = listing.get("description") or listing.get("full_description") or "Local-commerce inventory candidate."
    candidate_labels = [
        "wall surface",
        "window surface",
        "table surface",
        "shelf space",
        "door signage",
        "vehicle surface",
        "wearable item",
        "QR/NFC placement zone",
        "community board",
        "storefront zone",
    ]
    return {
        "bundle_id": "hfb_" + sha256_text(canonical_json({"listing": listing, "created_at": utc_now()}))[:24],
        "provider": "huggingface",
        "listing_context": listing,
        "plans": [
            build_hf_inference_plan(
                model_id="sentence-transformers/all-MiniLM-L6-v2",
                inputs=f"{title}\n{description}",
                listing=listing,
                purpose="semantic_listing_embedding",
            ),
            build_hf_inference_plan(
                model_id="facebook/bart-large-mnli",
                inputs={"text": f"{title}\n{description}", "candidate_labels": candidate_labels},
                parameters={"multi_label": True},
                listing=listing,
                purpose="candidate_type_classification",
            ),
            build_hf_inference_plan(
                model_id="distilbert-base-uncased-finetuned-sst-2-english",
                inputs=f"{title}\n{description}",
                listing=listing,
                purpose="review_tone_risk_signal",
            ),
        ],
        "recommended_next": [
            "Run embedding plan for semantic memory.",
            "Run zero-shot classification for candidate type hints.",
            "Run risk/tone classifier for admin review signals.",
            "Record outputs as KPI observations and ProofBook events.",
        ],
        "configured": hf_config_status()["configured"],
    }


def record_hf_plan(conn, context: BackendContext, plan: dict[str, Any]) -> dict[str, Any]:
    return append_chain_event(
        conn,
        context,
        "huggingface_plan",
        plan["hf_plan_id"],
        "huggingface.inference_plan_created",
        plan,
    )


def record_hf_bundle(conn, context: BackendContext, bundle: dict[str, Any]) -> dict[str, Any]:
    return append_chain_event(
        conn,
        context,
        "huggingface_bundle",
        bundle["bundle_id"],
        "huggingface.bundle_created",
        bundle,
    )


def create_hf_inference_plan(conn, *, context: BackendContext, model_id: str, inputs: Any, parameters: dict[str, Any] | None = None, listing: dict[str, Any] | None = None, purpose: str = "membra_hf_inference") -> dict[str, Any]:
    plan = build_hf_inference_plan(model_id=model_id, inputs=inputs, parameters=parameters, listing=listing, purpose=purpose)
    event = record_hf_plan(conn, context, plan)
    return {"success": True, "huggingface_plan": plan, "proofbook_event": event}


def create_hf_bundle_for_listing(conn, *, context: BackendContext, listing: dict[str, Any]) -> dict[str, Any]:
    bundle = build_hf_bundle_for_listing(listing)
    event = record_hf_bundle(conn, context, bundle)
    return {"success": True, "huggingface_bundle": bundle, "proofbook_event": event}
