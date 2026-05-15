"""MEMBRA Inverted LLM orchestration core.

MEMBRA = Memory-Evaluated Multi-agent Backpropagating Runtime Architecture.

This is not a base model. It is an orchestration learner: it treats LLMs,
public APIs, KPI factories, ProofBook, DataBits, and workers as tools, then
learns from task outcomes by promoting successful patterns and turning failures
into guardrails.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .deep_backend import BackendContext, append_chain_event, canonical_json, sha256_text, utc_now
from .huggingface_endpoints import build_hf_bundle_for_listing
from .infinite_kpi import build_infinite_kpi_production_plan
from .microoverworker import build_microoverworker_plan
from .sentence_as_service import build_sentence_product


@dataclass(frozen=True, slots=True)
class OrchestrationSkill:
    skill_id: str
    name: str
    tools: list[str]
    success_metric: str
    failure_metric: str
    default_weight: float


SKILLS: list[OrchestrationSkill] = [
    OrchestrationSkill("semantic_route", "Semantic Route Selection", ["huggingface_embeddings", "transformers_js", "proofbook_memory"], "answer_relevance", "hallucination_or_missing_context", 0.82),
    OrchestrationSkill("kpi_factory", "KPI Factory Planning", ["infinite_kpi", "public_sources", "microoverworker"], "useful_kpi_count", "duplicate_or_low_signal_kpis", 0.88),
    OrchestrationSkill("proof_guard", "ProofBook Guard", ["proofbook", "object_registry", "chain_verify"], "chain_integrity", "unverifiable_claim", 0.95),
    OrchestrationSkill("sentence_pack", "Sentence Packaging", ["sentence_as_service", "language_fi", "databits"], "compressed_value_clarity", "generic_sentence", 0.8),
    OrchestrationSkill("worker_delegate", "Worker Delegation", ["llm_employees", "partner_endpoints", "hf_plans"], "task_completion", "wrong_worker_or_tool", 0.78),
]


def skill_registry() -> dict[str, Any]:
    return {"system": "MEMBRA inverted LLM", "skills": [asdict(s) for s in SKILLS]}


def build_inverted_llm_plan(*, objective: str, listing: dict[str, Any] | None = None, context: dict[str, Any] | None = None) -> dict[str, Any]:
    listing = listing or {"title": "MEMBRA orchestration subject", "description": objective}
    context = context or {}
    seed = {"objective": objective, "listing": listing, "context": context, "created_at": utc_now()}
    return {
        "plan_id": "membra_inv_" + sha256_text(canonical_json(seed))[:24],
        "created_at": seed["created_at"],
        "name": "MEMBRA Inverted LLM",
        "objective": objective,
        "listing_context": listing,
        "context": context,
        "skills": skill_registry()["skills"],
        "orchestration_steps": [
            {"step": 1, "action": "retrieve_context", "tools": ["ProofBook", "DataBits", "KPI observations"]},
            {"step": 2, "action": "select_workers", "tools": ["MicroOverWorker", "LLM employees"]},
            {"step": 3, "action": "plan_inference", "tools": ["Hugging Face", "Groq", "Ollama", "Transformers.js"]},
            {"step": 4, "action": "score_outputs", "tools": ["Infinite KPI", "ProofBook", "review labels"]},
            {"step": 5, "action": "store_outcome", "tools": ["ProofBook", "strategy memory"]},
            {"step": 6, "action": "promote_successful_pattern", "tools": ["success registry", "negative examples"]},
        ],
        "microoverworker_plan": build_microoverworker_plan(listing=listing, objective=objective),
        "kpi_success_plan": build_infinite_kpi_production_plan(listing=listing, objective=f"measure success for: {objective}"),
        "huggingface_bundle": build_hf_bundle_for_listing(listing),
        "sentence_product": build_sentence_product(listing=listing),
        "learning_policy": {
            "learns_from": ["human_approval", "admin_review", "KPI_improvement", "ProofBook_integrity", "task_completion", "provider_success"],
            "does_not_do": ["train_base_model_weights", "claim_self_awareness", "ignore_review", "execute_unconfigured_providers"],
            "success_threshold": 0.78,
            "failure_creates_guardrail": True,
        },
        "execution_mode": "orchestration_plan_until_worker_runtime_executes",
        "review_required": True,
    }


def score_orchestration_outcome(plan: dict[str, Any], outcome: dict[str, Any]) -> dict[str, Any]:
    human = 1.0 if outcome.get("human_approved") else 0.0
    proof = 1.0 if outcome.get("proofbook_valid", True) else 0.0
    completed = 1.0 if outcome.get("task_completed") else 0.0
    kpi_delta = float(outcome.get("kpi_delta", 0.0))
    provider_success = 1.0 if outcome.get("provider_success", True) else 0.0
    score = round((human * 0.25) + (proof * 0.25) + (completed * 0.2) + (provider_success * 0.15) + (max(min(kpi_delta, 1), -1) * 0.15), 4)
    threshold = plan.get("learning_policy", {}).get("success_threshold", 0.78)
    return {
        "plan_id": plan["plan_id"],
        "outcome_score": score,
        "status": "promote_pattern" if score >= threshold else "create_guardrail",
        "features": {"human_approved": human, "proofbook_valid": proof, "task_completed": completed, "provider_success": provider_success, "kpi_delta": kpi_delta},
        "created_at": utc_now(),
    }


def record_inverted_llm_plan(conn, context: BackendContext, plan: dict[str, Any]) -> dict[str, Any]:
    return append_chain_event(conn, context, "inverted_llm_plan", plan["plan_id"], "membra_inverted_llm.plan_created", plan)


def record_inverted_llm_outcome(conn, context: BackendContext, plan: dict[str, Any], outcome: dict[str, Any]) -> dict[str, Any]:
    scored = score_orchestration_outcome(plan, outcome)
    return append_chain_event(conn, context, "inverted_llm_outcome", plan["plan_id"], "membra_inverted_llm.outcome_scored", scored)


def create_inverted_llm_plan(conn, *, context: BackendContext, objective: str, listing: dict[str, Any] | None = None, extra_context: dict[str, Any] | None = None) -> dict[str, Any]:
    plan = build_inverted_llm_plan(objective=objective, listing=listing, context=extra_context)
    event = record_inverted_llm_plan(conn, context, plan)
    return {"success": True, "inverted_llm_plan": plan, "proofbook_event": event}
