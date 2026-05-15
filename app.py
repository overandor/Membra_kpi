"""MEMBRA KPI — production-hardened Replit AI Assetification Marketplace."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
import stripe
import uvicorn
from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image
from starlette.middleware.trustedhost import TrustedHostMiddleware

from membra_kpi.assetification import assetify_from_context
from membra_kpi.deep_backend import BackendContext, apply_deep_backend_schema, backend_status, verify_chain
from membra_kpi.marketplace import confirm_visibility, create_listing_draft, request_visibility
from membra_kpi.product_router import build_product_router
from membra_kpi.proofbook import create_proof_entry, sha256_payload
from membra_kpi.security import apply_security_headers, enforce_rate_limit, validate_data_upload, validate_image_upload, verify_admin_token
from membra_kpi.solana_devnet import anchor_listing_on_solana_devnet, solana_devnet_status

APP_NAME = "MEMBRA KPI Assetification Marketplace"
APP_VERSION = "1.3.0"
APP_ENV = os.getenv("APP_ENV", "development")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000").rstrip("/")
DB_PATH = Path(os.getenv("DB_PATH", "./data/membra.db"))
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./static/uploads"))
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "change-me")
ADMIN_TOKEN_SHA256 = os.getenv("ADMIN_TOKEN_SHA256", "")
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "*").split(",") if h.strip()]
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "")
stripe.api_key = STRIPE_SECRET_KEY or None

DB_PATH.parent.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title=APP_NAME, version=APP_VERSION)
if ALLOWED_HOSTS != ["*"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.middleware("http")
async def security_middleware(request: Request, call_next):
    enforce_rate_limit(request)
    response = await call_next(request)
    apply_security_headers(response)
    return response

def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()

def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def rows(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with db() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]

def one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    with db() as conn:
        r = conn.execute(sql, params).fetchone()
        return dict(r) if r else None

def execute(sql: str, params: tuple[Any, ...] = ()) -> None:
    with db() as conn:
        conn.execute(sql, params)

def init_db() -> None:
    with db() as conn:
        conn.executescript("""
