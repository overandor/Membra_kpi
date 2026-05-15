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
from membra_kpi.event_outbox import ensure_event_outbox, enqueue_event, mark_delivered, mark_failed, outbox_stats, pending_events
from membra_kpi.events import deliver_event
from membra_kpi.marketplace import confirm_visibility, create_listing_draft, request_visibility
from membra_kpi.product_router import build_product_router
from membra_kpi.proofbook import create_proof_entry, sha256_payload
from membra_kpi.security import apply_security_headers, enforce_rate_limit, validate_data_upload, validate_image_upload, verify_admin_token
from membra_kpi.solana_devnet import anchor_listing_on_solana_devnet, solana_devnet_status

APP_NAME = "MEMBRA KPI Assetification Marketplace"
APP_VERSION = "1.5.0"
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
        ensure_event_outbox(conn)


init_db()
app.include_router(build_product_router(db))


def insert_proof(subject_type: str, subject_id: str, event_type: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    entry = create_proof_entry(subject_type, subject_id, event_type, metadata or {})
    row = entry.to_row()
    execute("INSERT INTO proofbook_entries(proof_id,subject_type,subject_id,event_type,proof_hash,metadata_json,created_at) VALUES(?,?,?,?,?,?,?)", (row["proof_id"], row["subject_type"], row["subject_id"], row["event_type"], row["proof_hash"], row["metadata_json"], row["created_at"]))
    return row


def emit_domain_event(
    event_type: str,
    *,
    subject_type: str,
    subject_id: str,
    owner_id: str | None = None,
    payload: dict[str, Any] | None = None,
    consent_scope: str | None = None,
    risk_level: str = "normal",
    correlation_id: str | None = None,
    causation_id: str | None = None,
) -> dict[str, Any]:
    """Persist a canonical MEMBRA event into the local outbox.

    Downstream delivery is intentionally separated from domain writes. This makes
    KPI durable when API, ProofBook, Wallet, Admin, or QR Gateway are offline.
    """
    with db() as conn:
        event = enqueue_event(
            conn,
            event_type,
            subject_type=subject_type,
            subject_id=subject_id,
            owner_id=owner_id,
            payload=payload or {},
            consent_scope=consent_scope,
            risk_level=risk_level,
            correlation_id=correlation_id,
            causation_id=causation_id,
        )
    insert_proof(
        "event_outbox",
        event["event_id"],
        "event_outbox_enqueued",
        {"event_type": event_type, "subject_type": subject_type, "subject_id": subject_id, "owner_id": owner_id, "proof_hash": event.get("proof_hash")},
    )
    return event


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
    else:
        raise HTTPException(400, "Unknown upload kind")
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
        "revenue trend" if any("revenue" in str(c).lower() or "sales" in str(c).lower() for c in df.columns) else "activity volume",
        "utilization rate",
        "top category mix",
        "missing data risk",
        "proof/readiness score",
    ]
    return {"summary": summary, "suggested_kpis": suggested}


def require_admin(token: str | None) -> None:
    if not verify_admin_token(token, plain_token=ADMIN_TOKEN, token_hash=ADMIN_TOKEN_SHA256 or None):
        raise HTTPException(status_code=401, detail="Valid admin token required")


def dashboard_payload() -> dict[str, Any]:
    with db() as conn:
        event_stats = outbox_stats(conn)
    return {
        "counts": {
            "photos": one("SELECT COUNT(*) c FROM photos")["c"],
            "inventory": one("SELECT COUNT(*) c FROM inventory_items")["c"],
            "drafts": one("SELECT COUNT(*) c FROM listing_drafts")["c"],
            "public_listings": one("SELECT COUNT(*) c FROM public_listings")["c"],
            "kpis": one("SELECT COUNT(*) c FROM kpi_cards")["c"],
            "proofs": one("SELECT COUNT(*) c FROM proofbook_entries")["c"],
            "event_outbox_pending": event_stats.get("pending", 0),
            "event_outbox_failed": event_stats.get("failed", 0),
            "event_outbox_delivered": event_stats.get("delivered", 0),
            "event_outbox_dead_letter": event_stats.get("dead_letter", 0),
        }
    }


