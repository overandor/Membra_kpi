"""Tokenized tranche infrastructure primitives for MEMBRA KPI.

This module models sellable infrastructure tranches as access/entitlement
records around MicroOverWorker and language-fi capabilities.

Important boundaries:
- These records are not securities offerings.
- These records do not represent equity, debt, profit share, or investment contracts.
- Wallet addresses are non-custodial references only.
- Any tokenization adapter must run in devnet/dry-run unless a lawful production
  issuance path is configured externally.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .deep_backend import BackendContext, append_chain_event, canonical_json, sha256_text, utc_now
from .language_fi import language_fi_status
from .microoverworker import microoverworker_status, normalize_wallet_binding, wallet_fingerprint


@dataclass(frozen=True, slots=True)
class TrancheClass:
    tranche_id: str
    name: str
    target_user: str
    entitlement_scope: list[str]
    language_fi_scope: list[str]
    microoverworker_scope: list[str]
    proofbook_required_events: list[str]
    wallet_policy: str
    transfer_policy: str
    compliance_note: str


TRANCHE_CLASSES: list[TrancheClass] = [
    TrancheClass(
        tranche_id="lf_access_starter",
        name="Language-Fi Starter Access Tranche",
        target_user="solo operator or local asset owner",
        entitlement_scope=["listing localization", "KPI description localization", "deterministic templates"],
        language_fi_scope=["en", "fi", "es"],
        microoverworker_scope=["listing_writer", "proof_reviewer"],
        proofbook_required_events=["tranche.intent_created", "tranche.wallet_bound", "tranche.entitlement_recorded"],
        wallet_policy="optional non-custodial reference wallet",
        transfer_policy="non-transferable by default; admin approval required for transfer metadata",
        compliance_note="Access entitlement only; no equity, debt, profit share or guaranteed revenue.",
    ),
    TrancheClass(
        tranche_id="lf_operator",
        name="Language-Fi Operator Tranche",
        target_user="operator managing multilingual listings",
        entitlement_scope=["bulk localization", "review queue", "ProofBook localized labels", "admin review notes"],
        language_fi_scope=["en", "fi", "es", "uk", "ru"],
        microoverworker_scope=["listing_writer", "buyer_discovery", "proof_reviewer", "underwriting_analyst"],
        proofbook_required_events=["tranche.intent_created", "tranche.wallet_bound", "tranche.entitlement_recorded", "tranche.reviewed"],
        wallet_policy="required non-custodial reference wallet for entitlement anchoring",
        transfer_policy="restricted; requires tenant admin approval and ProofBook event",
        compliance_note="Operational software entitlement. No investment return or asset ownership claim.",
    ),
    TrancheClass(
        tranche_id="lf_infra_partner",
        name="Language-Fi Infrastructure Partner Tranche",
        target_user="partner integrating MEMBRA language-fi infra",
        entitlement_scope=["API access", "provider bundle access", "worker task planning", "localized investor packets"],
        language_fi_scope=["all_registered_locales", "provider_adapter_ready"],
        microoverworker_scope=["all_safe_worker_roles", "provider_catalog", "data_density_bundle", "audit_bundle"],
        proofbook_required_events=["tranche.intent_created", "tranche.wallet_bound", "tranche.entitlement_recorded", "tranche.partner_reviewed", "tranche.activation_approved"],
        wallet_policy="required non-custodial wallet reference plus tenant identity",
        transfer_policy="non-transferable unless a new partner review is completed",
        compliance_note="Infrastructure access package; requires legal/compliance review before public sale.",
    ),
]


def tranche_catalog() -> dict[str, Any]:
    return {
        "product": "MEMBRA tokenized language-fi infrastructure tranches",
        "mode": "entitlement_metadata",
        "tranches": [asdict(t) for t in TRANCHE_CLASSES],
        "language_fi": language_fi_status(),
        "microoverworker": microoverworker_status(),
        "boundaries": {
            "not_equity": True,
            "not_debt": True,
            "not_profit_share": True,
            "not_investment_contract": True,
            "no_guaranteed_revenue": True,
            "wallets_are_references_only": True,
            "devnet_or_dry_run_tokenization_default": True,
        },
    }


def get_tranche(tranche_id: str) -> TrancheClass:
    for tranche in TRANCHE_CLASSES:
        if tranche.tranche_id == tranche_id:
            return tranche
    raise ValueError(f"unknown tranche_id: {tranche_id}")


def build_tranche_intent(*, tranche_id: str, buyer_id: str, tenant_id: str, wallet_payload: dict[str, Any] | None = None, requested_locale: str = "en", notes: str = "") -> dict[str, Any]:
    tranche = get_tranche(tranche_id)
    wallet = normalize_wallet_binding(wallet_payload) if wallet_payload else None
    wallet_record = asdict(wallet) | {"fingerprint": wallet_fingerprint(wallet)} if wallet else None
    intent_seed = {
        "tranche_id": tranche_id,
        "buyer_id": buyer_id,
        "tenant_id": tenant_id,
        "wallet": wallet_record,
        "requested_locale": requested_locale,
        "notes": notes,
    }
    return {
        "intent_id": "tri_" + sha256_text(canonical_json(intent_seed))[:24],
        "created_at": utc_now(),
        "buyer_id": buyer_id,
        "tenant_id": tenant_id,
        "tranche": asdict(tranche),
        "wallet_reference": wallet_record,
        "requested_locale": requested_locale,
        "notes": notes,
        "status": "intent_created_review_required",
        "activation_mode": "manual_review_required",
        "tokenization_mode": "metadata_only_devnet_or_dry_run",
        "compliance_caveats": tranche.compliance_note,
    }


def record_tranche_intent(conn, context: BackendContext, intent: dict[str, Any]) -> dict[str, Any]:
    return append_chain_event(
        conn,
        context,
        "tranche_intent",
        intent["intent_id"],
        "tranche.intent_created",
        intent,
    )


def create_tranche_intent(conn, *, context: BackendContext, tranche_id: str, buyer_id: str, wallet_payload: dict[str, Any] | None = None, requested_locale: str = "en", notes: str = "") -> dict[str, Any]:
    intent = build_tranche_intent(
        tranche_id=tranche_id,
        buyer_id=buyer_id,
        tenant_id=context.tenant_id,
        wallet_payload=wallet_payload,
        requested_locale=requested_locale,
        notes=notes,
    )
    event = record_tranche_intent(conn, context, intent)
    return {"success": True, "intent": intent, "proofbook_event": event}


def build_entitlement_record(intent: dict[str, Any], approved_by: str) -> dict[str, Any]:
    entitlement_seed = {
        "intent_id": intent["intent_id"],
        "approved_by": approved_by,
        "tenant_id": intent["tenant_id"],
        "tranche_id": intent["tranche"]["tranche_id"],
    }
    return {
        "entitlement_id": "ent_" + sha256_text(canonical_json(entitlement_seed))[:24],
        "intent_id": intent["intent_id"],
        "tenant_id": intent["tenant_id"],
        "buyer_id": intent["buyer_id"],
        "tranche_id": intent["tranche"]["tranche_id"],
        "wallet_reference": intent.get("wallet_reference"),
        "approved_by": approved_by,
        "status": "approved_entitlement_recorded",
        "created_at": utc_now(),
        "rights_summary": intent["tranche"]["entitlement_scope"],
        "non_rights_summary": ["no equity", "no debt", "no profit share", "no guaranteed revenue", "no fund custody"],
    }


def record_entitlement(conn, context: BackendContext, entitlement: dict[str, Any]) -> dict[str, Any]:
    return append_chain_event(
        conn,
        context,
        "tranche_entitlement",
        entitlement["entitlement_id"],
        "tranche.entitlement_recorded",
        entitlement,
    )
