"""MEMBRA KPI — production-hardened Replit AI Assetification Marketplace.

Operational scope:
- real photo uploads become inventory, SKUs, KPI cards, ProofBook records, and private listing drafts
- owner confirmation is required before marketplace visibility
- CSV/XLSX uploads are parsed into KPI summaries
- wallet records payout eligibility only; external rails settle money

Run locally/Replit:
    uvicorn app:app --host 0.0.0.0 --port 8000
"""
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
from membra_kpi.marketplace import confirm_visibility, create_listing_draft, request_visibility
from membra_kpi.proofbook import create_proof_entry, sha256_payload
from membra_kpi.security import (
    apply_security_headers,
    enforce_rate_limit,
    validate_data_upload,
    validate_image_upload,
    verify_admin_token,
)

APP_NAME = "MEMBRA KPI Assetification Marketplace"
APP_VERSION = "1.1.0"
APP_ENV = os.getenv("APP_ENV", "development")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000").rstrip("/")
DB_PATH = Path(os.getenv("DB_PATH", "./data/membra.db"))
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./static/uploads"))
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "change-me")
ADMIN_TOKEN_SHA256 = os.getenv("ADMIN_TOKEN_SHA256", "")
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "*").split(",") if h.strip()]
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
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
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS photos(
              photo_id TEXT PRIMARY KEY, owner_id TEXT, filename TEXT, file_path TEXT,
              content_type TEXT, width INTEGER, height INTEGER, room_type TEXT,
              monetization_goal TEXT, user_notes TEXT, location_hint TEXT,
              room_summary TEXT, status TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS inventory_items(
              inventory_item_id TEXT PRIMARY KEY, source_photo_id TEXT, owner_id TEXT, sku TEXT,
              detected_name TEXT, asset_type TEXT, visual_evidence TEXT, monetization_type TEXT,
              listing_type TEXT, description TEXT, suggested_price_low REAL, suggested_price_high REAL,
              pricing_unit TEXT, confidence REAL, kpi_score INTEGER, proof_required_json TEXT,
              risk_flags_json TEXT, recommended_action TEXT, status TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS sku_map(
              sku TEXT PRIMARY KEY, inventory_item_id TEXT, category TEXT, title TEXT, status TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS listing_drafts(
              listing_id TEXT PRIMARY KEY, inventory_item_id TEXT, sku TEXT, title TEXT, description TEXT,
              listing_type TEXT, suggested_price_low REAL, suggested_price_high REAL, pricing_unit TEXT,
              status TEXT, owner_visibility_requested_at TEXT, owner_confirmed_at TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS public_listings(
              public_listing_id TEXT PRIMARY KEY, listing_id TEXT, sku TEXT, title TEXT, description TEXT,
              price_low REAL, price_high REAL, pricing_unit TEXT, visibility_status TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS kpi_cards(
              kpi_id TEXT PRIMARY KEY, source_photo_id TEXT, inventory_item_id TEXT, title TEXT,
              value TEXT, score INTEGER, category TEXT, explanation TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS proofbook_entries(
              proof_id TEXT PRIMARY KEY, subject_type TEXT, subject_id TEXT, event_type TEXT,
              proof_hash TEXT, metadata_json TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS kpi_uploads(
              upload_id TEXT PRIMARY KEY, filename TEXT, row_count INTEGER, column_count INTEGER,
              summary_json TEXT, suggested_kpis_json TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS qr_artifacts(
              artifact_id TEXT PRIMARY KEY, subject_type TEXT, subject_id TEXT, artifact_title TEXT,
              destination_url TEXT, artifact_hash TEXT, qr_url TEXT, status TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS scan_events(
              scan_id TEXT PRIMARY KEY, artifact_id TEXT, event_type TEXT, ip_hash TEXT, user_agent TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS wallet_events(
              ledger_event_id TEXT PRIMARY KEY, user_id TEXT, subject_type TEXT, subject_id TEXT,
              amount_usd REAL, event_type TEXT, status TEXT, metadata_json TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS payout_eligibility(
              payout_event_id TEXT PRIMARY KEY, user_id TEXT, subject_type TEXT, subject_id TEXT,
              eligible_amount_usd REAL, eligibility_reason TEXT, status TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS admin_decisions(
              decision_id TEXT PRIMARY KEY, subject_type TEXT, subject_id TEXT, decision TEXT,
              operator TEXT, risk_level TEXT, notes TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS ai_chat_events(
              event_id TEXT PRIMARY KEY, owner_id TEXT, message TEXT, response TEXT, metadata_json TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS marketplace_events(
              event_id TEXT PRIMARY KEY, listing_id TEXT, event_type TEXT, metadata_json TEXT, created_at TEXT
            );
            """
        )


init_db()


def insert_proof(subject_type: str, subject_id: str, event_type: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    entry = create_proof_entry(subject_type, subject_id, event_type, metadata or {})
    row = entry.to_row()
    execute(
        "INSERT INTO proofbook_entries(proof_id,subject_type,subject_id,event_type,proof_hash,metadata_json,created_at) VALUES(?,?,?,?,?,?,?)",
        (row["proof_id"], row["subject_type"], row["subject_id"], row["event_type"], row["proof_hash"], row["metadata_json"], row["created_at"]),
    )
    return row


def safe_extension(filename: str) -> str:
    suffix = Path(filename or "upload").suffix.lower()
    allowed = {".jpg", ".jpeg", ".png", ".webp", ".csv", ".xlsx", ".xls"}
    return suffix if suffix in allowed else ""


async def save_upload(file: UploadFile, prefix: str, *, kind: str) -> tuple[str, Path]:
    data = await file.read()
    if kind == "image":
        validate_image_upload(file.filename or "", file.content_type, data)
    elif kind == "data":
        validate_data_upload(file.filename or "", data)
    filename = f"{prefix}_{uuid.uuid4().hex}{safe_extension(file.filename or '')}"
    path = UPLOAD_DIR / filename
    path.write_bytes(data)
    return filename, path


def image_meta(path: Path) -> tuple[int, int]:
    try:
        with Image.open(path) as img:
            return img.size
    except Exception:
        return 0, 0


def require_admin(token: str | None) -> None:
    if not verify_admin_token(token, plain_token=ADMIN_TOKEN, token_hash=ADMIN_TOKEN_SHA256 or None):
        raise HTTPException(status_code=401, detail="Valid admin token required")


def dashboard_payload() -> dict[str, Any]:
    counts = {
        "photos": one("SELECT COUNT(*) c FROM photos")["c"],
        "inventory": one("SELECT COUNT(*) c FROM inventory_items")["c"],
        "skus": one("SELECT COUNT(*) c FROM sku_map")["c"],
        "drafts": one("SELECT COUNT(*) c FROM listing_drafts")["c"],
        "public_listings": one("SELECT COUNT(*) c FROM public_listings")["c"],
        "kpis": one("SELECT COUNT(*) c FROM kpi_cards")["c"],
        "proofs": one("SELECT COUNT(*) c FROM proofbook_entries")["c"],
        "eligible": one("SELECT COALESCE(SUM(eligible_amount_usd),0) c FROM payout_eligibility WHERE status LIKE 'eligible%'")["c"],
    }
    return {
        "counts": counts,
        "recent_inventory": rows("SELECT * FROM inventory_items ORDER BY created_at DESC LIMIT 8"),
        "recent_kpis": rows("SELECT * FROM kpi_cards ORDER BY created_at DESC LIMIT 10"),
    }


def page(request: Request, name: str, **context: Any) -> HTMLResponse:
    return templates.TemplateResponse(name, {"request": request, "app_name": APP_NAME, "app_env": APP_ENV, **context})


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return page(request, "index.html", dashboard=dashboard_payload())


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return page(request, "dashboard.html", dashboard=dashboard_payload())


@app.get("/ai", response_class=HTMLResponse)
def ai_page(request: Request):
    return page(request, "ai.html")


@app.get("/assetify", response_class=HTMLResponse)
def assetify_page(request: Request):
    return page(request, "assetify.html", photos=rows("SELECT * FROM photos ORDER BY created_at DESC LIMIT 20"))


@app.get("/kpi", response_class=HTMLResponse)
def kpi_page(request: Request):
    return page(request, "kpi.html", uploads=rows("SELECT * FROM kpi_uploads ORDER BY created_at DESC LIMIT 20"), kpis=rows("SELECT * FROM kpi_cards ORDER BY created_at DESC LIMIT 30"))


@app.get("/inventory", response_class=HTMLResponse)
def inventory_page(request: Request):
    return page(request, "inventory.html", items=rows("SELECT * FROM inventory_items ORDER BY created_at DESC"), skus=rows("SELECT * FROM sku_map ORDER BY created_at DESC"), drafts=rows("SELECT * FROM listing_drafts ORDER BY created_at DESC"))


@app.get("/listings/drafts", response_class=HTMLResponse)
def drafts_page(request: Request):
    return page(request, "drafts.html", drafts=rows("SELECT * FROM listing_drafts ORDER BY created_at DESC"))


@app.get("/marketplace", response_class=HTMLResponse)
def marketplace_page(request: Request):
    return page(request, "marketplace.html", listings=rows("SELECT * FROM public_listings ORDER BY created_at DESC"))


@app.get("/marketplace/{listing_id}", response_class=HTMLResponse)
def listing_detail(request: Request, listing_id: str):
    listing = one("SELECT * FROM public_listings WHERE public_listing_id=? OR listing_id=?", (listing_id, listing_id))
    if not listing:
        raise HTTPException(404, "Listing not found")
    return page(request, "listing_detail.html", listing=listing)


@app.get("/proofbook", response_class=HTMLResponse)
def proofbook_page(request: Request):
    return page(request, "proofbook.html", proofs=rows("SELECT * FROM proofbook_entries ORDER BY created_at DESC LIMIT 300"))


@app.get("/wallet", response_class=HTMLResponse)
def wallet_page(request: Request):
    return page(request, "wallet.html", events=rows("SELECT * FROM wallet_events ORDER BY created_at DESC"), eligibility=rows("SELECT * FROM payout_eligibility ORDER BY created_at DESC"))


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    return page(request, "admin.html", decisions=rows("SELECT * FROM admin_decisions ORDER BY created_at DESC"), drafts=rows("SELECT * FROM listing_drafts ORDER BY created_at DESC LIMIT 50"), proofs=rows("SELECT * FROM proofbook_entries ORDER BY created_at DESC LIMIT 50"))


@app.get("/api-docs", response_class=HTMLResponse)
def docs_page(request: Request):
    endpoints = [
        "GET /api/health", "GET /api/ready", "GET /api/dashboard", "POST /api/ai/chat", "POST /api/photo/analyze",
        "GET /api/photos", "GET /api/inventory", "GET /api/sku-map", "POST /api/kpi/upload", "GET /api/kpis",
        "GET /api/proofbook", "GET /api/listings/drafts", "GET /api/listings/public",
        "POST /api/listings/{listing_id}/request-visibility", "POST /api/listings/{listing_id}/confirm-visibility",
        "POST /api/qr/artifacts", "GET /api/qr/artifacts", "GET /g/{artifact_id}",
        "GET/POST /api/wallet-events", "GET/POST /api/payout-eligibility", "GET/POST /api/admin/decisions",
        "POST /api/stripe/create-checkout-session", "POST /api/stripe/webhook",
    ]
    return page(request, "api_docs.html", endpoints=endpoints)


@app.get("/api/health")
def health():
    return {"ok": True, "app": APP_NAME, "version": APP_VERSION, "env": APP_ENV, "mode": "production_hardened_starter"}


@app.get("/api/ready")
def ready():
    try:
        counts = dashboard_payload()["counts"]
    except Exception as exc:
        raise HTTPException(503, f"database not ready: {exc}")
    warnings: list[str] = []
    if ADMIN_TOKEN in {"", "change-me"} and not ADMIN_TOKEN_SHA256:
        warnings.append("ADMIN_TOKEN is default; set ADMIN_TOKEN_SHA256 or a strong ADMIN_TOKEN before public deployment")
    if not (GROQ_API_KEY or OPENAI_API_KEY):
        warnings.append("LLM not configured; deterministic fallback is active")
    if not STRIPE_SECRET_KEY:
        warnings.append("Stripe not configured; payout eligibility records only")
    return {"ok": True, "counts": counts, "warnings": warnings}


@app.get("/api/dashboard")
def api_dashboard():
    return dashboard_payload()


@app.post("/api/photo/analyze")
async def analyze_photo(
    image: UploadFile = File(...),
    owner_id: str = Form("owner_default"),
    room_type: str = Form(""),
    monetization_goal: str = Form(""),
    user_notes: str = Form(""),
    location_hint: str = Form(""),
):
    filename, path = await save_upload(image, "photo", kind="image")
    width, height = image_meta(path)
    photo_id = new_id("photo")
    result = assetify_from_context(
        photo_id=photo_id,
        owner_id=owner_id,
        room_type=room_type,
        monetization_goal=monetization_goal,
        user_notes=user_notes,
        location_hint=location_hint,
        filename=filename,
        width=width,
        height=height,
    )
    execute(
        "INSERT INTO photos VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (photo_id, owner_id, filename, str(path), image.content_type or "", width, height, room_type, monetization_goal, user_notes, location_hint, result["room_summary"], "analyzed", now()),
    )
    created_drafts: list[dict[str, Any]] = []
    for item in result["detected_inventory"]:
        execute(
            "INSERT INTO inventory_items VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (item["inventory_item_id"], photo_id, owner_id, item["sku"], item["detected_name"], item["asset_type"], item["visual_evidence"], item["monetization_type"], item["listing_type"], item["description"], item["suggested_price_low"], item["suggested_price_high"], item["pricing_unit"], item["confidence"], item["kpi_score"], json.dumps(item["proof_required"]), json.dumps(item["risk_flags"]), item["recommended_action"], item["status"], now()),
        )
        category = item["sku"].split("-")[1]
        execute("INSERT INTO sku_map VALUES(?,?,?,?,?,?)", (item["sku"], item["inventory_item_id"], category, item["detected_name"], "active", now()))
        draft = create_listing_draft(item).to_dict()
        created_drafts.append(draft)
        execute(
            "INSERT INTO listing_drafts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (draft["listing_id"], draft["inventory_item_id"], draft["sku"], draft["title"], draft["description"], draft["listing_type"], draft["suggested_price_low"], draft["suggested_price_high"], draft["pricing_unit"], draft["status"], draft["owner_visibility_requested_at"], draft["owner_confirmed_at"], draft["created_at"]),
        )
    for card in result["kpi_cards"]:
        execute(
            "INSERT INTO kpi_cards VALUES(?,?,?,?,?,?,?,?,?)",
            (new_id("kpi"), card.get("source_photo_id"), card.get("inventory_item_id"), card["title"], card["value"], int(card["score"]), card["category"], card["explanation"], now()),
        )
    for event in ["photo_analyzed", "picture_inventory_mapped", "sku_map_created", "listing_drafts_created", "kpis_generated"]:
        insert_proof("photo", photo_id, event, {"owner_id": owner_id, "filename": filename, "inventory_count": len(result["detected_inventory"])})
    result["listing_drafts"] = created_drafts
    result["proofbook_entries_created"] = 5
    return result


@app.get("/api/photos")
def api_photos():
    return {"photos": rows("SELECT * FROM photos ORDER BY created_at DESC")}


@app.get("/api/inventory")
def api_inventory():
    return {"inventory": rows("SELECT * FROM inventory_items ORDER BY created_at DESC")}


@app.get("/api/sku-map")
def api_sku_map():
    return {"sku_map": rows("SELECT * FROM sku_map ORDER BY created_at DESC")}


def summarize_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    numeric = df.select_dtypes(include="number")
    categorical = df.select_dtypes(exclude="number")
    summary = {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "columns": list(map(str, df.columns)),
        "missing_values": {str(k): int(v) for k, v in df.isna().sum().to_dict().items()},
        "numeric_stats": json.loads(numeric.describe().fillna(0).to_json()) if not numeric.empty else {},
        "categorical_profile": {str(col): df[col].astype(str).value_counts().head(10).to_dict() for col in categorical.columns[:12]},
    }
    suggested = [
        "revenue trend" if any("revenue" in c.lower() or "sales" in c.lower() for c in df.columns) else "activity volume",
        "utilization rate", "top category mix", "missing data risk", "proof/readiness score",
    ]
    return {"summary": summary, "suggested_kpis": suggested}


@app.post("/api/kpi/upload")
async def upload_kpi(file: UploadFile = File(...)):
    filename, path = await save_upload(file, "dataset", kind="data")
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(path)
    elif suffix in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    else:
        raise HTTPException(400, "Upload CSV or XLSX")
    report = summarize_dataframe(df)
    upload_id = new_id("upload")
    execute(
        "INSERT INTO kpi_uploads VALUES(?,?,?,?,?,?,?)",
        (upload_id, filename, report["summary"]["row_count"], report["summary"]["column_count"], json.dumps(report["summary"], default=str), json.dumps(report["suggested_kpis"]), now()),
    )
    insert_proof("kpi_upload", upload_id, "kpis_generated", {"filename": filename, "rows": report["summary"]["row_count"]})
    return {"success": True, "upload_id": upload_id, **report}


@app.get("/api/kpis")
def api_kpis():
    return {"kpis": rows("SELECT * FROM kpi_cards ORDER BY created_at DESC"), "uploads": rows("SELECT * FROM kpi_uploads ORDER BY created_at DESC")}


@app.get("/api/proofbook")
def api_proofbook():
    return {"proofbook": rows("SELECT * FROM proofbook_entries ORDER BY created_at DESC")}


@app.get("/api/listings/drafts")
def api_listing_drafts():
    return {"drafts": rows("SELECT * FROM listing_drafts ORDER BY created_at DESC")}


@app.get("/api/listings/public")
def api_public_listings():
    return {"public_listings": rows("SELECT * FROM public_listings ORDER BY created_at DESC")}


@app.post("/api/listings/{listing_id}/request-visibility")
def api_request_visibility(listing_id: str):
    draft = one("SELECT * FROM listing_drafts WHERE listing_id=?", (listing_id,))
    if not draft:
        raise HTTPException(404, "Draft listing not found")
    updated = request_visibility(draft)
    execute("UPDATE listing_drafts SET status=?, owner_visibility_requested_at=? WHERE listing_id=?", (updated["status"], updated["owner_visibility_requested_at"], listing_id))
    execute("INSERT INTO marketplace_events VALUES(?,?,?,?,?)", (new_id("event"), listing_id, "visibility_requested", json.dumps({"status": updated["status"]}), now()))
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
    item = one("SELECT * FROM inventory_items WHERE inventory_item_id=?", (draft["inventory_item_id"],)) or {}
    amount = round((float(draft["suggested_price_low"]) + float(draft["suggested_price_high"])) / 2, 2)
    user_id = item.get("owner_id") or "owner_default"
    execute("INSERT INTO payout_eligibility VALUES(?,?,?,?,?,?,?,?)", (new_id("payout"), user_id, "listing", listing_id, amount, "owner_confirmed_marketplace_visibility", "eligible_pending_external_settlement", now()))
    execute("INSERT INTO wallet_events VALUES(?,?,?,?,?,?,?,?,?)", (new_id("ledger"), user_id, "listing", listing_id, amount, "payout_eligibility_created", "eligible_pending_external_settlement", json.dumps({"public_listing_id": p["public_listing_id"]}), now()))
    insert_proof("listing", listing_id, "visibility_confirmed", {"public_listing_id": p["public_listing_id"], "eligible_amount_usd": amount})
    return {"success": True, "listing": updated, "public_listing": p}


@app.post("/api/qr/artifacts")
def create_qr_artifact(payload: dict[str, Any]):
    artifact_id = new_id("artifact")
    artifact_hash = sha256_payload({"artifact_id": artifact_id, **payload, "created_at": now()})
    qr_url = f"{APP_BASE_URL}/g/{artifact_id}"
    execute("INSERT INTO qr_artifacts VALUES(?,?,?,?,?,?,?,?,?)", (artifact_id, payload.get("subject_type", "listing"), payload.get("subject_id", ""), payload.get("artifact_title", "MEMBRA artifact"), payload.get("destination_url", ""), artifact_hash, qr_url, "active", now()))
    insert_proof("qr_artifact", artifact_id, "qr_artifact_created", {"artifact_hash": artifact_hash})
    return {"success": True, "artifact_id": artifact_id, "artifact_hash": artifact_hash, "qr_url": qr_url}


@app.get("/api/qr/artifacts")
def list_qr_artifacts():
    return {"artifacts": rows("SELECT * FROM qr_artifacts ORDER BY created_at DESC")}


@app.get("/g/{artifact_id}", response_class=HTMLResponse)
def gateway(request: Request, artifact_id: str):
    artifact = one("SELECT * FROM qr_artifacts WHERE artifact_id=?", (artifact_id,))
    if not artifact:
        raise HTTPException(404, "Artifact not found")
    ip_hash = hashlib.sha256((request.client.host if request.client else "unknown").encode()).hexdigest()[:16]
    execute("INSERT INTO scan_events VALUES(?,?,?,?,?,?)", (new_id("scan"), artifact_id, "qr_scan", ip_hash, request.headers.get("user-agent", ""), now()))
    insert_proof("qr_artifact", artifact_id, "scan_recorded", {"ip_hash": ip_hash})
    return page(request, "gateway.html", artifact=artifact)


@app.get("/api/wallet-events")
def api_wallet_events():
    return {"wallet_events": rows("SELECT * FROM wallet_events ORDER BY created_at DESC")}


@app.post("/api/wallet-events")
def create_wallet_event(payload: dict[str, Any]):
    event_id = new_id("ledger")
    execute("INSERT INTO wallet_events VALUES(?,?,?,?,?,?,?,?,?)", (event_id, payload.get("user_id", "owner_default"), payload.get("subject_type", "manual"), payload.get("subject_id", ""), float(payload.get("amount_usd", 0)), payload.get("event_type", "manual_event"), payload.get("status", "recorded"), json.dumps(payload.get("metadata", {})), now()))
    return {"success": True, "ledger_event_id": event_id}


@app.get("/api/payout-eligibility")
def api_payout_eligibility():
    return {"payout_eligibility": rows("SELECT * FROM payout_eligibility ORDER BY created_at DESC")}


@app.post("/api/payout-eligibility")
def create_payout_eligibility(payload: dict[str, Any]):
    payout_id = new_id("payout")
    execute("INSERT INTO payout_eligibility VALUES(?,?,?,?,?,?,?,?)", (payout_id, payload.get("user_id", "owner_default"), payload.get("subject_type", "manual"), payload.get("subject_id", ""), float(payload.get("eligible_amount_usd", 0)), payload.get("eligibility_reason", "manual"), payload.get("status", "eligible_pending_external_settlement"), now()))
    insert_proof("payout", payout_id, "payout_eligibility_created", payload)
    return {"success": True, "payout_event_id": payout_id}


@app.get("/api/admin/decisions")
def api_admin_decisions():
    return {"admin_decisions": rows("SELECT * FROM admin_decisions ORDER BY created_at DESC")}


@app.post("/api/admin/decisions")
def create_admin_decision(payload: dict[str, Any], x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    decision_id = new_id("decision")
    execute("INSERT INTO admin_decisions VALUES(?,?,?,?,?,?,?,?)", (decision_id, payload.get("subject_type", "manual"), payload.get("subject_id", ""), payload.get("decision", "reviewed"), payload.get("operator", "admin"), payload.get("risk_level", "normal"), payload.get("notes", ""), now()))
    insert_proof(payload.get("subject_type", "manual"), payload.get("subject_id", decision_id), "admin_decision_recorded", {"decision_id": decision_id, "admin_decision": payload.get("decision", "reviewed")})
    return {"success": True, "decision_id": decision_id}


def fallback_ai(message: str) -> dict[str, Any]:
    text = (message or "").lower()
    asset_type = "apartment_space"
    price = "$40–$180 / monthly"
    if "car" in text:
        asset_type, price = "car_ad_space", "$120–$420 / monthly"
    elif "window" in text:
        asset_type, price = "first_floor_window_ad_surface", "$70–$180 / monthly"
    elif "wear" in text or "shirt" in text or "hoodie" in text:
        asset_type, price = "wearable_ad_space", "$30–$90 / monthly"
    elif "storage" in text or "closet" in text:
        asset_type, price = "storage_space", "$12–$80 / monthly"
    report = {
        "asset_type": asset_type,
        "monetization_path": "owner-approved MEMBRA inventory, proof package, private draft listing, owner-confirmed marketplace visibility",
        "required_permissions": ["ownership/control", "lease/building/HOA permission", "local law and insurance compatibility"],
        "risk_notes": ["estimates are not guaranteed", "admin review may hold visibility or eligibility"],
        "suggested_price_range": price,
        "proof_requirements": ["clear photos", "owner confirmation", "dimensions or usage rules", "consent scope"],
        "qr_nfc_setup": "Create QR artifact after draft listing exists.",
        "kpi_tracking_plan": ["readiness score", "proof readiness", "scan events", "listing conversion", "payout eligibility status"],
        "listing_readiness_score": 74,
        "next_action": "Upload a real photo in Assetify so MEMBRA can create actual inventory records and private drafts.",
    }
    return {"message": "MEMBRA can evaluate this as a real assetification workflow. Upload a photo or dataset to create records. AI-generated estimate; not guaranteed.", "opportunity_report": report}


@app.post("/api/ai/chat")
def ai_chat(payload: dict[str, Any]):
    messages = payload.get("messages", [])
    latest = messages[-1].get("content", "") if messages else ""
    system = "You are MEMBRA AI Concierge. Produce concise structured assetification advice. Never guarantee earnings. Require ownership/control, permission, proof, admin review, and external settlement rails."
    if GROQ_API_KEY:
        try:
            from groq import Groq
            client = Groq(api_key=GROQ_API_KEY)
            out = client.chat.completions.create(model=GROQ_MODEL, messages=[{"role": "system", "content": system}, *messages], temperature=0.2)
            response = {"message": out.choices[0].message.content, "opportunity_report": fallback_ai(latest)["opportunity_report"]}
        except Exception as exc:
            response = fallback_ai(f"{latest}\nLLM error: {exc}")
    elif OPENAI_API_KEY:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            out = client.chat.completions.create(model=OPENAI_MODEL, messages=[{"role": "system", "content": system}, *messages], temperature=0.2)
            response = {"message": out.choices[0].message.content, "opportunity_report": fallback_ai(latest)["opportunity_report"]}
        except Exception as exc:
            response = fallback_ai(f"{latest}\nLLM error: {exc}")
    else:
        response = fallback_ai(latest)
    execute("INSERT INTO ai_chat_events VALUES(?,?,?,?,?,?)", (new_id("chat"), payload.get("owner_id", "owner_default"), latest, response["message"], json.dumps(response.get("opportunity_report", {})), now()))
    return response


@app.post("/api/stripe/create-checkout-session")
def create_checkout_session(payload: dict[str, Any]):
    if not STRIPE_SECRET_KEY or not STRIPE_PRICE_ID:
        return JSONResponse({"configured": False, "message": "Stripe not configured."}, status_code=200)
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
        success_url=payload.get("success_url") or f"{APP_BASE_URL}/wallet?stripe=success",
        cancel_url=payload.get("cancel_url") or f"{APP_BASE_URL}/wallet?stripe=cancelled",
        customer_email=payload.get("email"),
    )
    return {"configured": True, "checkout_url": session.url}


@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("stripe-signature")
    if not STRIPE_WEBHOOK_SECRET:
        return {"configured": False, "message": "Stripe not configured."}
    try:
        event = stripe.Webhook.construct_event(body, signature, STRIPE_WEBHOOK_SECRET)
    except Exception as exc:
        raise HTTPException(400, f"Invalid Stripe webhook: {exc}")
    execute("INSERT INTO wallet_events VALUES(?,?,?,?,?,?,?,?,?)", (new_id("ledger"), "stripe", "stripe_event", event.get("id"), 0, event.get("type"), "recorded", json.dumps(event), now()))
    return {"received": True}


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=False)
