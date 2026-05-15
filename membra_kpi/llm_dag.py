"""MEMBRA Proprietary LLM DAG.

This module defines a deterministic, auditable DAG runtime for turning image and
listing signals into marketplace-grade intelligence. It is intentionally built as
MEMBRA infrastructure rather than a generic agent wrapper.

Core idea:

    image evidence
    -> quality packet
    -> duplicate packet
    -> SKU hypothesis
    -> proof manifest
    -> proprietary listing packet
    -> LLM critique / enrichment
    -> operator decision
    -> publication gate

The DAG supports two modes:

1. deterministic mode: no external LLM required, always works in Replit/local CI
2. adapter mode: callers can inject an LLM callable for Ollama/Groq/OpenAI/etc.

No node executes trades, handles custody, or guarantees earnings. The DAG only
creates auditable listing intelligence and review recommendations.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable


class DagStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class NodeKind(str, Enum):
    INGESTION = "ingestion"
    IMAGE_ANALYSIS = "image_analysis"
    SKU_REASONING = "sku_reasoning"
    PROOF_REASONING = "proof_reasoning"
    LISTING_ENRICHMENT = "listing_enrichment"
    RISK_REVIEW = "risk_review"
    OPERATOR_DECISION = "operator_decision"
    PUBLICATION_GATE = "publication_gate"


@dataclass(frozen=True)
class DagNodeSpec:
    node_id: str
    kind: NodeKind
    description: str
    depends_on: list[str] = field(default_factory=list)
    required_inputs: list[str] = field(default_factory=list)
    output_key: str = ""


@dataclass
class DagNodeRun:
    node_id: str
    kind: str
    status: DagStatus = DagStatus.PENDING
    started_at_ms: int | None = None
    finished_at_ms: int | None = None
    duration_ms: int | None = None
    input_hash: str = ""
    output_hash: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


@dataclass(frozen=True)
class DagExecutionResult:
    dag_id: str
    status: str
    graph_version: str
    created_at_ms: int
    finished_at_ms: int
    duration_ms: int
    node_runs: list[dict[str, Any]]
    outputs: dict[str, Any]
    audit_hash: str
    safety: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


LLMCallable = Callable[[str, dict[str, Any]], str]


GRAPH_VERSION = "membra_llm_dag_v1.0.0"


MEMBRA_LISTING_DAG: list[DagNodeSpec] = [
    DagNodeSpec(
        node_id="ingestion_context",
        kind=NodeKind.INGESTION,
        description="Normalize owner, image, context, and existing packet inputs.",
        required_inputs=["owner_id"],
        output_key="ingestion_context",
    ),
    DagNodeSpec(
        node_id="image_forensics",
        kind=NodeKind.IMAGE_ANALYSIS,
        description="Analyze image quality, hash evidence, duplicate posture, and visual readiness.",
        depends_on=["ingestion_context"],
        required_inputs=["image_quality"],
        output_key="image_forensics",
    ),
    DagNodeSpec(
        node_id="sku_hypothesis",
        kind=NodeKind.SKU_REASONING,
        description="Reason over SKU candidates and select a proprietary commercial hypothesis.",
        depends_on=["image_forensics"],
        required_inputs=["sku_identification"],
        output_key="sku_hypothesis",
    ),
    DagNodeSpec(
        node_id="proof_gap_analysis",
        kind=NodeKind.PROOF_REASONING,
        description="Evaluate missing proof, owner fields, and publication blockers.",
        depends_on=["sku_hypothesis"],
        required_inputs=["proprietary_listing_packet"],
        output_key="proof_gap_analysis",
    ),
    DagNodeSpec(
        node_id="listing_enrichment",
        kind=NodeKind.LISTING_ENRICHMENT,
        description="Generate MEMBRA-grade title, description, SEO tags, and owner next steps.",
        depends_on=["proof_gap_analysis"],
        required_inputs=["proprietary_listing_packet"],
        output_key="listing_enrichment",
    ),
    DagNodeSpec(
        node_id="risk_review",
        kind=NodeKind.RISK_REVIEW,
        description="Produce risk posture, compliance notes, and blocked-publication explanation.",
        depends_on=["listing_enrichment"],
        required_inputs=["proprietary_listing_packet"],
        output_key="risk_review",
    ),
    DagNodeSpec(
        node_id="operator_decision",
        kind=NodeKind.OPERATOR_DECISION,
        description="Route the candidate to private draft, owner fields, operator review, retake, or blocked.",
        depends_on=["risk_review"],
        required_inputs=["operator_summary"],
        output_key="operator_decision",
    ),
    DagNodeSpec(
        node_id="publication_gate",
        kind=NodeKind.PUBLICATION_GATE,
        description="Final publication eligibility gate based on proof, risk, and owner confirmation.",
        depends_on=["operator_decision"],
        required_inputs=["publish", "owner_confirmed"],
        output_key="publication_gate",
    ),
]


def now_ms() -> int:
    return int(time.time() * 1000)


def stable_hash(payload: Any, length: int = 32) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:length]


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return json.dumps(value, default=str, sort_keys=True)


def clamp_int(value: float, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, int(round(value))))


def require_inputs(context: dict[str, Any], node: DagNodeSpec) -> None:
    missing = [key for key in node.required_inputs if key not in context]
    if missing:
        raise ValueError(f"DAG node {node.node_id} missing required inputs: {missing}")


def top_candidate(sku_identification: dict[str, Any]) -> dict[str, Any]:
    return sku_identification.get("top_candidate") or (sku_identification.get("candidates") or [{}])[0]


def safe_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def deterministic_bullet_digest(*parts: Any, max_items: int = 8) -> list[str]:
    text = " ".join(normalize_text(p) for p in parts)
    tokens = [t for t in re.split(r"[^a-zA-Z0-9_$%.-]+", text) if len(t) > 3]
    seen: list[str] = []
    for token in tokens:
        key = token.lower()
        if key not in [s.lower() for s in seen]:
            seen.append(token)
        if len(seen) >= max_items:
            break
    return seen


def maybe_llm(llm: LLMCallable | None, prompt: str, payload: dict[str, Any], fallback: str) -> dict[str, Any]:
    if not llm:
        return {"mode": "deterministic", "text": fallback, "llm_error": ""}
    try:
        return {"mode": "llm", "text": llm(prompt, payload), "llm_error": ""}
    except Exception as exc:
        return {"mode": "deterministic_fallback", "text": fallback, "llm_error": str(exc)}


def node_ingestion_context(context: dict[str, Any], llm: LLMCallable | None = None) -> dict[str, Any]:
    owner_id = context.get("owner_id", "owner_default")
    photo_id = context.get("photo_id", "")
    filename = context.get("filename", "")
    location_hint = context.get("location_hint", "")
    user_notes = context.get("user_notes", "")
    return {
        "owner_id": owner_id,
        "photo_id": photo_id,
        "filename": filename,
        "location_hint": location_hint,
        "user_notes_digest": deterministic_bullet_digest(user_notes, location_hint, filename, max_items=6),
        "context_hash": stable_hash({"owner_id": owner_id, "photo_id": photo_id, "filename": filename, "location_hint": location_hint}),
        "operating_boundary": "AI may draft listing intelligence; owner approval and external settlement are required.",
    }


def node_image_forensics(context: dict[str, Any], llm: LLMCallable | None = None) -> dict[str, Any]:
    quality = safe_dict(context.get("image_quality"))
    score = int(quality.get("listing_quality_score") or 0)
    warnings = safe_list(quality.get("warnings"))
    readiness = "high" if score >= 82 else "medium" if score >= 60 else "low" if score >= 45 else "blocked"
    fallback = (
        f"Image readiness is {readiness}. Quality score {score}. "
        f"Warnings: {', '.join(map(str, warnings)) or 'none'}."
    )
    llm_note = maybe_llm(
        llm,
        "Analyze this MEMBRA listing image quality report for operator readiness. Return concise operational guidance.",
        {"image_quality": quality},
        fallback,
    )
    return {
        "readiness": readiness,
        "quality_score": score,
        "quality_grade": quality.get("quality_grade"),
        "exact_sha256": quality.get("exact_sha256"),
        "average_hash": quality.get("average_hash"),
        "warnings": warnings,
        "recommended_actions": safe_list(quality.get("recommended_actions")),
        "operator_note": llm_note,
    }


def node_sku_hypothesis(context: dict[str, Any], llm: LLMCallable | None = None) -> dict[str, Any]:
    sku_identification = safe_dict(context.get("sku_identification"))
    top = top_candidate(sku_identification)
    candidates = safe_list(sku_identification.get("candidates"))
    fallback = (
        f"Top SKU hypothesis is {top.get('sku')} for {top.get('asset_type')} "
        f"with confidence {top.get('confidence')} and grade {top.get('confidence_grade')}."
    )
    llm_note = maybe_llm(
        llm,
        "Review MEMBRA SKU candidates and explain why the top candidate should or should not be used.",
        {"top_candidate": top, "candidates": candidates[:5]},
        fallback,
    )
    return {
        "top_sku": top.get("sku"),
        "sku_family": top.get("sku_family"),
        "asset_type": top.get("asset_type"),
        "marketplace_category": top.get("marketplace_category"),
        "confidence": top.get("confidence"),
        "confidence_grade": top.get("confidence_grade"),
        "candidate_count": len(candidates),
        "evidence": safe_list(top.get("evidence")),
        "owner_fields_requested": safe_list(top.get("requested_owner_fields")),
        "operator_note": llm_note,
    }


def node_proof_gap_analysis(context: dict[str, Any], llm: LLMCallable | None = None) -> dict[str, Any]:
    packet = safe_dict(context.get("proprietary_listing_packet"))
    missing = safe_list(packet.get("missing_proof"))
    manifest = safe_list(packet.get("proof_manifest"))
    blocking = [row for row in manifest if row.get("blocks_publication_if_missing") and not row.get("present")]
    proof_score = int(packet.get("proof_score") or 0)
    fallback = (
        f"Proof score {proof_score}. Missing proof count {len(missing)}. "
        f"Blocking missing fields: {', '.join(str(x.get('key')) for x in blocking) or 'none'}."
    )
    llm_note = maybe_llm(
        llm,
        "Evaluate proof gaps for a MEMBRA listing packet. Identify owner next steps and publication blockers.",
        {"proof_score": proof_score, "missing_proof": missing, "blocking": blocking, "manifest": manifest},
        fallback,
    )
    return {
        "proof_score": proof_score,
        "proof_grade": packet.get("proof_grade"),
        "missing_proof": missing,
        "blocking_missing_proof": blocking,
        "required_owner_fields": safe_list(packet.get("required_owner_fields")),
        "operator_note": llm_note,
    }


def node_listing_enrichment(context: dict[str, Any], llm: LLMCallable | None = None) -> dict[str, Any]:
    packet = safe_dict(context.get("proprietary_listing_packet"))
    title = packet.get("title") or "MEMBRA listing candidate"
    description = packet.get("description") or "Owner-controlled MEMBRA listing candidate."
    seo = safe_dict(packet.get("seo"))
    commercial_profile = safe_dict(packet.get("commercial_profile"))
    fallback = (
        f"{title}\n\n{description}\n\nCommercial model: "
        f"{commercial_profile.get('revenue_model', 'manual review required')}"
    )
    llm_note = maybe_llm(
        llm,
        "Improve this MEMBRA listing copy without guaranteeing earnings. Keep owner-proof and compliance language.",
        {"title": title, "description": description, "seo": seo, "commercial_profile": commercial_profile},
        fallback,
    )
    return {
        "title": title,
        "description": description,
        "seo": seo,
        "commercial_use_cases": safe_list(commercial_profile.get("commercial_use_cases")),
        "buyer_persona": commercial_profile.get("buyer_persona"),
        "seller_persona": commercial_profile.get("seller_persona"),
        "operator_note": llm_note,
    }


def node_risk_review(context: dict[str, Any], llm: LLMCallable | None = None) -> dict[str, Any]:
    packet = safe_dict(context.get("proprietary_listing_packet"))
    risk_tier = packet.get("risk_tier", "yellow")
    review_actions = safe_list(packet.get("review_actions"))
    compliance_score = int(packet.get("compliance_score") or 0)
    safety = {
        "earnings_not_guaranteed": True,
        "owner_approval_required": True,
        "external_settlement_required": True,
        "non_custodial": True,
    }
    fallback = (
        f"Risk tier {risk_tier}. Compliance score {compliance_score}. "
        f"Review actions: {', '.join(map(str, review_actions)) or 'none'}."
    )
    llm_note = maybe_llm(
        llm,
        "Review MEMBRA listing risk. Produce compliance-safe operator guidance. Do not promise earnings.",
        {"risk_tier": risk_tier, "review_actions": review_actions, "compliance_score": compliance_score, "safety": safety},
        fallback,
    )
    return {
        "risk_tier": risk_tier,
        "compliance_score": compliance_score,
        "review_actions": review_actions,
        "safety": safety,
        "operator_note": llm_note,
    }


def node_operator_decision(context: dict[str, Any], llm: LLMCallable | None = None) -> dict[str, Any]:
    summary = safe_dict(context.get("operator_summary"))
    packet = safe_dict(context.get("proprietary_listing_packet"))
    review_actions = safe_list(packet.get("review_actions"))
    next_action = summary.get("next_action") or (review_actions[0] if review_actions else "owner_fields_required")
    valuation_score = int(packet.get("valuation_score") or summary.get("valuation_score") or 0)
    operator_score = int(packet.get("operator_score") or summary.get("operator_score") or 0)
    if "block_publication" in review_actions:
        decision = "hold_private_block_publication"
    elif "proof_retake_required" in review_actions:
        decision = "request_retake_or_more_proof"
    elif "operator_review_required" in review_actions or "compliance_review_required" in review_actions:
        decision = "route_to_operator_review"
    elif "owner_fields_required" in review_actions:
        decision = "request_owner_fields_then_publish_review"
    else:
        decision = "eligible_for_private_draft_and_owner_confirmation"
    return {
        "decision": decision,
        "next_action": next_action,
        "operator_score": operator_score,
        "valuation_score": valuation_score,
        "score_band": summary.get("score_band"),
        "appraisal_midpoint": summary.get("appraisal_midpoint"),
        "operator_summary": summary,
    }


def node_publication_gate(context: dict[str, Any], llm: LLMCallable | None = None) -> dict[str, Any]:
    publish = bool(context.get("publish"))
    owner_confirmed = bool(context.get("owner_confirmed"))
    packet = safe_dict(context.get("proprietary_listing_packet"))
    review_actions = safe_list(packet.get("review_actions"))
    risk_tier = packet.get("risk_tier")
    blocked = "block_publication" in review_actions or risk_tier in {"red", "blocked"}
    if not publish:
        state = "private_draft_only"
        reason = "publish=false; listing remains private."
    elif not owner_confirmed:
        state = "blocked_owner_confirmation_required"
        reason = "owner_confirmed=false; owner confirmation is required before visibility."
    elif blocked:
        state = "blocked_by_membra_packet"
        reason = "MEMBRA packet requires proof/compliance resolution before publication."
    else:
        state = "publication_eligible"
        reason = "Owner confirmed and packet does not block publication."
    return {
        "publication_state": state,
        "publication_allowed": state == "publication_eligible",
        "reason": reason,
        "owner_confirmed": owner_confirmed,
        "publish_requested": publish,
        "risk_tier": risk_tier,
        "review_actions": review_actions,
    }


NODE_EXECUTORS: dict[str, Callable[[dict[str, Any], LLMCallable | None], dict[str, Any]]] = {
    "ingestion_context": node_ingestion_context,
    "image_forensics": node_image_forensics,
    "sku_hypothesis": node_sku_hypothesis,
    "proof_gap_analysis": node_proof_gap_analysis,
    "listing_enrichment": node_listing_enrichment,
    "risk_review": node_risk_review,
    "operator_decision": node_operator_decision,
    "publication_gate": node_publication_gate,
}


class MembraDagRunner:
    """Small auditable DAG runner for MEMBRA listing intelligence."""

    def __init__(self, graph: Iterable[DagNodeSpec] | None = None, llm: LLMCallable | None = None):
        self.graph = list(graph or MEMBRA_LISTING_DAG)
        self.llm = llm

    def validate_graph(self) -> None:
        ids = {node.node_id for node in self.graph}
        for node in self.graph:
            missing = [dep for dep in node.depends_on if dep not in ids]
            if missing:
                raise ValueError(f"Node {node.node_id} has missing dependencies: {missing}")

    def run(self, initial_context: dict[str, Any]) -> DagExecutionResult:
        self.validate_graph()
        started = now_ms()
        context = dict(initial_context)
        outputs: dict[str, Any] = {}
        node_runs: list[DagNodeRun] = []
        status = DagStatus.SUCCEEDED

        for node in self.graph:
            run = DagNodeRun(node_id=node.node_id, kind=node.kind.value, status=DagStatus.RUNNING, started_at_ms=now_ms())
            run.input_hash = stable_hash({key: context.get(key) for key in sorted(context.keys())})
            try:
                for dep in node.depends_on:
                    if dep not in outputs:
                        raise ValueError(f"Dependency {dep} did not produce output before {node.node_id}")
                require_inputs(context, node)
                executor = NODE_EXECUTORS[node.node_id]
                output = executor(context, self.llm)
                outputs[node.output_key or node.node_id] = output
                context[node.output_key or node.node_id] = output
                run.output_hash = stable_hash(output)
                run.status = DagStatus.SUCCEEDED
            except Exception as exc:
                run.status = DagStatus.FAILED
                run.error = str(exc)
                status = DagStatus.FAILED
                outputs[node.output_key or node.node_id] = {"error": str(exc)}
                context[node.output_key or node.node_id] = outputs[node.output_key or node.node_id]
                # Stop at first failure; downstream decisions should not run on corrupt state.
                run.finished_at_ms = now_ms()
                run.duration_ms = run.finished_at_ms - (run.started_at_ms or run.finished_at_ms)
                node_runs.append(run)
                break
            run.finished_at_ms = now_ms()
            run.duration_ms = run.finished_at_ms - (run.started_at_ms or run.finished_at_ms)
            node_runs.append(run)

        finished = now_ms()
        dag_payload = {
            "graph_version": GRAPH_VERSION,
            "initial_context_hash": stable_hash(initial_context),
            "outputs": outputs,
            "node_runs": [r.to_dict() for r in node_runs],
            "status": status.value,
        }
        dag_id = f"mdag_{stable_hash(dag_payload, 16)}"
        audit_hash = stable_hash({"dag_id": dag_id, **dag_payload}, 64)
        return DagExecutionResult(
            dag_id=dag_id,
            status=status.value,
            graph_version=GRAPH_VERSION,
            created_at_ms=started,
            finished_at_ms=finished,
            duration_ms=finished - started,
            node_runs=[r.to_dict() for r in node_runs],
            outputs=outputs,
            audit_hash=audit_hash,
            safety={
                "owner_approval_required": True,
                "earnings_not_guaranteed": True,
                "external_settlement_required": True,
                "non_custodial": True,
                "no_private_keys": True,
            },
        )


def run_membra_listing_dag(payload: dict[str, Any], llm: LLMCallable | None = None) -> dict[str, Any]:
    """Convenience API for running the proprietary listing DAG."""
    return MembraDagRunner(llm=llm).run(payload).to_dict()
