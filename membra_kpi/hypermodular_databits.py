"""Hypermodular DataBits for MEMBRA KPI.

This layer breaks expensive data value into tiny auditable DataBits, then uses
those bits to back a Sentence-as-a-Service product. DataBits can be scattered as
metadata anchors across Solana devnet through safe anchor plans.

Boundaries:
- DataBits are information/access metadata, not securities.
- No equity, debt, profit share, or guaranteed revenue is represented.
- Wallets are non-custodial references only.
- Solana support is devnet/dry-run metadata anchoring by default.
- Production token issuance requires external legal/compliance review.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .deep_backend import BackendContext, append_chain_event, canonical_json, sha256_text, utc_now
from .info_gauntlets import build_info_gauntlet, select_info_bits
from .sentence_as_service import build_sentence_product
from .solana_devnet import listing_anchor_payload, memo_text_for_payload


@dataclass(frozen=True, slots=True)
class DataBit:
    databit_id: str
    parent_sentence_id: str
    label: str
    category: str
    value_claim: str
    source_family: str
    density_score: int
    scarcity_score: int
    proof_weight: int
    review_required: bool
    metadata_hash: str


@dataclass(frozen=True, slots=True)
class DataBitTranche:
    tranche_id: str
    parent_sentence_id: str
    tranche_label: str
    bit_ids: list[str]
    aggregate_density_score: float
    aggregate_proof_weight: float
    entitlement_mode: str
    transfer_policy: str
    compliance_note: str


def _score_scarcity(bit: dict[str, Any]) -> int:
    category = bit.get("category", "")
    if category in {"proof", "compliance", "wallet"}:
        return 88
    if category in {"buyer_discovery", "underwriting"}:
        return 82
    if category in {"research", "web3"}:
        return 76
    return 70


def _score_proof_weight(bit: dict[str, Any]) -> int:
    confidence = str(bit.get("confidence", ""))
    if confidence == "deterministic":
        return 95
    if "review" in confidence:
        return 78
    if "source" in confidence:
        return 72
    return 65


def create_databits_for_sentence(sentence_product: dict[str, Any], *, categories: list[str] | None = None) -> list[dict[str, Any]]:
    bits = select_info_bits(categories=categories, min_value_density=70)
    parent_sentence_id = sentence_product["sentence_id"]
    databits: list[dict[str, Any]] = []
    for bit in bits:
        seed = {
            "parent_sentence_id": parent_sentence_id,
            "label": bit["label"],
            "category": bit["category"],
            "source_family": bit["source_family"],
            "claim": bit["claim"],
        }
        metadata_hash = sha256_text(canonical_json(seed))
        databits.append(asdict(DataBit(
            databit_id="dbit_" + metadata_hash[:24],
            parent_sentence_id=parent_sentence_id,
            label=bit["label"],
            category=bit["category"],
            value_claim=bit["claim"],
            source_family=bit["source_family"],
            density_score=int(bit["value_density"]),
            scarcity_score=_score_scarcity(bit),
            proof_weight=_score_proof_weight(bit),
            review_required=bool(bit["review_required"]),
            metadata_hash=metadata_hash,
        )))
    return databits


def build_databit_tranches(sentence_product: dict[str, Any], databits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for bit in databits:
        grouped.setdefault(bit["category"], []).append(bit)
    tranches: list[dict[str, Any]] = []
    for category, bits in grouped.items():
        avg_density = round(sum(b["density_score"] for b in bits) / len(bits), 2)
        avg_proof = round(sum(b["proof_weight"] for b in bits) / len(bits), 2)
        seed = {"parent_sentence_id": sentence_product["sentence_id"], "category": category, "bit_ids": [b["databit_id"] for b in bits]}
        tranche_hash = sha256_text(canonical_json(seed))
        tranches.append(asdict(DataBitTranche(
            tranche_id="dbtr_" + tranche_hash[:24],
            parent_sentence_id=sentence_product["sentence_id"],
            tranche_label=f"{category.replace('_', ' ').title()} DataBit Tranche",
            bit_ids=[b["databit_id"] for b in bits],
            aggregate_density_score=avg_density,
            aggregate_proof_weight=avg_proof,
            entitlement_mode="metadata_access_reference",
            transfer_policy="review_required_non_custodial_reference",
            compliance_note="Information-access metadata only; no investment return, equity, debt, or profit share.",
        )))
    return sorted(tranches, key=lambda x: x["aggregate_density_score"], reverse=True)


def build_solana_scatter_anchor_plan(sentence_product: dict[str, Any], databits: list[dict[str, Any]], tranches: list[dict[str, Any]]) -> dict[str, Any]:
    anchor_items: list[dict[str, Any]] = []
    for item in databits + tranches:
        listing_like = {
            "listing_id": item.get("databit_id") or item.get("tranche_id"),
            "sku": item.get("category") or "databit_tranche",
            "title": item.get("label") or item.get("tranche_label"),
            "description": canonical_json(item),
            "pricing_unit": "metadata_reference",
        }
        payload = listing_anchor_payload(listing_like, proof_hash=item.get("metadata_hash"))
        anchor_items.append({
            "anchor_subject_id": listing_like["listing_id"],
            "anchor_subject_type": "databit" if "databit_id" in item else "databit_tranche",
            "anchor_hash": payload["anchor_hash"],
            "payload": payload,
            "memo_preview": memo_text_for_payload(payload)[:96] + "...",
            "network": "solana-devnet",
            "mode": "scatter_anchor_plan_only",
        })
    plan_seed = {
        "sentence_id": sentence_product["sentence_id"],
        "anchor_count": len(anchor_items),
        "anchor_hashes": [a["anchor_hash"] for a in anchor_items],
    }
    return {
        "scatter_plan_id": "scat_" + sha256_text(canonical_json(plan_seed))[:24],
        "parent_sentence_id": sentence_product["sentence_id"],
        "network": "solana-devnet",
        "mode": "dry_run_or_devnet_worker_required",
        "anchor_count": len(anchor_items),
        "anchor_items": anchor_items,
        "safety": {
            "mainnet_disabled": True,
            "no_funds_moved": True,
            "metadata_only": True,
            "review_required": True,
        },
    }


def calculate_sentence_backing_score(databits: list[dict[str, Any]], tranches: list[dict[str, Any]]) -> dict[str, Any]:
    if not databits:
        return {"backing_score": 0, "grade": "F", "density": 0, "scarcity": 0, "proof_weight": 0}
    density = round(sum(b["density_score"] for b in databits) / len(databits), 2)
    scarcity = round(sum(b["scarcity_score"] for b in databits) / len(databits), 2)
    proof_weight = round(sum(b["proof_weight"] for b in databits) / len(databits), 2)
    tranche_bonus = min(len(tranches) * 1.5, 10)
    backing_score = round((density * 0.45) + (scarcity * 0.25) + (proof_weight * 0.25) + tranche_bonus, 2)
    if backing_score >= 95:
        grade = "A+"
    elif backing_score >= 90:
        grade = "A"
    elif backing_score >= 85:
        grade = "B+"
    elif backing_score >= 80:
        grade = "B"
    elif backing_score >= 75:
        grade = "C+"
    elif backing_score >= 70:
        grade = "C"
    else:
        grade = "D"
    return {"backing_score": backing_score, "grade": grade, "density": density, "scarcity": scarcity, "proof_weight": proof_weight, "tranche_bonus": tranche_bonus}


def build_hypermodular_sentence_backing(*, listing: dict[str, Any] | None = None, categories: list[str] | None = None, locale: str = "en") -> dict[str, Any]:
    listing = listing or {"title": "MEMBRA sentence-backed data product", "description": "Hypermodular DataBits backing a proof-aware commercial sentence."}
    sentence = build_sentence_product(listing=listing, locale=locale)
    gauntlet = build_info_gauntlet(listing=listing, categories=categories, locale=locale)
    databits = create_databits_for_sentence(sentence, categories=categories)
    tranches = build_databit_tranches(sentence, databits)
    scatter_plan = build_solana_scatter_anchor_plan(sentence, databits, tranches)
    backing_score = calculate_sentence_backing_score(databits, tranches)
    packet_seed = {
        "sentence_id": sentence["sentence_id"],
        "databit_ids": [b["databit_id"] for b in databits],
        "tranche_ids": [t["tranche_id"] for t in tranches],
        "scatter_plan_id": scatter_plan["scatter_plan_id"],
    }
    return {
        "packet_id": "hmb_" + sha256_text(canonical_json(packet_seed))[:24],
        "created_at": utc_now(),
        "product": "Hypermodular Sentence-Backed DataBits",
        "sentence_product": sentence,
        "info_gauntlet": gauntlet,
        "databits": databits,
        "databit_tranches": tranches,
        "solana_scatter_anchor_plan": scatter_plan,
        "sentence_backing_score": backing_score,
        "value_sentence": "A MEMBRA sentence is backed by scattered, proof-weighted DataBits that compress public data, KPIs, wallet references, repos, partner endpoints, and language-fi infrastructure into auditable Solana-devnet metadata anchors.",
        "caveats": [
            "DataBits are metadata/information units, not securities.",
            "Solana anchors are devnet/dry-run metadata references unless explicitly configured otherwise.",
            "No custody, payout, mainnet signing, equity, debt, profit share, or guaranteed revenue is represented.",
            "Live provider claims require configured worker execution and ProofBook evidence.",
        ],
        "review_required": True,
    }


def record_hypermodular_sentence_backing(conn, context: BackendContext, packet: dict[str, Any]) -> dict[str, Any]:
    return append_chain_event(
        conn,
        context,
        "hypermodular_sentence_backing",
        packet["packet_id"],
        "hypermodular.databits_sentence_backed",
        packet,
    )


def create_hypermodular_sentence_backing(conn, *, context: BackendContext, listing: dict[str, Any] | None = None, categories: list[str] | None = None, locale: str = "en") -> dict[str, Any]:
    packet = build_hypermodular_sentence_backing(listing=listing, categories=categories, locale=locale)
    event = record_hypermodular_sentence_backing(conn, context, packet)
    return {"success": True, "hypermodular_packet": packet, "proofbook_event": event}
