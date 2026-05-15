"""KPI scoring engine for MEMBRA assetification records."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class KpiCard:
    title: str
    value: str
    score: int
    category: str
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def clamp_score(value: float) -> int:
    return int(max(0, min(100, round(value))))


def readiness_score(*, confidence: float, risk_flags: list[str] | None = None, proof_required: list[str] | None = None) -> int:
    risk_flags = risk_flags or []
    proof_required = proof_required or []
    score = 45 + (float(confidence or 0.0) * 45)
    score -= min(len(risk_flags) * 7, 28)
    score -= min(max(len(proof_required) - 2, 0) * 3, 12)
    return clamp_score(score)


def proof_readiness_score(proof_required: list[str] | None = None, risk_flags: list[str] | None = None) -> int:
    proof_required = proof_required or []
    risk_flags = risk_flags or []
    score = 88 - min(len(proof_required), 8) * 4 - min(len(risk_flags), 6) * 6
    return clamp_score(score)


def risk_score(risk_flags: list[str] | None = None) -> int:
    risk_flags = risk_flags or []
    return clamp_score(18 + len(risk_flags) * 14)


def demand_match_score(category: str, location_hint: str | None = None) -> int:
    category = (category or "").upper()
    base = {
        "CARAD": 82,
        "WINDOW": 79,
        "WEAR": 68,
        "STORAGE": 74,
        "RELAY": 72,
        "WORK": 70,
        "SEAT": 64,
        "TOOL": 61,
        "PARKING": 76,
        "WALLAD": 73,
    }.get(category, 58)
    text = (location_hint or "").lower()
    if any(x in text for x in ["downtown", "campus", "main", "urban", "street"]):
        base += 8
    return clamp_score(base)


def generate_item_kpis(
    *,
    category: str,
    detected_name: str,
    confidence: float,
    price_low: float,
    price_high: float,
    pricing_unit: str,
    proof_required: list[str] | None = None,
    risk_flags: list[str] | None = None,
    location_hint: str | None = None,
) -> list[KpiCard]:
    proof_required = proof_required or []
    risk_flags = risk_flags or []
    ready = readiness_score(confidence=confidence, risk_flags=risk_flags, proof_required=proof_required)
    proof_score = proof_readiness_score(proof_required, risk_flags)
    risk = risk_score(risk_flags)
    demand = demand_match_score(category, location_hint)
    midpoint = round((float(price_low) + float(price_high)) / 2, 2)
    return [
        KpiCard("SKU readiness score", f"{ready}/100", ready, "readiness", f"{detected_name} is scored from confidence, proof needs, and risk flags."),
        KpiCard("Listing readiness score", f"{max(0, ready - 4)}/100", max(0, ready - 4), "readiness", "Draft can move toward visibility after owner confirmation and proof completion."),
        KpiCard("Proof readiness score", f"{proof_score}/100", proof_score, "proof", "Higher scores indicate fewer proof gaps before marketplace visibility."),
        KpiCard("Local demand match", f"{demand}/100", demand, "demand", "Estimated demand fit based on category and coarse location context."),
        KpiCard("Asset utilization score", f"{clamp_score((ready + demand) / 2)}/100", clamp_score((ready + demand) / 2), "utilization", "Blend of readiness and demand match."),
        KpiCard("Monthly earning estimate", f"${price_low:,.0f}–${price_high:,.0f} / {pricing_unit}", ready, "earnings", "AI-generated estimate. Not guaranteed."),
        KpiCard("Owner value score", f"{clamp_score((ready * 0.55) + (demand * 0.45))}/100", clamp_score((ready * 0.55) + (demand * 0.45)), "owner", "Potential owner value before admin review and marketplace demand are proven."),
        KpiCard("Advertiser surface value", f"{clamp_score(demand + (8 if category in {'CARAD','WINDOW','WEAR','WALLAD'} else -5))}/100", clamp_score(demand + (8 if category in {"CARAD", "WINDOW", "WEAR", "WALLAD"} else -5)), "advertising", "Relative fit for QR/NFC campaign placement."),
        KpiCard("Trust score", f"{clamp_score(92 - risk)}/100", clamp_score(92 - risk), "trust", "Trust score improves after proof verification and owner confirmation."),
        KpiCard("Risk score", f"{risk}/100", risk, "risk", "Lower is better. Risk flags require admin or owner review."),
    ]


def aggregate_dashboard(kpi_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not kpi_rows:
        return {"count": 0, "average_score": 0, "categories": {}}
    scores = [int(row.get("score", 0) or 0) for row in kpi_rows]
    categories: dict[str, int] = {}
    for row in kpi_rows:
        cat = str(row.get("category", "unknown"))
        categories[cat] = categories.get(cat, 0) + 1
    return {"count": len(kpi_rows), "average_score": clamp_score(sum(scores) / max(len(scores), 1)), "categories": categories}
