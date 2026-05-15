"""LLM Employee Bundle for MEMBRA KPI.

This module bundles API providers, token configuration metadata, and LLM-worker
roles into one auditable backend registry.

It never stores raw tokens. It only checks whether required environment
variables are configured and creates safe execution plans that app routes or
workers can run behind explicit provider adapters.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any

from .deep_backend import BackendContext, append_chain_event, canonical_json, sha256_text, utc_now
from .value_api_bundle import bundle_definitions, listing_enrichment_plan, value_density_report


@dataclass(frozen=True, slots=True)
class TokenSlot:
    slot_id: str
    env_var: str
    provider: str
    purpose: str
    required_for: list[str]
    secret: bool = True


@dataclass(frozen=True, slots=True)
class LLMProvider:
    provider_id: str
    name: str
    env_key: str
    default_model: str
    model_env: str
    endpoint_env: str | None
    strengths: list[str]
    best_employee_roles: list[str]


@dataclass(frozen=True, slots=True)
class LLMEmployeeRole:
    role_id: str
    name: str
    mission: str
    allowed_tools: list[str]
    forbidden_actions: list[str]
    output_schema: dict[str, str]


TOKEN_SLOTS: list[TokenSlot] = [
    TokenSlot("groq_api_key", "GROQ_API_KEY", "groq", "Fast LLM reasoning, listing copy, KPI explanation and research worker tasks", ["concierge", "listing_writer", "research_analyst", "investor_memo"]),
    TokenSlot("openai_api_key", "OPENAI_API_KEY", "openai", "Optional general LLM and vision provider", ["vision_review", "listing_writer", "admin_reviewer"]),
    TokenSlot("google_maps_key", "GOOGLE_MAPS_API_KEY", "google_maps", "Maps, geocoding and place context", ["map_context_worker", "buyer_discovery"]),
    TokenSlot("google_places_key", "GOOGLE_PLACES_API_KEY", "google_places", "Nearby business and place discovery", ["buyer_discovery", "map_context_worker"]),
    TokenSlot("google_civic_key", "GOOGLE_CIVIC_API_KEY", "google_civic", "Public civic/geographic context", ["local_context_analyst"]),
    TokenSlot("google_vision_key", "GOOGLE_CLOUD_VISION_API_KEY", "google_vision", "OCR and image label adapter", ["vision_review", "proof_quality_worker"]),
    TokenSlot("fred_key", "FRED_API_KEY", "fred", "Macro and market context", ["investor_memo", "underwriting_analyst"]),
    TokenSlot("bea_key", "BEA_API_KEY", "bea", "Regional economic context", ["investor_memo", "underwriting_analyst"]),
    TokenSlot("opencorporates_key", "OPENCORPORATES_API_KEY", "opencorporates", "Business/entity discovery", ["buyer_discovery", "entity_review"]),
    TokenSlot("iot_ingest_token", "MEMBRA_IOT_INGEST_TOKEN", "membra_iot", "IoT telemetry ingest authentication", ["iot_event_worker"]),
]

LLM_PROVIDERS: list[LLMProvider] = [
    LLMProvider("groq", "Groq", "GROQ_API_KEY", "llama-3.3-70b-versatile", "GROQ_MODEL", "GROQ_BASE_URL", ["speed", "agent routing", "listing copy", "structured reasoning"], ["concierge", "listing_writer", "research_analyst", "investor_memo"]),
    LLMProvider("openai", "OpenAI", "OPENAI_API_KEY", "gpt-4o-mini", "OPENAI_MODEL", "OPENAI_BASE_URL", ["general reasoning", "vision-capable workflows", "structured outputs"], ["vision_review", "admin_reviewer", "listing_writer"]),
    LLMProvider("ollama", "Ollama", "OLLAMA_BASE_URL", "llama3.1", "OLLAMA_MODEL", "OLLAMA_BASE_URL", ["local fallback", "private local inference", "offline development"], ["concierge", "listing_writer", "research_analyst"]),
    LLMProvider("deterministic", "Deterministic Fallback", "", "rules", "", None, ["always available", "auditable", "no hallucinated provider claims"], ["all_roles_fallback"]),
]

LLM_EMPLOYEES: list[LLMEmployeeRole] = [
    LLMEmployeeRole(
        "concierge",
        "MEMBRA Concierge",
        "Answer user questions from stored listings, KPI cards, ProofBook events and provider status.",
        ["read_listings", "read_kpis", "read_proofbook", "read_provider_status"],
        ["guarantee_income", "claim_payout_sent", "sign_transactions"],
        {"answer": "string", "record_refs": "array", "confidence": "string"},
    ),
    LLMEmployeeRole(
        "listing_writer",
        "Listing Writer",
        "Generate differentiated listing copy, permission checklists and buyer-facing descriptions.",
        ["read_asset_context", "read_map_context", "read_kpi_scores"],
        ["invent_ownership", "guarantee_revenue", "publish_without_review"],
        {"title": "string", "description": "string", "buyer_categories": "array", "review_required": "boolean"},
    ),
    LLMEmployeeRole(
        "buyer_discovery",
        "Buyer Discovery Analyst",
        "Combine map, company, POI and local context into pitch targets and buyer categories.",
        ["osm_overpass", "google_places", "opencorporates", "wikidata"],
        ["spam_contacts", "scrape_private_data", "bypass_rate_limits"],
        {"buyer_categories": "array", "pitch_targets": "array", "source_notes": "array"},
    ),
    LLMEmployeeRole(
        "underwriting_analyst",
        "Underwriting Analyst",
        "Score listing monetization, location density, risk, proof quality and local demand.",
        ["census", "data_commons", "fred", "bea", "noaa", "kpi_observations"],
        ["guarantee_income", "ignore_risk_flags", "override_deterministic_scores"],
        {"score_explanation": "string", "risk_notes": "array", "data_sources": "array"},
    ),
    LLMEmployeeRole(
        "proof_reviewer",
        "ProofBook Reviewer",
        "Review proof event chains, evidence quality and listing readiness for admin workflows.",
        ["read_proofbook", "verify_chain", "read_object_registry"],
        ["delete_proof_events", "mark_fake_verification", "claim_certification"],
        {"integrity_status": "string", "review_notes": "array", "next_actions": "array"},
    ),
    LLMEmployeeRole(
        "investor_memo",
        "Investor Memo Analyst",
        "Create investor-room summaries from verified KPI, provider and operational data.",
        ["read_dashboard", "read_provider_status", "fred", "bea", "openalex", "sec_edgar"],
        ["invent_revenue", "misstate_users", "omit_caveats"],
        {"memo": "string", "caveats": "array", "data_sources": "array"},
    ),
]


def configured(env_var: str) -> bool:
    if not env_var:
        return True
    return bool(os.getenv(env_var))


def token_status() -> dict[str, Any]:
    slots = []
    for slot in TOKEN_SLOTS:
        slots.append({
            **asdict(slot),
            "configured": configured(slot.env_var),
            "value_exposed": False,
        })
    return {
        "token_slots": slots,
        "configured_count": sum(1 for slot in slots if slot["configured"]),
        "total_count": len(slots),
        "secret_policy": {
            "raw_tokens_returned": False,
            "environment_only": True,
            "rotate_via_host_secrets": True,
        },
    }


def llm_provider_status() -> dict[str, Any]:
    providers = []
    for provider in LLM_PROVIDERS:
        is_configured = provider.provider_id == "deterministic" or configured(provider.env_key)
        providers.append({
            **asdict(provider),
            "configured": is_configured,
            "active_model": os.getenv(provider.model_env, provider.default_model) if provider.model_env else provider.default_model,
        })
    return {
        "providers": providers,
        "active_preference": os.getenv("LLM_PROVIDER", "auto"),
        "fallback_order": ["groq", "openai", "ollama", "deterministic"],
    }


def employee_registry() -> dict[str, Any]:
    return {
        "employees": [asdict(role) for role in LLM_EMPLOYEES],
        "count": len(LLM_EMPLOYEES),
        "global_rules": [
            "Do not guarantee income.",
            "Do not claim payout execution.",
            "Do not sign blockchain transactions.",
            "Do not claim live provider execution unless provider adapter confirms it.",
            "Always preserve auditability through ProofBook events for material actions.",
        ],
    }


def llm_employee_bundle_status() -> dict[str, Any]:
    return {
        "name": "MEMBRA LLM Employee Bundle",
        "tokens": token_status(),
        "llm_providers": llm_provider_status(),
        "employees": employee_registry(),
        "data_bundles": value_density_report()["bundles"],
    }


def build_employee_task(employee_role: str, objective: str, listing: dict[str, Any] | None = None) -> dict[str, Any]:
    role = next((r for r in LLM_EMPLOYEES if r.role_id == employee_role), None)
    if not role:
        raise ValueError(f"Unknown LLM employee role: {employee_role}")
    listing = listing or {}
    plan = listing_enrichment_plan(listing) if listing else {}
    task = {
        "task_id": sha256_text(employee_role + "|" + objective + "|" + canonical_json(listing))[:24],
        "employee_role": asdict(role),
        "objective": objective,
        "listing_context": listing,
        "recommended_data_plan": plan,
        "created_at": utc_now(),
        "execution_mode": "plan_only_until_worker_adapter_runs",
        "review_required": True,
    }
    return task


def record_employee_task(conn, context: BackendContext, task: dict[str, Any]) -> dict[str, Any]:
    return append_chain_event(
        conn,
        context,
        "llm_employee_task",
        task["task_id"],
        "llm_employee.task_planned",
        task,
    )
