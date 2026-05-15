"""FastAPI router for MEMBRA KPI productized backend layers."""
from __future__ import annotations

import sqlite3
from typing import Any, Callable

from fastapi import APIRouter, Header, HTTPException

from .deep_backend import BackendContext
from .free_product_integrations import create_free_product_integration_plan, product_catalog, recommended_stack
from .huggingface_endpoints import create_hf_bundle_for_listing, create_hf_inference_plan, hf_config_status, hf_model_catalog
from .info_gauntlets import create_info_gauntlet_service, list_info_bits
from .language_fi import language_fi_status, localize_listing_stub
from .microoverworker import create_microoverworker_product_bundle, microoverworker_status
from .partner_endpoints import create_partner_endpoint_plan, partner_by_id, partner_catalog
from .provider_api import get_all_provider_status, get_google_status, get_iot_status, get_provider_requirements, get_web3_status
from .public_source_expansion import create_public_source_enrichment_plan, public_source_expansion_report, sources_by_category, top_public_sources
from .sentence_as_service import create_sentence_as_service
from .tranche_infra import build_entitlement_record, create_tranche_intent, record_entitlement, tranche_catalog
from .value_api_bundle import bundle_definitions, high_density_providers, value_density_report


def build_product_router(db_factory: Callable[[], sqlite3.Connection]) -> APIRouter:
    router = APIRouter(prefix="/api/product", tags=["membra-product"])

    def context(payload: dict[str, Any] | None = None) -> BackendContext:
        payload = payload or {}
        return BackendContext(
            tenant_id=str(payload.get("tenant_id", "tenant_default")),
            actor_id=str(payload.get("actor_id", "product-api")),
            role=str(payload.get("role", "system")),
        )

    @router.get("/providers")
    def providers(): return get_all_provider_status()
    @router.get("/providers/requirements")
    def provider_requirements(): return get_provider_requirements()
    @router.get("/providers/web3")
    def providers_web3(): return get_web3_status()
    @router.get("/providers/iot")
    def providers_iot(): return get_iot_status()
    @router.get("/providers/google")
    def providers_google(): return get_google_status()
    @router.get("/huggingface/status")
    def huggingface_status(): return hf_config_status()
    @router.get("/huggingface/models")
    def huggingface_models(): return hf_model_catalog()
    @router.post("/huggingface/plan")
    def huggingface_plan(payload: dict[str, Any]):
        with db_factory() as conn:
            return create_hf_inference_plan(conn, context=context(payload), model_id=payload["model_id"], inputs=payload.get("inputs", ""), parameters=payload.get("parameters", {}), listing=payload.get("listing", {}), purpose=payload.get("purpose", "membra_hf_inference"))
    @router.post("/huggingface/listing-bundle")
    def huggingface_listing_bundle(payload: dict[str, Any]):
        with db_factory() as conn:
            return create_hf_bundle_for_listing(conn, context=context(payload), listing=payload.get("listing", {}))

    @router.get("/data/value-density")
    def data_value_density(): return value_density_report()
    @router.get("/data/high-density")
    def data_high_density(): return {"providers": high_density_providers()}
    @router.get("/data/bundles")
    def data_bundles(): return {"bundles": bundle_definitions()}
    @router.get("/public-sources")
    def public_sources(): return public_source_expansion_report()
    @router.get("/public-sources/categories")
    def public_sources_categories(): return sources_by_category()
    @router.get("/public-sources/top")
    def public_sources_top(): return {"sources": top_public_sources()}
    @router.post("/public-sources/enrichment-plan")
    def public_sources_plan(payload: dict[str, Any]):
        with db_factory() as conn:
            return create_public_source_enrichment_plan(conn, context=context(payload), listing=payload.get("listing", {}), bundle_id=payload.get("bundle_id", "all_public_local_underwriting"))

    @router.get("/free-products")
    def free_products(): return product_catalog()
    @router.get("/free-products/recommended-stack")
    def free_products_stack(): return recommended_stack()
    @router.post("/free-products/plan")
    def free_products_plan(payload: dict[str, Any]):
        with db_factory() as conn:
            return create_free_product_integration_plan(conn, context=context(payload), listing=payload.get("listing", {}), objective=payload.get("objective", "upgrade MEMBRA backend into a 10x free-tier product stack"))

    @router.get("/partners")
    def partners(): return partner_catalog()
    @router.get("/partners/{partner_id}")
    def partner_detail(partner_id: str):
        partner = partner_by_id(partner_id)
        if not partner: raise HTTPException(404, "Partner not found")
        return partner
    @router.post("/partners/plan")
    def partners_plan(payload: dict[str, Any]):
        with db_factory() as conn:
            return create_partner_endpoint_plan(conn, context=context(payload), partner_id=payload["partner_id"], operation=payload["operation"], listing=payload.get("listing", {}), payload=payload.get("payload", {}))

    @router.get("/microoverworker/status")
    def microoverworker(): return microoverworker_status()
    @router.post("/microoverworker/bundle")
    def microoverworker_bundle(payload: dict[str, Any]):
        with db_factory() as conn:
            return create_microoverworker_product_bundle(conn, context=context(payload), listing=payload.get("listing", {}), wallet_payloads=payload.get("wallets", []), kpis=payload.get("kpis", []), objective=payload.get("objective"))

    @router.get("/language-fi/status")
    def language_fi(): return language_fi_status()
    @router.post("/language-fi/localize")
    def language_fi_localize(payload: dict[str, Any]): return localize_listing_stub(payload.get("listing", {}), locale=payload.get("locale", "fi"))
    @router.get("/tranches")
    def tranches(): return tranche_catalog()
    @router.post("/tranches/intent")
    def tranches_intent(payload: dict[str, Any]):
        with db_factory() as conn:
            return create_tranche_intent(conn, context=context(payload), tranche_id=payload["tranche_id"], buyer_id=payload.get("buyer_id", "buyer_default"), wallet_payload=payload.get("wallet"), requested_locale=payload.get("locale", "en"), notes=payload.get("notes", ""))
    @router.post("/tranches/approve")
    def tranches_approve(payload: dict[str, Any], x_admin_token: str | None = Header(default=None)):
        if payload.get("require_admin_token") and not x_admin_token: raise HTTPException(401, "Admin token required by request policy")
        with db_factory() as conn:
            ctx = context(payload); entitlement = build_entitlement_record(payload["intent"], approved_by=payload.get("approved_by", ctx.actor_id)); event = record_entitlement(conn, ctx, entitlement); return {"success": True, "entitlement": entitlement, "proofbook_event": event}
    @router.post("/sentence-as-service/create")
    def sentence_create(payload: dict[str, Any]):
        with db_factory() as conn:
            return create_sentence_as_service(conn, context=context(payload), listing=payload.get("listing", {}), tranche_id=payload.get("tranche_id", "lf_operator"), buyer_id=payload.get("buyer_id", "buyer_default"), wallet_payloads=payload.get("wallets", []), locale=payload.get("locale", "en"))
    @router.get("/info-bits")
    def info_bits(): return {"info_bits": list_info_bits()}
    @router.post("/info-gauntlets/create")
    def info_gauntlets_create(payload: dict[str, Any]):
        with db_factory() as conn:
            return create_info_gauntlet_service(conn, context=context(payload), listing=payload.get("listing", {}), categories=payload.get("categories"), locale=payload.get("locale", "en"), objective=payload.get("objective", "package a high-density MEMBRA info gauntlet"))
    return router