def page(request: Request, name: str, **context: Any) -> HTMLResponse:
    return templates.TemplateResponse(name, {"request": request, "app_name": APP_NAME, "app_env": APP_ENV, **context})


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return page(request, "index.html", dashboard=dashboard_payload())


@app.get("/api/health")
def health():
    return {"ok": True, "app": APP_NAME, "version": APP_VERSION, "env": APP_ENV, "product_router_mounted": True, "event_outbox": True}


@app.get("/api/ready")
def ready():
    warnings = []
    if ADMIN_TOKEN in {"", "change-me"} and not ADMIN_TOKEN_SHA256:
        warnings.append("ADMIN_TOKEN is default")
    if not STRIPE_SECRET_KEY:
        warnings.append("Stripe not configured; eligibility records only")
    if not os.getenv("MEMBRA_EVENT_SECRET"):
        warnings.append("MEMBRA_EVENT_SECRET not configured; outbox events are unsigned")
    if not os.getenv("MEMBRA_EVENT_SINKS"):
        warnings.append("MEMBRA_EVENT_SINKS not configured; outbox replay has no downstream targets")
    with db() as conn:
        event_stats = outbox_stats(conn)
    return {"ok": True, "counts": dashboard_payload()["counts"], "event_outbox": event_stats, "deep_backend": api_deep_backend_status(), "solana_devnet": solana_devnet_status(), "warnings": warnings}


@app.get("/api/deep-backend/status")
def api_deep_backend_status():
    with db() as conn:
        return backend_status(conn)


@app.get("/api/solana/devnet/status")
def api_solana_status():
    return solana_devnet_status()


@app.get("/api/photos")
def api_photos():
    return {"photos": rows("SELECT * FROM photos ORDER BY created_at DESC")}


@app.get("/api/inventory")
def api_inventory():
    return {"inventory": rows("SELECT * FROM inventory_items ORDER BY created_at DESC")}


@app.get("/api/sku-map")
def api_sku_map():
    return {"sku_map": rows("SELECT * FROM sku_map ORDER BY created_at DESC")}


@app.get("/api/kpis")
def api_kpis():
    return {"kpis": rows("SELECT * FROM kpi_cards ORDER BY created_at DESC"), "uploads": rows("SELECT * FROM kpi_uploads ORDER BY created_at DESC")}


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
            (item["inventory_item_id"], photo_id, owner_id, item["sku"], item["detected_name"], item["asset_type"], item["visual_evidence"], item["monetization_type"], item["listing_type"], item["description"], item["suggested_price_low"], item["suggested_price_high"], item["pricing_unit"], item["confidence"], item["kpi_score"], json.dumps(item["proof_required"], default=str), json.dumps(item["risk_flags"], default=str), item["recommended_action"], item["status"], now()),
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
    proof_events: list[dict[str, Any]] = []
    for event_type in ["photo_analyzed", "picture_inventory_mapped", "inventory_items_created", "sku_map_created", "listing_drafts_created", "kpis_generated"]:
        proof_events.append(insert_proof("photo", photo_id, event_type, {"owner_id": owner_id, "filename": filename, "inventory_count": len(result["detected_inventory"]), "draft_count": len(created_drafts)}))
    photo_event = emit_domain_event(
        "photo_analyzed",
        subject_type="photo",
        subject_id=photo_id,
        owner_id=owner_id,
        payload={"photo_id": photo_id, "filename": filename, "width": width, "height": height, "room_type": room_type, "monetization_goal": monetization_goal, "room_summary": result["room_summary"]},
        consent_scope="uploaded photo metadata, owner context, and derived proof/inventory records only",
        risk_level="normal",
    )
    inventory_event = emit_domain_event(
        "inventory_items_created",
        subject_type="photo",
        subject_id=photo_id,
        owner_id=owner_id,
        payload={"inventory": result["detected_inventory"], "inventory_count": len(result["detected_inventory"])},
        consent_scope="derived inventory and listing-readiness metadata only",
        risk_level="normal",
        correlation_id=photo_event["event_id"],
    )
    sku_event = emit_domain_event(
        "sku_map_created",
        subject_type="photo",
        subject_id=photo_id,
        owner_id=owner_id,
        payload={"skus": [item["sku"] for item in result["detected_inventory"]]},
        consent_scope="SKU identifiers and derived asset categories only",
        risk_level="normal",
        correlation_id=photo_event["event_id"],
        causation_id=inventory_event["event_id"],
    )
    draft_event = emit_domain_event(
        "listing_drafts_created",
        subject_type="photo",
        subject_id=photo_id,
        owner_id=owner_id,
        payload={"drafts": created_drafts, "draft_count": len(created_drafts)},
        consent_scope="private draft metadata only; no public visibility without owner confirmation",
        risk_level="medium",
        correlation_id=photo_event["event_id"],
        causation_id=sku_event["event_id"],
    )
    kpi_event = emit_domain_event(
        "kpis_generated",
        subject_type="photo",
        subject_id=photo_id,
        owner_id=owner_id,
        payload={"kpi_count": len(result["kpi_cards"]), "proofs": proof_events},
        consent_scope="derived KPI summaries and proof hashes only",
        risk_level="normal",
        correlation_id=photo_event["event_id"],
        causation_id=draft_event["event_id"],
    )
    result["listing_drafts"] = created_drafts
    result["proofbook_entries_created"] = len(proof_events)
    result["events"] = [photo_event, inventory_event, sku_event, draft_event, kpi_event]
    return result


