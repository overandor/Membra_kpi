"""Known free/free-tier product integrations for MEMBRA KPI.

This catalog connects MEMBRA Partner Endpoints, MicroOverWorker, Language-Fi,
Sentence-as-a-Service, and data-density bundles to practical free or generous
free-tier products that can be used to ship a real backend without pretending
unconfigured providers are live.

No external calls are executed here. This is a live-ready integration map,
capability registry, and route-planning layer.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any

from .deep_backend import BackendContext, append_chain_event, canonical_json, sha256_text, utc_now
from .partner_endpoints import partner_catalog
from .value_api_bundle import value_density_report


@dataclass(frozen=True, slots=True)
class FreeProductIntegration:
    product_id: str
    name: str
    category: str
    free_model: str
    token_envs: list[str]
    endpoint_family: str
    memebra_capability: list[str]
    best_microoverworker_role: str
    production_notes: str
    setup_priority: int


FREE_PRODUCTS: list[FreeProductIntegration] = [
    FreeProductIntegration("supabase", "Supabase", "database_auth_storage", "free_tier", ["SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY"], "postgres_auth_storage_realtime", ["auth", "tenant_db", "object_storage", "realtime_review"], "backend_operator", "Good first production backend: auth, Postgres, storage, edge functions. Keep service key server-side.", 1),
    FreeProductIntegration("neon", "Neon", "database", "free_tier", ["DATABASE_URL"], "serverless_postgres", ["tenant_db", "migrations", "kpi_queries", "proofbook_persistence"], "backend_operator", "Strong Postgres option. Pair with separate auth/storage.", 2),
    FreeProductIntegration("upstash_redis", "Upstash Redis", "queue_cache", "free_tier", ["UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN"], "redis_rest_queue_cache", ["worker_queue", "rate_limits", "provider_job_state", "chat_memory_cache"], "worker_orchestrator", "Good serverless queue/cache layer. Use for provider workers and rate limiting.", 3),
    FreeProductIntegration("cloudflare_r2", "Cloudflare R2", "object_storage", "free_allowance", ["R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"], "s3_compatible_object_storage", ["proof_images", "source_images", "exports", "investor_packets"], "proof_reviewer", "S3-compatible storage with favorable egress economics. Keep credentials server-side.", 4),
    FreeProductIntegration("netlify_blobs", "Netlify Blobs", "object_storage", "included_platform_feature", ["NETLIFY_SITE_ID", "NETLIFY_AUTH_TOKEN"], "blob_storage", ["small_exports", "runtime_snapshots", "image_metadata"], "backend_operator", "Useful for Netlify deployment artifacts and lightweight storage.", 5),
    FreeProductIntegration("huggingface_spaces", "Hugging Face Spaces", "deployment_ai_hosting", "free_tier", ["HF_TOKEN"], "spaces_runtime", ["gradio_demo", "model_demo", "operator_console"], "research_analyst", "Good public demo surface. Do not store secrets in repo.", 6),
    FreeProductIntegration("groq", "Groq", "llm", "free_or_dev_tier", ["GROQ_API_KEY"], "openai_compatible_chat", ["fast_concierge", "listing_writer", "investor_memo", "worker_reasoning"], "listing_writer", "Fast LLM provider. Outputs require deterministic validation for scores and compliance.", 7),
    FreeProductIntegration("ollama", "Ollama", "local_llm", "free_local", ["OLLAMA_BASE_URL", "OLLAMA_MODEL"], "local_generate", ["private_local_llm", "fallback_reasoning", "dev_testing"], "research_analyst", "Local model runtime. Availability depends on host environment.", 8),
    FreeProductIntegration("transformers_js", "Transformers.js", "browser_ai", "free_open_source", [], "browser_inference", ["embeddings", "semantic_search", "similarity_detection", "local_classification"], "semantic_memory_worker", "Runs in browser; excellent for local search and non-secret inference.", 9),
    FreeProductIntegration("openstreetmap_overpass", "OpenStreetMap / Overpass", "geospatial", "free_with_limits", [], "overpass_query", ["nearby_businesses", "map_context", "buyer_discovery", "foot_traffic_proxy"], "buyer_discovery", "Respect public server limits. Self-host or cache for heavier use.", 10),
    FreeProductIntegration("overture_maps", "Overture Maps", "geospatial_dataset", "open_data", [], "parquet_dataset", ["places", "buildings", "transport", "map_enrichment"], "map_context_worker", "High value but heavier data pipeline integration.", 11),
    FreeProductIntegration("nominatim", "Nominatim", "geocoding", "free_with_policy", [], "osm_geocoding", ["address_lookup", "approx_location", "map_context"], "map_context_worker", "Use respectfully; cache results and follow usage policy.", 12),
    FreeProductIntegration("leaflet", "Leaflet", "frontend_map", "free_open_source", [], "map_ui", ["map_nearby", "pin_location", "listing_map_cards"], "frontend_operator", "No paid API required when paired with OSM tiles/providers respecting policies.", 13),
    FreeProductIntegration("open_meteo", "Open-Meteo", "weather", "free", [], "forecast_api", ["weather_risk", "campaign_timing", "seasonality"], "underwriting_analyst", "Easy no-key weather integration.", 14),
    FreeProductIntegration("data_commons", "Google Data Commons", "public_stats", "free_key", ["DATA_COMMONS_API_KEY"], "public_knowledge_graph", ["city_context", "economic_context", "demographics"], "underwriting_analyst", "High-density public-stat API. Key often required.", 15),
    FreeProductIntegration("us_census", "US Census API", "demographics", "free", ["CENSUS_API_KEY"], "census_data", ["income", "housing", "population", "commute", "neighborhood_score"], "underwriting_analyst", "Excellent US neighborhood underwriting source.", 16),
    FreeProductIntegration("fred", "FRED", "economic", "free_key", ["FRED_API_KEY"], "macro_series", ["macro_context", "investor_room", "pricing_context"], "investor_memo", "Easy high-value investor context.", 17),
    FreeProductIntegration("openalex", "OpenAlex", "research", "free", [], "research_graph", ["research_moat", "prior_art", "innovation_tracking"], "research_analyst", "Useful for research-grade product narratives.", 18),
    FreeProductIntegration("wikidata", "Wikidata", "knowledge_graph", "free", [], "sparql", ["landmarks", "entity_context", "public_place_context"], "research_analyst", "Explainable public entity enrichment.", 19),
    FreeProductIntegration("sec_edgar", "SEC EDGAR", "company_financial", "free", [], "company_filings", ["company_research", "b2b_targets", "investor_room"], "buyer_discovery", "Respect SEC fair access policy and user-agent requirements.", 20),
    FreeProductIntegration("sentry", "Sentry", "observability", "free_tier", ["SENTRY_DSN"], "error_tracking", ["exceptions", "release_health", "backend_alerts"], "backend_operator", "Good first error monitoring provider.", 21),
    FreeProductIntegration("grafana_cloud", "Grafana Cloud", "observability", "free_tier", ["GRAFANA_CLOUD_TOKEN", "OTEL_EXPORTER_OTLP_ENDPOINT"], "metrics_logs_traces", ["metrics", "logs", "traces", "dashboards"], "backend_operator", "Use OpenTelemetry where possible.", 22),
    FreeProductIntegration("github_actions", "GitHub Actions", "ci_cd", "free_for_public_repos", [], "ci_cd", ["tests", "builds", "deploys", "secret_scanning"], "backend_operator", "Already natural fit for public repos.", 23),
]


def product_catalog() -> dict[str, Any]:
    products = []
    for item in FREE_PRODUCTS:
        data = asdict(item)
        data["configured"] = all(bool(os.getenv(env)) for env in item.token_envs) if item.token_envs else True
        data["tokens_exposed"] = False
        products.append(data)
    return {
        "product": "MEMBRA Free Product Integration Catalog",
        "products": sorted(products, key=lambda x: x["setup_priority"]),
        "counts": {
            "total": len(products),
            "configured": sum(1 for p in products if p["configured"]),
        },
        "safety": {
            "no_raw_tokens": True,
            "server_side_secret_policy": True,
            "unconfigured_products_are_not_reported_live": True,
        },
    }


def recommended_stack() -> dict[str, Any]:
    return {
        "stack_id": "membra_free_10x_stack",
        "name": "MEMBRA Free/Free-Tier 10x Backend Stack",
        "phase_1_core": ["supabase", "upstash_redis", "cloudflare_r2", "groq", "openstreetmap_overpass", "leaflet", "github_actions", "sentry"],
        "phase_2_intelligence": ["us_census", "data_commons", "fred", "open_meteo", "wikidata", "openalex", "sec_edgar"],
        "phase_3_research_runtime": ["transformers_js", "ollama", "overture_maps", "grafana_cloud", "huggingface_spaces"],
        "why_10x": [
            "Supabase/Neon creates real backend depth quickly.",
            "R2/Netlify Blobs gives proof-image persistence.",
            "OSM plus Census plus Data Commons turns listings into underwriting records.",
            "Groq/Ollama/Transformers.js gives cloud, local, and browser AI paths.",
            "Sentry/Grafana/GitHub Actions make the platform more production-grade than normal prototypes.",
        ],
    }


def build_free_product_integration_plan(*, listing: dict[str, Any] | None = None, objective: str = "upgrade MEMBRA backend into a 10x free-tier product stack") -> dict[str, Any]:
    listing = listing or {}
    seed = {"listing": listing, "objective": objective, "created_at": utc_now()}
    return {
        "plan_id": "fpi_" + sha256_text(canonical_json(seed))[:24],
        "created_at": seed["created_at"],
        "objective": objective,
        "recommended_stack": recommended_stack(),
        "free_product_catalog": product_catalog(),
        "partner_catalog": partner_catalog(),
        "data_density": value_density_report()["recommended_first_bundle"],
        "listing_context": listing,
        "execution_mode": "adapter_ready_plan_only_until_configured",
        "review_required": True,
    }


def record_free_product_plan(conn, context: BackendContext, plan: dict[str, Any]) -> dict[str, Any]:
    return append_chain_event(
        conn,
        context,
        "free_product_integration_plan",
        plan["plan_id"],
        "free_product.integration_plan_created",
        plan,
    )


def create_free_product_integration_plan(conn, *, context: BackendContext, listing: dict[str, Any] | None = None, objective: str = "upgrade MEMBRA backend into a 10x free-tier product stack") -> dict[str, Any]:
    plan = build_free_product_integration_plan(listing=listing, objective=objective)
    event = record_free_product_plan(conn, context, plan)
    return {"success": True, "free_product_plan": plan, "proofbook_event": event}
