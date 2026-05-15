"""LLM concierge for MEMBRA KPI.

The concierge is production-oriented:
- Uses live provider APIs when GROQ_API_KEY or OPENAI_API_KEY is configured.
- Falls back to deterministic, transparent routing guidance when no provider is configured.
- Never invents dashboard records; it reads current database counts and recent rows.
"""
from __future__ import annotations

import os
import sqlite3
from typing import Any

import httpx

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))

SYSTEM_PROMPT = """You are MEMBRA Concierge, the operating assistant for MEMBRA KPI.
Your job is to help a user turn permitted apartment, car, window, wearable, storage, tool, or local handoff data into structured inventory, KPI insight, proof records, private drafts, and owner-confirmed marketplace actions.
Rules:
- Do not promise income, yield, settlement, legal approval, or payment.
- State when owner confirmation, proof, lease/local review, or external rails are required.
- Never ask for private keys, seed phrases, raw credentials, or unconsented personal data.
- Prefer concrete next actions that map to existing MEMBRA endpoints and dashboard panels.
- If data is missing, ask for the minimum needed input.
"""


def _row_count(conn: sqlite3.Connection, table: str) -> int:
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    except Exception:
        return 0


def dashboard_context(conn: sqlite3.Connection) -> dict[str, Any]:
    counts = {
        "photos": _row_count(conn, "photos"),
        "inventory_items": _row_count(conn, "inventory_items"),
        "listing_drafts": _row_count(conn, "listing_drafts"),
        "public_listings": _row_count(conn, "public_listings"),
        "kpi_cards": _row_count(conn, "kpi_cards"),
        "proofbook_entries": _row_count(conn, "proofbook_entries"),
        "event_outbox": _row_count(conn, "event_outbox"),
    }
    recent: dict[str, Any] = {}
    for table in ["photos", "inventory_items", "listing_drafts", "public_listings", "proofbook_entries"]:
        try:
            rows = conn.execute(f"SELECT * FROM {table} ORDER BY created_at DESC LIMIT 3").fetchall()
            recent[table] = [dict(row) for row in rows]
        except Exception:
            recent[table] = []
    return {"counts": counts, "recent": recent}


def recommended_actions(message: str, context: dict[str, Any]) -> list[dict[str, str]]:
    text = message.lower()
    actions: list[dict[str, str]] = []
    if any(word in text for word in ["photo", "picture", "scan", "apartment", "window", "car", "wear", "storage", "tool"]):
        actions.append({"label": "Upload proof photo", "endpoint": "POST /api/photo/analyze", "panel": "Dashboard → Upload proof photo"})
    if any(word in text for word in ["kpi", "csv", "spreadsheet", "analysis", "data"]):
        actions.append({"label": "Upload KPI dataset", "endpoint": "POST /api/kpi/upload", "panel": "Dashboard/API"})
    if context.get("counts", {}).get("listing_drafts", 0):
        actions.append({"label": "Request owner visibility", "endpoint": "POST /api/listings/{listing_id}/request-visibility", "panel": "Draft listings"})
    if context.get("counts", {}).get("event_outbox", 0):
        actions.append({"label": "Replay event outbox", "endpoint": "POST /api/events/outbox/replay", "panel": "Event outbox"})
    if not actions:
        actions.append({"label": "Start with a proof photo", "endpoint": "POST /api/photo/analyze", "panel": "Dashboard → Upload proof photo"})
    return actions[:4]


def deterministic_response(message: str, context: dict[str, Any]) -> str:
    counts = context.get("counts", {})
    base = [
        "MEMBRA can help structure this into a permissioned assetification workflow.",
        f"Current system state: {counts.get('photos', 0)} photo proofs, {counts.get('inventory_items', 0)} inventory items, {counts.get('listing_drafts', 0)} private drafts, {counts.get('public_listings', 0)} public listings, and {counts.get('proofbook_entries', 0)} ProofBook records.",
        "Best next step: upload a real proof photo or KPI dataset, then review the generated private drafts before any owner-confirmed marketplace visibility.",
        "Boundary: MEMBRA records proof, listings, analytics, and payout eligibility only. External rails settle money, and local/lease rules still apply.",
    ]
    if "window" in message.lower():
        base.insert(2, "For first-floor windows, treat the surface as a review-gated ad asset: prove control, capture visibility context, then require building/local-rule review before public listing.")
    if "car" in message.lower():
        base.insert(2, "For car ad space, treat the vehicle surface as a route-aware media asset with proof, owner consent, campaign fit, and safety review.")
    if "wear" in message.lower():
        base.insert(2, "For wear ads, use a consented wearable QR/media kit and keep campaign acceptance explicit.")
    return "\n\n".join(base)


async def call_llm_provider(message: str, context: dict[str, Any]) -> tuple[str, str]:
    payload = {
        "model": GROQ_MODEL if GROQ_API_KEY else OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Dashboard context: {context}\n\nUser request: {message}"},
        ],
        "temperature": 0.35,
        "max_tokens": 650,
    }
    if GROQ_API_KEY:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT_SECONDS) as client:
            res = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
            res.raise_for_status()
            data = res.json()
            return data["choices"][0]["message"]["content"], f"groq:{GROQ_MODEL}"
    if OPENAI_API_KEY:
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT_SECONDS) as client:
            res = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            res.raise_for_status()
            data = res.json()
            return data["choices"][0]["message"]["content"], f"openai:{OPENAI_MODEL}"
    return deterministic_response(message, context), "deterministic:no_provider_configured"


async def concierge_reply(conn: sqlite3.Connection, message: str, client_context: dict[str, Any] | None = None) -> dict[str, Any]:
    message = (message or "").strip()
    if not message:
        return {"ok": False, "error": "message is required"}
    context = dashboard_context(conn)
    if client_context:
        context["client_context"] = client_context
    try:
        answer, provider = await call_llm_provider(message, context)
    except Exception as exc:
        answer = deterministic_response(message, context)
        provider = f"fallback_after_provider_error:{type(exc).__name__}"
    return {
        "ok": True,
        "provider": provider,
        "answer": answer,
        "actions": recommended_actions(message, context),
        "dashboard_context": context,
        "safety": {
            "income_guarantee": False,
            "custody": False,
            "requires_owner_confirmation": True,
            "requires_external_settlement": True,
        },
    }