@app.post("/api/kpi/upload")
async def upload_kpi(file: UploadFile = File(...), owner_id: str = Form("owner_default")):
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
        (upload_id, filename, report["summary"]["row_count"], report["summary"]["column_count"], json.dumps(report["summary"], default=str), json.dumps(report["suggested_kpis"], default=str), now()),
    )
    proof = insert_proof("kpi_upload", upload_id, "kpis_generated", {"owner_id": owner_id, "filename": filename, "rows": report["summary"]["row_count"], "columns": report["summary"]["column_count"]})
    event = emit_domain_event(
        "kpis_generated",
        subject_type="kpi_upload",
        subject_id=upload_id,
        owner_id=owner_id,
        payload={"filename": filename, "summary": report["summary"], "suggested_kpis": report["suggested_kpis"], "proof": proof},
        consent_scope="dataset profile, column summary, derived KPI metadata, and proof hash only",
        risk_level="normal",
    )
    return {"success": True, "upload_id": upload_id, "event": event, **report}


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
    event = emit_domain_event(
        "proof_reviewed",
        subject_type="listing",
        subject_id=listing_id,
        owner_id=listing.get("owner_id"),
        payload={"action": "solana_devnet_anchor_requested", "network": "solana-devnet", "proof": proof, "anchor": result},
        consent_scope="proof hash and devnet anchor metadata only",
        risk_level="normal",
    )
    return {"success": result.get("error") is None, "anchor": result, "event": event}


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


@app.get("/api/events/outbox")
def api_event_outbox(status: str | None = None, limit: int = 250):
    allowed = {None, "pending", "delivered", "failed", "dead_letter"}
    if status not in allowed:
        raise HTTPException(400, "status must be pending, delivered, failed, or dead_letter")
    limit = max(1, min(limit, 500))
    if status:
        out = rows("SELECT * FROM event_outbox WHERE status=? ORDER BY created_at DESC LIMIT ?", (status, limit))
    else:
        out = rows("SELECT * FROM event_outbox ORDER BY created_at DESC LIMIT ?", (limit,))
    return {"events": out}


@app.get("/api/events/outbox/stats")
def api_event_outbox_stats():
    with db() as conn:
        return {"event_outbox": outbox_stats(conn)}


