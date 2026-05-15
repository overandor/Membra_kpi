from membra_kpi.golden_prime_decision import (
    PHI,
    golden_weighted_score,
    rank_decision_candidates,
    workflow_step_schedule,
    DecisionCandidate,
)


def test_golden_weighted_score_bounds():
    candidate = DecisionCandidate(
        candidate_id="c1",
        label="High proof listing route",
        utility_score=88,
        confidence_score=80,
        novelty_score=70,
        proof_score=92,
        risk_score=15,
        metadata={},
    )
    score = golden_weighted_score(candidate)
    assert 0 <= score <= 100


def test_rank_decision_candidates_selects_top():
    decision = rank_decision_candidates([
        {"candidate_id": "a", "label": "Safe proven", "utility_score": 90, "confidence_score": 90, "novelty_score": 50, "proof_score": 95, "risk_score": 10},
        {"candidate_id": "b", "label": "Risky novel", "utility_score": 70, "confidence_score": 50, "novelty_score": 99, "proof_score": 40, "risk_score": 80},
    ])
    assert decision["selected"] is not None
    assert decision["selected"]["candidate_id"] == "a"
    assert decision["method"] == "golden_ratio_weighting_with_prime_gap_anti_crowding"


def test_workflow_step_schedule_is_prime_gap_structured():
    schedule = workflow_step_schedule(5)
    assert len(schedule) == 5
    assert schedule[0]["prime"] == 2
    assert schedule[0]["recommended_cadence_seconds"] > 0
    assert 1.61 < PHI < 1.62
