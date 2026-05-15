"""Sentence-as-a-Service for MEMBRA KPI.

This module packages MicroOverWorker, language-fi, provider bundles, wallet
references, KPIs, repos, and tranche metadata into concise product sentences.

The goal is to compress backend value into sellable, auditable, localized
commercial language without making revenue, payout, security, or ownership
claims that the system cannot prove.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .deep_backend import BackendContext, append_chain_event, canonical_json, sha256_text, utc_now
from .language_fi import localize_listing_stub
from .microoverworker import build_microoverworker_plan, microoverworker_status
from .tranche_infra import build_tranche_intent, tranche_catalog
from .value_api_bundle import value_density_report


@dataclass(frozen=True, slots=True)
class SentenceProduct:
    sentence_id: str
    headline: str
    one_liner: str
    proof_sentence: str
    buyer_sentence: str
    infra_sentence: str
    caveat_sentence: str
    locale: str
    created_at: str


def sentence_templates() -> dict[str, str]:
    return {
        "headline": "MEMBRA packages local-commerce proof, language-fi infrastructure, wallet references, KPI intelligence, and provider data into auditable MicroOverWorker tranches.",
        "one_liner": "One photo or listing becomes a proof-backed, multilingual, KPI-scored commerce asset with buyer context, wallet metadata, and review-ready infrastructure access.",
        "proof_sentence": "Every material action can be recorded through ProofBook so listings, tranches, provider plans, and worker tasks remain inspectable and hash-audited.",
        "buyer_sentence": "For operators, the product turns scattered APIs, repos, wallets, maps, LLMs, and KPI records into one packaged operating sentence that can be sold, localized, reviewed, and activated.",
        "infra_sentence": "Language-fi tranches expose multilingual listing workflows, localized KPI narratives, MicroOverWorker task planning, provider bundles, and non-custodial wallet references as infrastructure entitlements.",
        "caveat_sentence": "This is software access and operational metadata, not equity, debt, profit share, guaranteed revenue, custody, or automatic payout execution.",
    }


def build_sentence_product(*, listing: dict[str, Any] | None = None, tranche_id: str = "lf_operator", buyer_id: str = "buyer_default", tenant_id: str = "tenant_default", wallet_payloads: list[dict[str, Any]] | None = None, locale: str = "en") -> dict[str, Any]:
    listing = listing or {"title": "MEMBRA infrastructure bundle", "description": "MicroOverWorker plus language-fi infrastructure access."}
    templates = sentence_templates()
    micro_plan = build_microoverworker_plan(listing=listing, wallet_payloads=wallet_payloads or [])
    tranche_intent = build_tranche_intent(
        tranche_id=tranche_id,
        buyer_id=buyer_id,
        tenant_id=tenant_id,
        wallet_payload=(wallet_payloads or [None])[0] if wallet_payloads else None,
        requested_locale=locale,
        notes="Sentence-as-a-Service packaged value intent.",
    )
    payload_seed = {
        "listing": listing,
        "tranche_id": tranche_id,
        "buyer_id": buyer_id,
        "tenant_id": tenant_id,
        "locale": locale,
        "micro_plan_id": micro_plan["plan_id"],
        "tranche_intent_id": tranche_intent["intent_id"],
    }
    product = SentenceProduct(
        sentence_id="sas_" + sha256_text(canonical_json(payload_seed))[:24],
        headline=templates["headline"],
        one_liner=templates["one_liner"],
        proof_sentence=templates["proof_sentence"],
        buyer_sentence=templates["buyer_sentence"],
        infra_sentence=templates["infra_sentence"],
        caveat_sentence=templates["caveat_sentence"],
        locale=locale,
        created_at=utc_now(),
    )
    result = asdict(product)
    if locale != "en":
        localized = localize_listing_stub({"title": product.headline, "description": product.one_liner}, locale=locale)
        result["localized"] = localized
    result["microoverworker_plan"] = micro_plan
    result["tranche_intent"] = tranche_intent
    result["bundle_context"] = {
        "microoverworker": microoverworker_status(),
        "tranches": tranche_catalog(),
        "value_density": value_density_report()["recommended_first_bundle"],
    }
    result["review_required"] = True
    return result


def record_sentence_product(conn, context: BackendContext, sentence_product: dict[str, Any]) -> dict[str, Any]:
    return append_chain_event(
        conn,
        context,
        "sentence_as_service",
        sentence_product["sentence_id"],
        "sentence_as_service.created",
        sentence_product,
    )


def create_sentence_as_service(conn, *, context: BackendContext, listing: dict[str, Any] | None = None, tranche_id: str = "lf_operator", buyer_id: str = "buyer_default", wallet_payloads: list[dict[str, Any]] | None = None, locale: str = "en") -> dict[str, Any]:
    product = build_sentence_product(
        listing=listing,
        tranche_id=tranche_id,
        buyer_id=buyer_id,
        tenant_id=context.tenant_id,
        wallet_payloads=wallet_payloads,
        locale=locale,
    )
    event = record_sentence_product(conn, context, product)
    return {"success": True, "sentence_as_service": product, "proofbook_event": event}
