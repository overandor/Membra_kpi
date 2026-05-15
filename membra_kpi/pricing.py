"""Pricing primitives for MEMBRA KPI assetification.

The values here are conservative demo defaults. They are not earnings guarantees.
Production pricing should incorporate location, supply/demand, trust score, proof
quality, insurance constraints, local rules, and marketplace liquidity.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PriceBand:
    low: float
    high: float
    unit: str = "monthly"

    def midpoint(self) -> float:
        return round((self.low + self.high) / 2, 2)


BASE_PRICE_BANDS: dict[str, PriceBand] = {
    "SEAT": PriceBand(40, 180, "monthly"),
    "WORK": PriceBand(75, 350, "monthly"),
    "STORAGE": PriceBand(12, 80, "monthly"),
    "TOOL": PriceBand(5, 45, "daily"),
    "WINDOW": PriceBand(70, 180, "monthly"),
    "CARAD": PriceBand(120, 420, "monthly"),
    "WEAR": PriceBand(30, 90, "monthly"),
    "RELAY": PriceBand(4, 25, "per job"),
    "PANTRY": PriceBand(10, 75, "bundle"),
    "RESALE": PriceBand(15, 160, "bundle"),
    "PARKING": PriceBand(60, 300, "monthly"),
    "WALLAD": PriceBand(50, 160, "monthly"),
    "TASK": PriceBand(15, 120, "per task"),
    "CAMPAIGN": PriceBand(100, 500, "monthly"),
}

LOCATION_MULTIPLIERS = {
    "downtown": 1.25,
    "urban": 1.15,
    "campus": 1.12,
    "suburban": 1.0,
    "rural": 0.82,
    "local": 1.0,
    "unknown": 1.0,
}


def normalize_category(category: str) -> str:
    return (category or "STORAGE").strip().upper().replace("-", "_")


def location_multiplier(location_hint: str | None) -> float:
    text = (location_hint or "unknown").lower()
    for key, value in LOCATION_MULTIPLIERS.items():
        if key in text:
            return value
    return 1.0


def price_band_for(category: str, *, location_hint: str | None = None, confidence: float = 0.75) -> PriceBand:
    category = normalize_category(category)
    base = BASE_PRICE_BANDS.get(category, BASE_PRICE_BANDS["STORAGE"])
    loc = location_multiplier(location_hint)
    confidence = max(0.35, min(float(confidence or 0.75), 0.98))
    uncertainty_discount = 0.82 + (confidence * 0.18)
    low = round(base.low * loc * uncertainty_discount, 2)
    high = round(base.high * loc * (0.95 + confidence * 0.12), 2)
    return PriceBand(low=low, high=max(high, low), unit=base.unit)


def earnings_label(category: str, *, location_hint: str | None = None, confidence: float = 0.75) -> str:
    band = price_band_for(category, location_hint=location_hint, confidence=confidence)
    return f"${band.low:,.0f}–${band.high:,.0f} / {band.unit}"
