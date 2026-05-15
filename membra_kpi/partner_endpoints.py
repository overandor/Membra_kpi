"""Live partner endpoint registry for MEMBRA KPI.

This module packages partner endpoints into auditable backend metadata. It does
not expose raw partner tokens and does not execute unsafe actions. Live calls
must be implemented by provider-specific workers that consume these endpoint
plans behind rate limits, auth, and ProofBook auditing.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any

from .deep_backend import BackendContext, append_chain_event, canonical_json, sha256_text, utc_now
from .microoverworker import build_microoverworker_plan


@dataclass(frozen=True, slots=True)
class PartnerEndpoint:
    partner_id: str
    name: str
    category: str
    base_url_env: str
    token_env: str
    auth_mode: str
    endpoint_family: str
    allowed_operations: list[str]
    data_products: list[str]
    live_ready_when_configured: bool
    safety_notes: str


PARTNER_ENDPOINTS: list[PartnerEndpoint] = [
    PartnerEndpoint(
        "google_places_partner",
        "Google Places Partner",
        "maps_and_nearby_business",
        "GOOGLE_PLACES_BASE_URL",
        "GOOGLE_PLACES_API_KEY",
        "api_key",
        "places_nearby_search",
        ["nearby_search", "place_details", "business_category_context"],
        ["nearby_business_types", "recommended_buyer_categories", "pitch_targets"],
        True,
        "Official API key required. Do not call from frontend with unrestricted keys.",
    ),
    PartnerEndpoint(
        "google_vision_partner",
        "Google Vision Partner",
        "vision_ocr",
        "GOOGLE_VISION_BASE_URL",
        "GOOGLE_CLOUD_VISION_API_KEY",
        "api_key_or_service_account",
        "image_annotate",
        ["ocr", "label_detection", "text_detection"],
        ["proof_text", "image_labels", "surface_context"],
        True,
        "Image analysis is assistive and requires review before listing activation.",
    ),
    PartnerEndpoint(
        "groq_partner",
        "Groq LLM Partner",
        "llm",
        "GROQ_BASE_URL",
        "GROQ_API_KEY",
        "bearer_token",
        "chat_completions",
        ["listing_copy", "kpi_explanation", "investor_memo", "worker_reasoning"],
        ["sentences", "listing_descriptions", "worker_reports"],
        True,
        "Never claim LLM output as verified fact without deterministic/backend support.",
    ),
    PartnerEndpoint(
        "openai_partner",
        "OpenAI Partner",
        "llm_vision",
        "OPENAI_BASE_URL",
        "OPENAI_API_KEY",
        "bearer_token",
        "responses_or_chat_completions",
        ["listing_copy", "vision_review", "admin_summary"],
        ["vision_notes", "listing_copy", "review_summaries"],
        True,
        "Optional provider. Raw API key must stay server-side.",
    ),
    PartnerEndpoint(
        "opencorporates_partner",
        "OpenCorporates Partner",
        "company_registry",
        "OPENCORPORATES_BASE_URL",
        "OPENCORPORATES_API_KEY",
        "api_key",
        "company_search",
        ["company_search", "company_profile", "buyer_verification"],
        ["entity_context", "buyer_candidates", "company_confidence"],
        True,
        "Respect provider terms and rate limits. Entity matches require human review.",
    ),
    PartnerEndpoint(
        "stripe_partner",
        "Stripe Partner",
        "billing",
        "STRIPE_BASE_URL",
        "STRIPE_SECRET_KEY",
        "bearer_token",
        "checkout_and_webhooks",
        ["checkout_session", "webhook_verify", "billing_event_reconcile"],
        ["billing_status", "entitlement_payment_context"],
        True,
        "Billing status must not imply payout execution or investment return.",
    ),
    PartnerEndpoint(
        "solana_devnet_partner",
        "Solana Devnet Partner",
        "web3_devnet_anchor",
        "MEMBRA_SOLANA_DEVNET_RPC_URL",
        "MEMBRA_SOLANA_DEVNET_KEYPAIR",
        "local_devnet_keypair_reference",
        "devnet_memo_anchor",
        ["anchor_listing_metadata", "anchor_entitlement_metadata", "verify_devnet_signature"],
        ["anchor_hash", "devnet_signature", "proofbook_link"],
        True,
        "Devnet only. No mainnet signing, no fund movement, no custody.",
    ),
    PartnerEndpoint(
        "iot_device_partner",
        "MEMBRA IoT Device Partner",
        "iot_ingest",
        "MEMBRA_IOT_BASE_URL",
        "MEMBRA_IOT_INGEST_TOKEN",
        "shared_ingest_token_or_hmac",
        "iot_events",
        ["qr_scan", "nfc_tap", "beacon_seen", "device_heartbeat", "proof_capture"],
        ["proof_events", "presence_signals", "scan_metrics"],
        True,
        "Reject public ingest unless token or HMAC verification is configured.",
    ),
]


def _configured(env_var: str) -> bool:
    if not env_var:
        return True
    return bool(os.getenv(env_var))


def partner_catalog() -> dict[str, Any]:
    partners = []
    for partner in PARTNER_ENDPOINTS:
        item = asdict(partner)
        item["base_url_configured"] = _configured(partner.base_url_env)
        item["token_configured"] = _configured(partner.token_env)
        item["live_configured"] = item["token_configured"] and partner.live_ready_when_configured
        item["token_value_exposed"] = False
        partners.append(item)
    return {
        "product": "MEMBRA Partner Endpoint Bundle",
        "partners": partners,
        "counts": {
            "total": len(partners),
            "live_configured": sum(1 for p in partners if p["live_configured"]),
        },
        "safety": {
            "tokens_not_returned": True,
            "server_side_only": True,
            "proofbook_required_for_material_actions": True,
            "rate_limits_required_for_live_workers": True,
        },
    }


def partner_by_id(partner_id: str) -> dict[str, Any] | None:
    for partner in partner_catalog()["partners"]:
        if partner["partner_id"] == partner_id:
            return partner
    return None


def build_partner_endpoint_plan(*, partner_id: str, operation: str, listing: dict[str, Any] | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    partner = partner_by_id(partner_id)
    if not partner:
        raise ValueError(f"unknown partner_id: {partner_id}")
    if operation not in partner["allowed_operations"]:
        raise ValueError(f"operation {operation!r} is not allowed for partner {partner_id!r}")
    listing = listing or {}
    payload = payload or {}
    seed = {
        "partner_id": partner_id,
        "operation": operation,
        "listing": listing,
        "payload": payload,
        "created_at": utc_now(),
    }
    return {
        "partner_plan_id": "pep_" + sha256_text(canonical_json(seed))[:24],
        "created_at": seed["created_at"],
        "partner": partner,
        "operation": operation,
        "listing_context": listing,
        "payload": payload,
        "microoverworker_plan": build_microoverworker_plan(listing=listing) if listing else None,
        "execution_mode": "live_worker_ready_if_configured_else_plan_only",
        "live_configured": partner["live_configured"],
        "review_required": True,
    }


def record_partner_endpoint_plan(conn, context: BackendContext, plan: dict[str, Any]) -> dict[str, Any]:
    return append_chain_event(
        conn,
        context,
        "partner_endpoint_plan",
        plan["partner_plan_id"],
        "partner.endpoint_plan_created",
        plan,
    )


def create_partner_endpoint_plan(conn, *, context: BackendContext, partner_id: str, operation: str, listing: dict[str, Any] | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    plan = build_partner_endpoint_plan(partner_id=partner_id, operation=operation, listing=listing, payload=payload)
    event = record_partner_endpoint_plan(conn, context, plan)
    return {"success": True, "partner_endpoint_plan": plan, "proofbook_event": event}
