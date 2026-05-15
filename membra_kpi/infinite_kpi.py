"""Infinite KPI Production for MEMBRA KPI.

This module creates a safe, resumable KPI-production engine. It is called
"infinite" because it can continually derive fresh KPI candidates from listings,
public sources, partner endpoints, MicroOverWorker bundles, Info Gauntlets,
DataBits, language-fi, and ProofBook events.

It never runs an unbounded loop inside a web request. Instead it builds bounded
production plans and worker batches with cursors, rate-limit metadata, refresh
cadence, and ProofBook audit events.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .deep_backend import BackendContext, append_chain_event, canonical_json, record_kpi_observation, sha256_text, utc_now
from .hypermodular_databits import build_hypermodular_sentence_backing
from .info_gauntlets import build_info_gauntlet, list_info_bits
from .microoverworker import build_microoverworker_plan
from .public_source_expansion import public_source_bundles, public_source_expansion_report
from .value_api_bundle import bundle_definitions, value_density_report


@dataclass(frozen=True, slots=True)
class KPIFactoryTemplate:
    template_id: str
    name: str
    category: str
    metric_unit: str
    source_family: str
    formula_hint: str
    refresh_cadence: str
    priority: int
    review_required: bool


KPI_TEMPLATES: list[KPIFactoryTemplate] = [
    KPIFactoryTemplate("kpi_visibility_density", "Visibility Density", "listing_quality", "score", "listing + image + map", "weighted visibility, surface salience, map prominence", "per_listing_update", 100, True),
    KPIFactoryTemplate("kpi_buyer_fit", "Buyer Fit", "buyer_discovery", "score", "OSM/Overture/Places", "buyer category match x nearby commerce density", "daily_or_on_context_change", 98, True),
    KPIFactoryTemplate("kpi_permission_readiness", "Permission Readiness", "compliance", "score", "listing + admin status", "permission completeness minus risk friction", "per_review_update", 97, True),
    KPIFactoryTemplate("kpi_proof_weight", "Proof Weight", "proofbook", "score", "ProofBook + objects", "proof event count, chain validity, object hashes, review status", "per_event", 99, False),
    KPIFactoryTemplate("kpi_data_density", "Data Density", "data_product", "score", "public source graph", "number and quality of bound public sources", "daily_or_bundle_change", 96, True),
    KPIFactoryTemplate("kpi_sentence_backing", "Sentence Backing", "sentence_as_service", "score", "DataBits + tranches", "density, scarcity, proof weight, tranche count", "per_sentence_packet", 95, True),
    KPIFactoryTemplate("kpi_wallet_binding_quality", "Wallet Binding Quality", "wallet_reference", "score", "wallet metadata", "non-custodial reference completeness and network validity", "per_wallet_update", 82, True),
    KPIFactoryTemplate("kpi_language_fi_readiness", "Language-Fi Readiness", "localization", "score", "language-fi", "locale support, review state, deterministic/provider mode", "per_locale_request", 84, True),
    KPIFactoryTemplate("kpi_tranche_activation_readiness", "Tranche Activation Readiness", "tranche", "score", "tranche infra", "intent completeness, wallet reference, review events, caveat presence", "per_tranche_event", 90, True),
    KPIFactoryTemplate("kpi_partner_live_readiness", "Partner Live Readiness", "provider", "score", "partner endpoints", "token configured, endpoint family, safety gates, operation whitelist", "per_provider_status", 88, False),
    KPIFactoryTemplate("kpi_compliance_friction", "Compliance Friction", "risk", "score", "OpenSanctions/OFAC/admin", "entity review flags, missing permissions, payout restrictions", "per_risk_scan", 93, True),
    KPIFactoryTemplate("kpi_public_source_coverage", "Public Source Coverage", "public_sources", "score", "public source expansion", "bound source count x value density minus integration difficulty", "daily_or_source_change", 91, False),
]


def list_kpi_templates() -> list[dict[str, Any]]:
    return [asdict(t) for t in sorted(KPI_TEMPLATES, key=lambda x: x.priority, reverse=True)]


def _clamp_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def _base_listing_factor(listing: dict[str, Any]) -> float:
    text_len = len(str(listing.get("title", ""))) + len(str(listing.get("description", "")))
    has_location = bool(listing.get("city") or listing.get("location_hint") or listing.get("latitude"))
    has_price = any(k in listing for k in ["price_low", "price_high", "suggested_price_low", "suggested_price_high"])
    return _clamp_score(35 + min(text_len / 8, 30) + (20 if has_location else 0) + (15 if has_price else 0))


def derive_kpi_value(template: KPIFactoryTemplate, listing: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = context or {}
    base = _base_listing_factor(listing)
    source_bonus = float(context.get("source_bonus", 0))
    proof_bonus = float(context.get("proof_bonus", 0))
    risk_penalty = float(context.get("risk_penalty", 0))
    priority_bonus = template.priority / 20
    if template.category == "risk":
        value = 100 - min(90, risk_penalty + (100 - base) * 0.35)
    elif template.category == "proofbook":
        value = 50 + proof_bonus + priority_bonus
    elif template.category in {"data_product", "public_sources", "sentence_as_service"}:
        value = base * 0.45 + source_bonus + priority_bonus + 25
    else:
        value = base * 0.65 + source_bonus * 0.2 + proof_bonus * 0.15 + priority_bonus
    score = _clamp_score(value)
    return {
        "template_id": template.template_id,
        "metric_name": template.name,
        "metric_value": score,
        "metric_unit": template.metric_unit,
        "category": template.category,
        "source_family": template.source_family,
        "formula_hint": template.formula_hint,
        "confidence": "deterministic_factory_estimate",
        "review_required": template.review_required,
        "explanation": f"{template.name} derived from base listing factor {base}, source bonus {source_bonus}, proof bonus {proof_bonus}, risk penalty {risk_penalty}.",
    }


def build_kpi_batch(*, listing: dict[str, Any], context: dict[str, Any] | None = None, limit: int = 12, cursor: str | None = None) -> dict[str, Any]:
    templates = sorted(KPI_TEMPLATES, key=lambda x: x.priority, reverse=True)
    start = int(cursor or 0)
    end = min(start + max(1, min(limit, 50)), len(templates))
    selected = templates[start:end]
    kpis = [derive_kpi_value(t, listing, context=context) for t in selected]
    next_cursor = str(end) if end < len(templates) else None
    seed = {"listing": listing, "start": start, "end": end, "kpis": kpis}
    return {
        "batch_id": "kpib_" + sha256_text(canonical_json(seed))[:24],
        "created_at": utc_now(),
        "cursor": cursor,
        "next_cursor": next_cursor,
        "limit": limit,
        "kpis": kpis,
        "count": len(kpis),
        "execution_mode": "bounded_batch_not_uncontrolled_loop",
    }


def build_infinite_kpi_production_plan(*, listing: dict[str, Any] | None = None, objective: str = "continuous high-density KPI production", batch_size: int = 12) -> dict[str, Any]:
    listing = listing or {"title": "MEMBRA KPI production subject", "description": "Subject for infinite KPI generation."}
    source_report = public_source_expansion_report()
    value_report = value_density_report()
    gauntlet = build_info_gauntlet(listing=listing)
    hyper = build_hypermodular_sentence_backing(listing=listing)
    micro = build_microoverworker_plan(listing=listing, objective=objective)
    context = {
        "source_bonus": min(35, source_report["source_count"] / 2),
        "proof_bonus": 10,
        "risk_penalty": 5 if listing else 15,
    }
    first_batch = build_kpi_batch(listing=listing, context=context, limit=batch_size)
    seed = {"listing": listing, "objective": objective, "first_batch": first_batch["batch_id"], "created_at": utc_now()}
    return {
        "production_plan_id": "ikpi_" + sha256_text(canonical_json(seed))[:24],
        "created_at": seed["created_at"],
        "product": "Infinite KPI Production",
        "objective": objective,
        "listing_context": listing,
        "kpi_templates": list_kpi_templates(),
        "first_batch": first_batch,
        "refresh_cadences": sorted({t.refresh_cadence for t in KPI_TEMPLATES}),
        "source_bindings": {
            "public_source_count": source_report["source_count"],
            "public_source_bundles": public_source_bundles(),
            "value_density_bundles": bundle_definitions(),
            "recommended_value_bundle": value_report["recommended_first_bundle"],
            "info_bits": list_info_bits(),
        },
        "microoverworker_plan": micro,
        "info_gauntlet": gauntlet,
        "hypermodular_packet_summary": {
            "packet_id": hyper["packet_id"],
            "backing_score": hyper["sentence_backing_score"],
            "databit_count": len(hyper["databits"]),
            "tranche_count": len(hyper["databit_tranches"]),
        },
        "worker_policy": {
            "no_unbounded_web_loop": True,
            "cursor_required": True,
            "max_batch_size": 50,
            "rate_limits_required": True,
            "provider_workers_required_for_live_fetch": True,
            "proofbook_event_per_batch": True,
        },
        "review_required": True,
    }


def record_kpi_batch(conn, context: BackendContext, *, subject_type: str, subject_id: str, batch: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for kpi in batch["kpis"]:
        record = record_kpi_observation(
            conn,
            context,
            subject_type=subject_type,
            subject_id=subject_id,
            metric_name=kpi["metric_name"],
            metric_value=float(kpi["metric_value"]),
            metric_unit=kpi["metric_unit"],
            confidence=0.72 if kpi["review_required"] else 0.9,
            source="infinite_kpi_factory",
            payload=kpi,
        )
        records.append(record)
    append_chain_event(conn, context, subject_type, subject_id, "infinite_kpi.batch_recorded", {"batch_id": batch["batch_id"], "count": len(records)})
    return records


def record_infinite_kpi_plan(conn, context: BackendContext, plan: dict[str, Any]) -> dict[str, Any]:
    return append_chain_event(
        conn,
        context,
        "infinite_kpi_plan",
        plan["production_plan_id"],
        "infinite_kpi.production_plan_created",
        plan,
    )


def create_infinite_kpi_production(conn, *, context: BackendContext, listing: dict[str, Any] | None = None, objective: str = "continuous high-density KPI production", batch_size: int = 12, record_first_batch: bool = True) -> dict[str, Any]:
    plan = build_infinite_kpi_production_plan(listing=listing, objective=objective, batch_size=batch_size)
    event = record_infinite_kpi_plan(conn, context, plan)
    records: list[dict[str, Any]] = []
    if record_first_batch:
        subject_id = str((listing or {}).get("listing_id") or plan["production_plan_id"])
        records = record_kpi_batch(conn, context, subject_type="listing", subject_id=subject_id, batch=plan["first_batch"])
    return {"success": True, "infinite_kpi_plan": plan, "proofbook_event": event, "recorded_kpis": records}
