"""MicroOverWorker product bundle for MEMBRA KPI.

MicroOverWorker unifies endpoints, wallet addresses, KPI records, repository
metadata, provider bundles, and LLM employee tasks into one auditable product
worker plan.

It is designed as a safe orchestration layer:
- no raw secret exposure
- no private-key storage
- no fund movement
- no mainnet signing
- ProofBook events for material worker plans
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .deep_backend import BackendContext, append_chain_event, canonical_json, sha256_text, utc_now
from .external_providers import provider_registry
from .llm_employee_bundle import build_employee_task, llm_employee_bundle_status
from .value_api_bundle import bundle_definitions, listing_enrichment_plan, value_density_report


@dataclass(frozen=True, slots=True)
class RepoBinding:
    repo: str
    role: str
    product_surface: str
    status: str


@dataclass(frozen=True, slots=True)
class WalletBinding:
    wallet_type: str
    address: str
    network: str
    purpose: str
    custody_mode: str
    status: str


MEMBRA_REPOS: list[RepoBinding] = [
    RepoBinding("overandor/membra", "canonical runtime and platform hub", "core_os", "active"),
    RepoBinding("overandor/Membra_kpi", "KPI, listing, ProofBook and worker backend", "microoverworker", "active"),
    RepoBinding("overandor/Membra_wallet", "wallet eligibility boundary", "wallet", "namespace"),
    RepoBinding("overandor/Membra_proofbook", "proof ledger namespace", "proofbook", "namespace"),
    RepoBinding("overandor/Membra_api", "API namespace", "api", "namespace"),
    RepoBinding("overandor/Membra_mobile", "mobile capture namespace", "mobile", "namespace"),
    RepoBinding("overandor/47", "language-fi multilingual adapter namespace", "language_fi", "registered"),
]


def repo_bundle() -> list[dict[str, Any]]:
    return [asdict(repo) for repo in MEMBRA_REPOS]


def normalize_wallet_binding(payload: dict[str, Any]) -> WalletBinding:
    address = str(payload.get("address", "")).strip()
    network = str(payload.get("network", "unknown")).strip().lower()
    wallet_type = str(payload.get("wallet_type", "external_wallet")).strip()
    purpose = str(payload.get("purpose", "payout_eligibility_reference")).strip()
    if not address:
        raise ValueError("wallet address is required")
    if len(address) < 16:
        raise ValueError("wallet address is too short to register")
    return WalletBinding(
        wallet_type=wallet_type,
        address=address,
        network=network,
        purpose=purpose,
        custody_mode="non_custodial_reference_only",
        status="registered_reference",
    )


def wallet_fingerprint(wallet: WalletBinding) -> str:
    return sha256_text(canonical_json(asdict(wallet)))[:32]


def microoverworker_status() -> dict[str, Any]:
    return {
        "product": "MEMBRA MicroOverWorker",
        "description": "Endpoint, wallet, KPI, repo, provider and LLM-employee orchestration layer.",
        "repos": repo_bundle(),
        "providers": provider_registry(),
        "data_bundles": bundle_definitions(),
        "llm_employee_bundle": llm_employee_bundle_status(),
        "safety": {
            "wallets_are_references_only": True,
            "no_custody": True,
            "no_mainnet_signing": True,
            "proofbook_audited_plans": True,
            "human_review_required_for_public_activation": True,
        },
    }


def build_microoverworker_plan(
    *,
    listing: dict[str, Any],
    wallet_payloads: list[dict[str, Any]] | None = None,
    kpis: list[dict[str, Any]] | None = None,
    objective: str = "enrich listing, map buyer demand, verify proof posture and prepare review packet",
) -> dict[str, Any]:
    wallets = [normalize_wallet_binding(w) for w in (wallet_payloads or [])]
    wallet_records = [asdict(w) | {"fingerprint": wallet_fingerprint(w)} for w in wallets]
    enrichment_plan = listing_enrichment_plan(listing)
    llm_tasks = [
        build_employee_task("underwriting_analyst", objective, listing=listing),
        build_employee_task("buyer_discovery", "Find nearby buyer categories and pitch targets for this listing.", listing=listing),
        build_employee_task("proof_reviewer", "Review proof posture and admin readiness for this listing.", listing=listing),
    ]
    plan_payload = {
        "product": "MEMBRA MicroOverWorker",
        "plan_id": "mow_" + sha256_text(canonical_json({"listing": listing, "wallets": wallet_records, "kpis": kpis or [], "objective": objective}))[:24],
        "created_at": utc_now(),
        "objective": objective,
        "listing": listing,
        "wallet_references": wallet_records,
        "kpis": kpis or [],
        "repos": repo_bundle(),
        "provider_bundle": value_density_report()["recommended_first_bundle"],
        "enrichment_plan": enrichment_plan,
        "llm_employee_tasks": llm_tasks,
        "review_required": True,
        "execution_mode": "plan_only_until_worker_queue_executes",
    }
    return plan_payload


def record_microoverworker_plan(conn, context: BackendContext, plan: dict[str, Any]) -> dict[str, Any]:
    return append_chain_event(
        conn,
        context,
        "microoverworker_plan",
        plan["plan_id"],
        "microoverworker.plan_created",
        plan,
    )


def create_microoverworker_product_bundle(conn, *, context: BackendContext, listing: dict[str, Any], wallet_payloads: list[dict[str, Any]] | None = None, kpis: list[dict[str, Any]] | None = None, objective: str | None = None) -> dict[str, Any]:
    plan = build_microoverworker_plan(
        listing=listing,
        wallet_payloads=wallet_payloads,
        kpis=kpis,
        objective=objective or "enrich listing, map buyer demand, verify proof posture and prepare review packet",
    )
    event = record_microoverworker_plan(conn, context, plan)
    return {"success": True, "bundle": plan, "proofbook_event": event}
