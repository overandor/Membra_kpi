"""MEMBRA orchestration DAG runtime primitives.

This module turns MEMBRA's orchestration ideas into explicit directed workflow
plans. It combines:
- inverted LLM objectives
- golden-ratio candidate ranking
- prime-gap retry/cadence spacing
- KPI success hooks
- ProofBook event lineage

No worker is executed here. The DAG is plan-first and worker-safe.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .deep_backend import BackendContext, append_chain_event, canonical_json, sha256_text, utc_now
from .golden_prime_decision import rank_decision_candidates, workflow_step_schedule
from .inverted_llm import build_inverted_llm_plan, score_orchestration_outcome


@dataclass(frozen=True, slots=True)
class OrchestrationNode:
    node_id: str
    node_type: str
    label: str
    worker_role: str
    inputs: list[str]
    outputs: list[str]
    retry_policy: dict[str, Any]
    success_metric: str
    metadata: dict[str, Any]


def default_node_templates() -> list[dict[str, Any]]:
    return [
        {"node_type": "retrieve", "label": "Retrieve ProofBook and DataBit context", "worker_role": "retrieval_worker", "success_metric": "context_relevance"},
        {"node_type": "rank", "label": "Rank route candidates with golden-prime engine", "worker_role": "orchestration_ranker", "success_metric": "route_quality"},
        {"node_type": "infer", "label": "Plan model/provider inference", "worker_role": "provider_worker", "success_metric": "provider_success"},
        {"node_type": "score", "label": "Score outcome with Infinite KPI", "worker_role": "kpi_worker", "success_metric": "kpi_delta"},
        {"node_type": "verify", "label": "Verify ProofBook and review caveats", "worker_role": "proof_reviewer", "success_metric": "proofbook_valid"},
        {"node_type": "promote", "label": "Promote pattern or create guardrail", "worker_role": "strategy_memory_worker", "success_metric": "pattern_quality"},
    ]


def build_orchestration_dag(*, objective: str, listing: dict[str, Any] | None = None, context: dict[str, Any] | None = None) -> dict[str, Any]:
    listing = listing or {"title": "MEMBRA DAG subject", "description": objective}
    context = context or {}
    inverted_plan = build_inverted_llm_plan(objective=objective, listing=listing, context=context)
    schedule = workflow_step_schedule(len(default_node_templates()))
    nodes: list[dict[str, Any]] = []
    previous_output = "objective"
    for idx, template in enumerate(default_node_templates()):
        seed = {"objective": objective, "idx": idx, "template": template, "listing": listing}
        node = OrchestrationNode(
            node_id="node_" + sha256_text(canonical_json(seed))[:18],
            node_type=template["node_type"],
            label=template["label"],
            worker_role=template["worker_role"],
            inputs=[previous_output],
            outputs=[f"{template['node_type']}_output"],
            retry_policy={
                "prime": schedule[idx]["prime"],
                "prime_gap": schedule[idx]["prime_gap"],
                "recommended_cadence_seconds": schedule[idx]["recommended_cadence_seconds"],
                "max_attempts": 3,
            },
            success_metric=template["success_metric"],
            metadata={"golden_phase": schedule[idx]["golden_phase"]},
        )
        previous_output = node.outputs[0]
        nodes.append(asdict(node))
    candidates = [
        {"candidate_id": n["node_id"], "label": n["label"], "utility_score": 78 + i, "confidence_score": 75, "novelty_score": 70 + (i * 2), "proof_score": 80, "risk_score": 20, "metadata": {"node_type": n["node_type"]}}
        for i, n in enumerate(nodes)
    ]
    route_decision = rank_decision_candidates(candidates)
    dag_seed = {"objective": objective, "listing": listing, "nodes": [n["node_id"] for n in nodes], "created_at": utc_now()}
    return {
        "dag_id": "dag_" + sha256_text(canonical_json(dag_seed))[:24],
        "created_at": dag_seed["created_at"],
        "objective": objective,
        "listing_context": listing,
        "context": context,
        "nodes": nodes,
        "edges": [{"from": nodes[i]["node_id"], "to": nodes[i + 1]["node_id"]} for i in range(len(nodes) - 1)],
        "route_decision": route_decision,
        "inverted_llm_plan": inverted_plan,
        "execution_mode": "dag_plan_only_until_worker_runtime_executes",
        "worker_requirements": ["queue", "retry_manager", "proofbook_writer", "kpi_observer", "strategy_memory"],
        "review_required": True,
    }


def score_dag_outcome(dag: dict[str, Any], node_outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    if not node_outcomes:
        return {"dag_id": dag["dag_id"], "score": 0, "status": "no_outcomes"}
    completed = sum(1 for o in node_outcomes if o.get("task_completed")) / len(node_outcomes)
    proof = sum(1 for o in node_outcomes if o.get("proofbook_valid", True)) / len(node_outcomes)
    provider = sum(1 for o in node_outcomes if o.get("provider_success", True)) / len(node_outcomes)
    avg_delta = sum(float(o.get("kpi_delta", 0)) for o in node_outcomes) / len(node_outcomes)
    score = round((completed * 0.32) + (proof * 0.28) + (provider * 0.2) + (max(min(avg_delta, 1), -1) * 0.2), 4)
    return {
        "dag_id": dag["dag_id"],
        "score": score,
        "status": "promote_dag_pattern" if score >= 0.78 else "create_dag_guardrail",
        "node_count": len(node_outcomes),
        "created_at": utc_now(),
    }


def record_orchestration_dag(conn, context: BackendContext, dag: dict[str, Any]) -> dict[str, Any]:
    return append_chain_event(conn, context, "orchestration_dag", dag["dag_id"], "orchestration.dag_created", dag)


def record_dag_outcome(conn, context: BackendContext, dag: dict[str, Any], node_outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    scored = score_dag_outcome(dag, node_outcomes)
    return append_chain_event(conn, context, "orchestration_dag", dag["dag_id"], "orchestration.dag_outcome_scored", scored)


def create_orchestration_dag(conn, *, context: BackendContext, objective: str, listing: dict[str, Any] | None = None, extra_context: dict[str, Any] | None = None) -> dict[str, Any]:
    dag = build_orchestration_dag(objective=objective, listing=listing, context=extra_context)
    event = record_orchestration_dag(conn, context, dag)
    return {"success": True, "orchestration_dag": dag, "proofbook_event": event}
