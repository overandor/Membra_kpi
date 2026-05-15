"""Golden-ratio and prime-gap decision heuristics for MEMBRA.

This module adds deterministic workflow scoring primitives inspired by:
- golden ratio weighting for balanced exploitation/exploration
- prime-gap spacing for anti-crowding, retry cadence, and worker scheduling

These are decision heuristics, not mathematical guarantees. They are designed to
make MEMBRA orchestration decisions stable, inspectable, non-random, and harder
to collapse into repetitive worker choices.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from .deep_backend import BackendContext, append_chain_event, canonical_json, sha256_text, utc_now

PHI = (1 + math.sqrt(5)) / 2
INV_PHI = 1 / PHI
INV_PHI_SQUARED = 1 / (PHI * PHI)
PRIMES = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71]
PRIME_GAPS = [PRIMES[i + 1] - PRIMES[i] for i in range(len(PRIMES) - 1)]


@dataclass(frozen=True, slots=True)
class DecisionCandidate:
    candidate_id: str
    label: str
    utility_score: float
    confidence_score: float
    novelty_score: float
    proof_score: float
    risk_score: float
    metadata: dict[str, Any]


def clamp(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 4)


def golden_weighted_score(candidate: DecisionCandidate) -> float:
    """Balance value/proof against novelty/risk using golden-ratio weights."""
    exploitation = (candidate.utility_score * INV_PHI) + (candidate.proof_score * INV_PHI_SQUARED)
    exploration = candidate.novelty_score * INV_PHI_SQUARED
    confidence = candidate.confidence_score * 0.18
    risk_penalty = candidate.risk_score * INV_PHI_SQUARED
    return clamp(exploitation + exploration + confidence - risk_penalty)


def prime_gap_priority(index: int, score: float) -> dict[str, Any]:
    gap = PRIME_GAPS[index % len(PRIME_GAPS)]
    prime = PRIMES[index % len(PRIMES)]
    retry_delay_seconds = int((gap + prime) * PHI)
    slot = int((score + prime + gap) % 100)
    return {
        "prime": prime,
        "prime_gap": gap,
        "retry_delay_seconds": retry_delay_seconds,
        "anti_crowding_slot": slot,
    }


def rank_decision_candidates(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    normalized: list[DecisionCandidate] = []
    for idx, raw in enumerate(candidates):
        normalized.append(DecisionCandidate(
            candidate_id=str(raw.get("candidate_id") or raw.get("id") or f"candidate_{idx}"),
            label=str(raw.get("label") or raw.get("name") or f"Candidate {idx}"),
            utility_score=float(raw.get("utility_score", raw.get("score", 50))),
            confidence_score=float(raw.get("confidence_score", 60)),
            novelty_score=float(raw.get("novelty_score", 50)),
            proof_score=float(raw.get("proof_score", 50)),
            risk_score=float(raw.get("risk_score", 25)),
            metadata=dict(raw.get("metadata", {})),
        ))
    ranked = []
    for idx, candidate in enumerate(normalized):
        score = golden_weighted_score(candidate)
        ranked.append({
            **asdict(candidate),
            "golden_score": score,
            "prime_gap_schedule": prime_gap_priority(idx, score),
        })
    ranked.sort(key=lambda x: (x["golden_score"], x["novelty_score"], x["proof_score"]), reverse=True)
    return {
        "decision_id": "gpd_" + sha256_text(canonical_json({"candidates": candidates, "created_at": utc_now()}))[:24],
        "created_at": utc_now(),
        "method": "golden_ratio_weighting_with_prime_gap_anti_crowding",
        "phi": PHI,
        "ranked_candidates": ranked,
        "selected": ranked[0] if ranked else None,
        "review_required": True,
    }


def workflow_step_schedule(step_count: int) -> list[dict[str, Any]]:
    steps = []
    for idx in range(max(0, step_count)):
        prime = PRIMES[idx % len(PRIMES)]
        gap = PRIME_GAPS[idx % len(PRIME_GAPS)]
        steps.append({
            "step_index": idx + 1,
            "prime": prime,
            "prime_gap": gap,
            "golden_phase": round(((idx + 1) * INV_PHI) % 1, 6),
            "recommended_cadence_seconds": int((prime + gap) * PHI),
        })
    return steps


def record_decision(conn, context: BackendContext, decision: dict[str, Any]) -> dict[str, Any]:
    return append_chain_event(
        conn,
        context,
        "golden_prime_decision",
        decision["decision_id"],
        "golden_prime.decision_ranked",
        decision,
    )


def create_golden_prime_decision(conn, *, context: BackendContext, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    decision = rank_decision_candidates(candidates)
    event = record_decision(conn, context, decision)
    return {"success": True, "decision": decision, "proofbook_event": event}