@app.post("/api/events/outbox/replay")
async def api_event_outbox_replay(limit: int = 50, x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    limit = max(1, min(limit, 200))
    results: list[dict[str, Any]] = []
    with db() as conn:
        events = pending_events(conn, limit=limit)
    for event in events:
        outbox_id = event.pop("_outbox_id")
        event.pop("_attempt_count", None)
        delivery = await deliver_event(event)
        with db() as conn:
            if delivery and all(item.get("ok") for item in delivery):
                mark_delivered(conn, outbox_id)
                insert_proof("event_outbox", event["event_id"], "event_outbox_delivered", {"delivery": delivery})
                status = "delivered"
            else:
                error = "No MEMBRA_EVENT_SINKS configured" if not delivery else json.dumps(delivery, default=str)
                mark_failed(conn, outbox_id, error)
                insert_proof("event_outbox", event["event_id"], "event_outbox_failed", {"delivery": delivery, "error": error})
                status = "failed"
        results.append({"event_id": event["event_id"], "status": status, "delivery": delivery})
    return {"processed": len(results), "results": results}


@app.post("/api/listings/{listing_id}/request-visibility")
def api_request_visibility(listing_id: str):
    draft = one("SELECT * FROM listing_drafts WHERE listing_id=?", (listing_id,))
    if not draft:
        raise HTTPException(404, "Draft listing not found")
    updated = request_visibility(draft)
    execute("UPDATE listing_drafts SET status=?, owner_visibility_requested_at=? WHERE listing_id=?", (updated["status"], updated["owner_visibility_requested_at"], listing_id))
    proof = insert_proof("listing", listing_id, "visibility_requested", {"status": updated["status"]})
    event = emit_domain_event(
        "visibility_requested",
        subject_type="listing",
        subject_id=listing_id,
        owner_id=draft.get("owner_id") or draft.get("user_id"),
        payload={"draft": draft, "listing": updated, "proof": proof},
        consent_scope="owner requested internal marketplace visibility; proof and listing metadata only",
        risk_level="medium",
    )
    return {"success": True, "listing": updated, "event": event}


@app.post("/api/listings/{listing_id}/confirm-visibility")
def api_confirm_visibility(listing_id: str):
    draft = one("SELECT * FROM listing_drafts WHERE listing_id=?", (listing_id,))
    if not draft:
        raise HTTPException(404, "Draft listing not found")
    updated, public = confirm_visibility(draft)
    p = public.to_dict()
    execute("UPDATE listing_drafts SET status=?, owner_confirmed_at=? WHERE listing_id=?", (updated["status"], updated["owner_confirmed_at"], listing_id))
    execute("INSERT INTO public_listings VALUES(?,?,?,?,?,?,?,?,?,?)", (p["public_listing_id"], p["listing_id"], p["sku"], p["title"], p["description"], p["price_low"], p["price_high"], p["pricing_unit"], p["visibility_status"], p["created_at"]))
    proof = insert_proof("listing", listing_id, "visibility_confirmed", {"public_listing_id": p["public_listing_id"]})
    amount = round((float(p.get("price_low") or 0) + float(p.get("price_high") or 0)) / 2, 2)
    owner_id = draft.get("owner_id") or draft.get("user_id") or "owner_default"
    payout_id = new_id("payout")
    ledger_id = new_id("ledger")
    execute("INSERT INTO payout_eligibility VALUES(?,?,?,?,?,?,?,?)", (payout_id, owner_id, "listing", listing_id, amount, "owner_confirmed_marketplace_visibility", "eligible_pending_external_settlement", now()))
    execute("INSERT INTO wallet_events VALUES(?,?,?,?,?,?,?,?,?)", (ledger_id, owner_id, "listing", listing_id, amount, "payout_eligibility_created", "eligible_pending_external_settlement", json.dumps({"public_listing_id": p["public_listing_id"]}, default=str), now()))
    payout_proof = insert_proof("listing", listing_id, "payout_eligibility_created", {"payout_event_id": payout_id, "ledger_event_id": ledger_id, "eligible_amount_usd": amount})
    visibility_event = emit_domain_event(
        "visibility_confirmed",
        subject_type="listing",
        subject_id=listing_id,
        owner_id=owner_id,
        payload={"draft": draft, "listing": updated, "public_listing": p, "proof": proof, "eligible_amount_usd": amount, "destination_url": f"{APP_BASE_URL}/marketplace/{p['public_listing_id']}"},
        consent_scope="owner confirmed marketplace visibility; listing, proof, QR, and payout-eligibility metadata only",
        risk_level="normal",
    )
    payout_event = emit_domain_event(
        "payout_eligibility_created",
        subject_type="listing",
        subject_id=listing_id,
        owner_id=owner_id,
        payload={"payout_event_id": payout_id, "ledger_event_id": ledger_id, "eligible_amount_usd": amount, "proof": payout_proof, "public_listing_id": p["public_listing_id"]},
        consent_scope="payout eligibility metadata only; external rails settle money",
        risk_level="normal",
        correlation_id=visibility_event["event_id"],
    )
    return {"success": True, "listing": updated, "public_listing": p, "events": [visibility_event, payout_event]}


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=False)