CREATE TABLE IF NOT EXISTS photos(photo_id TEXT PRIMARY KEY, owner_id TEXT, filename TEXT, file_path TEXT, content_type TEXT, width INTEGER, height INTEGER, room_type TEXT, monetization_goal TEXT, user_notes TEXT, location_hint TEXT, room_summary TEXT, status TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS inventory_items(inventory_item_id TEXT PRIMARY KEY, source_photo_id TEXT, owner_id TEXT, sku TEXT, detected_name TEXT, asset_type TEXT, visual_evidence TEXT, monetization_type TEXT, listing_type TEXT, description TEXT, suggested_price_low REAL, suggested_price_high REAL, pricing_unit TEXT, confidence REAL, kpi_score INTEGER, proof_required_json TEXT, risk_flags_json TEXT, recommended_action TEXT, status TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS sku_map(sku TEXT PRIMARY KEY, inventory_item_id TEXT, category TEXT, title TEXT, status TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS listing_drafts(listing_id TEXT PRIMARY KEY, inventory_item_id TEXT, sku TEXT, title TEXT, description TEXT, listing_type TEXT, suggested_price_low REAL, suggested_price_high REAL, pricing_unit TEXT, status TEXT, owner_visibility_requested_at TEXT, owner_confirmed_at TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS public_listings(public_listing_id TEXT PRIMARY KEY, listing_id TEXT, sku TEXT, title TEXT, description TEXT, price_low REAL, price_high REAL, pricing_unit TEXT, visibility_status TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS kpi_cards(kpi_id TEXT PRIMARY KEY, source_photo_id TEXT, inventory_item_id TEXT, title TEXT, value TEXT, score INTEGER, category TEXT, explanation TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS proofbook_entries(proof_id TEXT PRIMARY KEY, subject_type TEXT, subject_id TEXT, event_type TEXT, proof_hash TEXT, metadata_json TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS kpi_uploads(upload_id TEXT PRIMARY KEY, filename TEXT, row_count INTEGER, column_count INTEGER, summary_json TEXT, suggested_kpis_json TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS wallet_events(ledger_event_id TEXT PRIMARY KEY, user_id TEXT, subject_type TEXT, subject_id TEXT, amount_usd REAL, event_type TEXT, status TEXT, metadata_json TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS payout_eligibility(payout_event_id TEXT PRIMARY KEY, user_id TEXT, subject_type TEXT, subject_id TEXT, eligible_amount_usd REAL, eligibility_reason TEXT, status TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS admin_decisions(decision_id TEXT PRIMARY KEY, subject_type TEXT, subject_id TEXT, decision TEXT, operator TEXT, risk_level TEXT, notes TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS marketplace_events(event_id TEXT PRIMARY KEY, listing_id TEXT, event_type TEXT, metadata_json TEXT, created_at TEXT);
""")
        apply_deep_backend_schema(conn)

init_db()
app.include_router(build_product_router(db))

def insert_proof(subject_type: str, subject_id: str, event_type: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    entry = create_proof_entry(subject_type, subject_id, event_type, metadata or {})
    row = entry.to_row()
    execute("INSERT INTO proofbook_entries(proof_id,subject_type,subject_id,event_type,proof_hash,metadata_json,created_at) VALUES(?,?,?,?,?,?,?)", (row["proof_id"], row["subject_type"], row["subject_id"], row["event_type"], row["proof_hash"], row["metadata_json"], row["created_at"]))
    return row

def require_admin(token: str | None) -> None:
    if not verify_admin_token(token, plain_token=ADMIN_TOKEN, token_hash=ADMIN_TOKEN_SHA256 or None):
        raise HTTPException(status_code=401, detail="Valid admin token required")

def dashboard_payload() -> dict[str, Any]:
    return {"counts": {"photos": one("SELECT COUNT(*) c FROM photos")["c"], "inventory": one("SELECT COUNT(*) c FROM inventory_items")["c"], "drafts": one("SELECT COUNT(*) c FROM listing_drafts")["c"], "public_listings": one("SELECT COUNT(*) c FROM public_listings")["c"], "kpis": one("SELECT COUNT(*) c FROM kpi_cards")["c"], "proofs": one("SELECT COUNT(*) c FROM proofbook_entries")["c"]}}

def page(request: Request, name: str, **context: Any) -> HTMLResponse:
    return templates.TemplateResponse(name, {"request": request, "app_name": APP_NAME, "app_env": APP_ENV, **context})

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return page(request, "index.html", dashboard=dashboard_payload())

@app.get("/api/health")
def health():
    return {"ok": True, "app": APP_NAME, "version": APP_VERSION, "env": APP_ENV, "product_router_mounted": True}

@app.get("/api/ready")
def ready():
    warnings = []
    if ADMIN_TOKEN in {"", "change-me"} and not ADMIN_TOKEN_SHA256:
        warnings.append("ADMIN_TOKEN is default")
    if not STRIPE_SECRET_KEY:
        warnings.append("Stripe not configured; eligibility records only")
    return {"ok": True, "counts": dashboard_payload()["counts"], "deep_backend": api_deep_backend_status(), "solana_devnet": solana_devnet_status(), "warnings": warnings}

@app.get("/api/deep-backend/status")
def api_deep_backend_status():
    with db() as conn:
        return backend_status(conn)

@app.get("/api/solana/devnet/status")
def api_solana_status():
    return solana_devnet_status()

@app.post("/api/listings/{listing_id}/anchor-devnet")
def api_anchor_listing_devnet(listing_id: str, x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    listing = one("SELECT * FROM public_listings WHERE listing_id=? OR public_listing_id=?", (listing_id, listing_id))
    if not listing:
        draft = one("SELECT * FROM listing_drafts WHERE listing_id=?", (listing_id,))
        if not draft:
            raise HTTPException(404, "Listing not found")
        listing = draft
    proof = insert_proof("listing", listing_id, "solana_devnet_anchor_requested", {"network": "solana-devnet"})
    with db() as conn:
        context = BackendContext(actor_id="admin", role="platform_admin")
        result = anchor_listing_on_solana_devnet(conn, context, listing, proof_hash=proof["proof_hash"])
    return {"success": result.get("error") is None, "anchor": result}

@app.get("/api/proofbook/chain")
def api_proofbook_chain():
    with db() as conn:
        return verify_chain(conn)

@app.get("/api/dashboard")
def api_dashboard():
    return dashboard_payload()

@app.get("/api/listings/public")
def api_public_listings():
    return {"public_listings": rows("SELECT * FROM public_listings ORDER BY created_at DESC")}

@app.get("/api/listings/drafts")
def api_listing_drafts():
    return {"drafts": rows("SELECT * FROM listing_drafts ORDER BY created_at DESC")}

@app.get("/api/proofbook")
def api_proofbook():
    return {"proofbook": rows("SELECT * FROM proofbook_entries ORDER BY created_at DESC"), "chain": api_proofbook_chain()}

@app.post("/api/listings/{listing_id}/request-visibility")
def api_request_visibility(listing_id: str):
    draft = one("SELECT * FROM listing_drafts WHERE listing_id=?", (listing_id,))
    if not draft:
        raise HTTPException(404, "Draft listing not found")
    updated = request_visibility(draft)
    execute("UPDATE listing_drafts SET status=?, owner_visibility_requested_at=? WHERE listing_id=?", (updated["status"], updated["owner_visibility_requested_at"], listing_id))
    insert_proof("listing", listing_id, "visibility_requested", {"status": updated["status"]})
    return {"success": True, "listing": updated}

@app.post("/api/listings/{listing_id}/confirm-visibility")
def api_confirm_visibility(listing_id: str):
    draft = one("SELECT * FROM listing_drafts WHERE listing_id=?", (listing_id,))
    if not draft:
        raise HTTPException(404, "Draft listing not found")
    updated, public = confirm_visibility(draft)
    p = public.to_dict()
    execute("UPDATE listing_drafts SET status=?, owner_confirmed_at=? WHERE listing_id=?", (updated["status"], updated["owner_confirmed_at"], listing_id))
    execute("INSERT INTO public_listings VALUES(?,?,?,?,?,?,?,?,?,?)", (p["public_listing_id"], p["listing_id"], p["sku"], p["title"], p["description"], p["price_low"], p["price_high"], p["pricing_unit"], p["visibility_status"], p["created_at"]))
    insert_proof("listing", listing_id, "visibility_confirmed", {"public_listing_id": p["public_listing_id"]})
    return {"success": True, "listing": updated, "public_listing": p}

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=False)
