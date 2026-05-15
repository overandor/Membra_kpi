"""Gauntlets of Info Bits as a Service for MEMBRA KPI.

An Info Gauntlet is a dense, audit-ready packet of high-value information bits
assembled from public sources, partner endpoints, KPIs, wallet references,
repos, LLM employees, language-fi, MicroOverWorker, and ProofBook metadata.

The goal is to compress many low-cost/free data sources into a high-density
commercial artifact that can be sold as a service without pretending that
unconfigured providers have executed live calls.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .deep_backend import BackendContext, append_chain_event, canonical_json, sha256_text, utc_now
from .free_product_integrations import recommended_stack
from .llm_employee_bundle import build_employee_task
from .microoverworker import build_microoverworker_plan
from .partner_endpoints import partner_catalog
from .public_source_expansion import public_source_bundles, public_source_expansion_report
from .sentence_as_service import build_sentence_product
from .value_api_bundle import value_density_report


@dataclass(frozen=True, slots=True)
class InfoBit:
    bit_id: str
    label: str
    category: str
    claim: str
    source_family: str
    value_density: int
    confidence: str
    review_required: bool


INFO_BIT_TEMPLATES: list[InfoBit] = [
    InfoBit("nearby_business_density", "Nearby Business Density", "buyer_discovery", "The listing can be enriched with nearby business categories and pitch targets.", "OSM/Overture/Google Places", 96, "source-dependent", True),
    InfoBit("neighborhood_income_context", "Neighborhood Income Context", "underwriting", "The listing can receive demographic and income-context scoring.", "Census/ACS/Data Commons", 94, "source-dependent", True),
    InfoBit("proof_chain_integrity", "Proof Chain Integrity", "proof", "Material actions can be recorded in a hash-chained ProofBook ledger.", "MEMBRA ProofBook", 93, "deterministic", False),
    InfoBit("language_fi_localization", "Language-Fi Localization", "localization", "The listing can be packaged into multilingual review-ready commercial copy.", "language-fi", 88, "template-or-provider-dependent", True),
    InfoBit("wallet_reference_binding", "Wallet Reference Binding", "wallet", "Non-custodial wallet references can be attached as entitlement or payout-eligibility metadata.", "MicroOverWorker wallet binding", 82, "deterministic", True),
    InfoBit("economic_macro_context", "Economic Macro Context", "investor_room", "Macro and regional economic data can strengthen investor-room narratives.", "FRED/BEA/BLS", 86, "source-dependent", True),
    InfoBit("compliance_risk_scan", "Compliance Risk Scan", "risk", "Public sanctions and entity-risk sources can trigger admin review workflows.", "OpenSanctions/OFAC/OpenOwnership", 91, "match-review-required", True),
    InfoBit("weather_activation_timing", "Weather Activation Timing", "activation", "Weather and seasonality can influence campaign timing and proof capture.", "NOAA/Open-Meteo", 80, "source-dependent", True),
    InfoBit("research_moat_context", "Research Moat Context", "research", "Research, patent and software graphs can support defensibility narratives.", "OpenAlex/Crossref/USPTO/GitHub", 78, "source-dependent", True),
    InfoBit("devnet_anchor_metadata", "Devnet Anchor Metadata", "web3", "Listing and entitlement metadata can be anchored to Solana devnet in dry-run or configured devnet mode.", "Solana devnet adapter", 74, "devnet-only", True),
]


def list_info_bits() -> list[dict[str, Any]]:
    return [asdict(bit) for bit in INFO_BIT_TEMPLATES]


def select_info_bits(categories: list[str] | None = None, min_value_density: int = 75) -> list[dict[str, Any]]:
    selected = []
    for bit in INFO_BIT_TEMPLATES:
        if bit.value_density < min_value_density:
            continue
        if categories and bit.category not in categories:
            continue
        selected.append(asdict(bit))
    return sorted(selected, key=lambda x: x["value_density"], reverse=True)


def calculate_gauntlet_score(bits: list[dict[str, Any]]) -> dict[str, Any]:
    if not bits:
        return {"score": 0, "grade": "F", "bit_count": 0}
    score = round(sum(int(bit["value_density"]) for bit in bits) / len(bits), 2)
    if score >= 94:
        grade = "A+"
    elif score >= 90:
        grade = "A"
    elif score >= 85:
        grade = "B+"
    elif score >= 80:
        grade = "B"
    elif score >= 75:
        grade = "C+"
    elif score >= 70:
        grade = "C"
    else:
        grade = "D"
    return {"score": score, "grade": grade, "bit_count": len(bits)}


def build_info_gauntlet(*, listing: dict[str, Any] | None = None, categories: list[str] | None = None, locale: str = "en", objective: str = "package a high-density MEMBRA info gauntlet") -> dict[str, Any]:
    listing = listing or {"title": "MEMBRA local-commerce infrastructure packet", "description": "High-density public data, provider, KPI and ProofBook package."}
    bits = select_info_bits(categories=categories)
    score = calculate_gauntlet_score(bits)
    micro_plan = build_microoverworker_plan(listing=listing, objective=objective)
    sentence = build_sentence_product(listing=listing, locale=locale)
    tasks = [
        build_employee_task("underwriting_analyst", "Turn selected info bits into underwriting rationale.", listing=listing),
        build_employee_task("buyer_discovery", "Turn selected info bits into buyer discovery actions.", listing=listing),
        build_employee_task("proof_reviewer", "Review proof and evidence requirements for selected info bits.", listing=listing),
    ]
    seed = {"listing": listing, "categories": categories or [], "locale": locale, "objective": objective, "score": score}
    return {
        "gauntlet_id": "gnt_" + sha256_text(canonical_json(seed))[:24],
        "created_at": utc_now(),
        "product": "Gauntlets of Info Bits as a Service",
        "objective": objective,
        "listing_context": listing,
        "selected_bits": bits,
        "gauntlet_score": score,
        "commercial_sentence": sentence,
        "microoverworker_plan": micro_plan,
        "llm_employee_tasks": tasks,
        "recommended_free_stack": recommended_stack(),
        "partner_catalog": partner_catalog(),
        "public_source_bundles": public_source_bundles(),
        "value_density_bundle": value_density_report()["recommended_first_bundle"],
        "public_source_summary": {
            "source_count": public_source_expansion_report()["source_count"],
            "top_source_count": len(public_source_expansion_report()["top_sources"]),
        },
        "execution_mode": "packet_ready_worker_execution_required_for_live_fetch",
        "review_required": True,
        "caveats": [
            "Information bits are enrichment signals, not guarantees.",
            "Provider execution must be configured before live source claims are made.",
            "Compliance matches require human review.",
            "Wallet references are non-custodial metadata only.",
        ],
    }


def record_info_gauntlet(conn, context: BackendContext, gauntlet: dict[str, Any]) -> dict[str, Any]:
    return append_chain_event(
        conn,
        context,
        "info_gauntlet",
        gauntlet["gauntlet_id"],
        "info_gauntlet.created",
        gauntlet,
    )


def create_info_gauntlet_service(conn, *, context: BackendContext, listing: dict[str, Any] | None = None, categories: list[str] | None = None, locale: str = "en", objective: str = "package a high-density MEMBRA info gauntlet") -> dict[str, Any]:
    gauntlet = build_info_gauntlet(listing=listing, categories=categories, locale=locale, objective=objective)
    event = record_info_gauntlet(conn, context, gauntlet)
    return {"success": True, "info_gauntlet": gauntlet, "proofbook_event": event}
