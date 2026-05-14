"""MEMBRA KPI — Hugging Face production app.

Environment secrets:
GROQ_API_KEY, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_ID, APP_BASE_URL
Optional: GROQ_MODEL, REQUIRE_STRIPE, FREE_DAILY_LIMIT, PAID_DAILY_LIMIT, ADMIN_TOKEN
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any

import gradio as gr
import pandas as pd
import stripe
import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from groq import Groq
from pydantic import BaseModel

APP_NAME = "MEMBRA KPI"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-70b-8192")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:7860").rstrip("/")
REQUIRE_STRIPE = os.getenv("REQUIRE_STRIPE", "false").lower() in {"1", "true", "yes"}
FREE_DAILY_LIMIT = int(os.getenv("FREE_DAILY_LIMIT", "25"))
PAID_DAILY_LIMIT = int(os.getenv("PAID_DAILY_LIMIT", "1000"))
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
DB_PATH = Path(os.getenv("DB_PATH", "/tmp/membra_kpi.sqlite3"))
EXPORT_DIR = Path(os.getenv("EXPORT_DIR", "/tmp/membra_kpi_exports"))
EXPORT_DIR.mkdir(parents=True, exist_ok=True)
stripe.api_key = STRIPE_SECRET_KEY or None
api = FastAPI(title=APP_NAME)

class CheckoutRequest(BaseModel):
    email: str
    success_url: str | None = None
    cancel_url: str | None = None

class GrantRequest(BaseModel):
    email: str
    tier: str = "pro"
    daily_limit: int | None = None


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def day() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")


def clean_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise ValueError("Valid email required")
    return email


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS entitlement(email TEXT PRIMARY KEY,tier TEXT,status TEXT,daily_limit INTEGER,stripe_customer_id TEXT,stripe_subscription_id TEXT,updated_at TEXT);
        CREATE TABLE IF NOT EXISTS usage(email TEXT,day TEXT,count INTEGER DEFAULT 0,PRIMARY KEY(email,day));
        CREATE TABLE IF NOT EXISTS generations(id TEXT PRIMARY KEY,email TEXT,fingerprint TEXT,kpi_count INTEGER,created_at TEXT);
        """)

init_db()


def entitlement(email: str) -> dict[str, Any]:
    email = clean_email(email)
    with db() as conn:
        e = conn.execute("SELECT * FROM entitlement WHERE email=?", (email,)).fetchone()
        u = conn.execute("SELECT count FROM usage WHERE email=? AND day=?", (email, day())).fetchone()
    used = int(u["count"]) if u else 0
    base = dict(e) if e else {"email": email, "tier": "free", "status": "active" if not REQUIRE_STRIPE else "inactive", "daily_limit": FREE_DAILY_LIMIT}
    base["used_today"] = used
    base["remaining_today"] = max(0, int(base["daily_limit"]) - used)
    return base


def grant(email: str, tier: str = "pro", customer: str | None = None, subscription: str | None = None) -> None:
    limit = PAID_DAILY_LIMIT if tier == "pro" else FREE_DAILY_LIMIT
    with db() as conn:
        conn.execute("INSERT INTO entitlement(email,tier,status,daily_limit,stripe_customer_id,stripe_subscription_id,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(email) DO UPDATE SET tier=excluded.tier,status=excluded.status,daily_limit=excluded.daily_limit,stripe_customer_id=COALESCE(excluded.stripe_customer_id,entitlement.stripe_customer_id),stripe_subscription_id=COALESCE(excluded.stripe_subscription_id,entitlement.stripe_subscription_id),updated_at=excluded.updated_at", (clean_email(email), tier, "active", limit, customer, subscription, utcnow()))


def add_usage(email: str, n: int) -> None:
    with db() as conn:
        conn.execute("INSERT INTO usage(email,day,count) VALUES(?,?,?) ON CONFLICT(email,day) DO UPDATE SET count=usage.count+excluded.count", (clean_email(email), day(), int(n)))


def load_df(path: str) -> pd.DataFrame:
    if not path:
        raise ValueError("Upload a CSV, Excel, JSON, JSONL, or Parquet dataset")
    p = Path(path)
    if p.suffix.lower() == ".csv":
        df = pd.read_csv(p)
    elif p.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(p)
    elif p.suffix.lower() == ".jsonl":
        df = pd.read_json(p, lines=True)
    elif p.suffix.lower() == ".json":
        df = pd.read_json(p)
    elif p.suffix.lower() == ".parquet":
        df = pd.read_parquet(p)
    else:
        raise ValueError(f"Unsupported type: {p.suffix}")
    if df.empty:
        raise ValueError("Dataset is empty")
    return df.iloc[:250000, :150].copy()


def profile(df: pd.DataFrame) -> str:
    cols = []
    for c in df.columns:
        s = df[c]
        item = {"name": str(c), "dtype": str(s.dtype), "null_pct": round(float(s.isna().mean()*100), 2), "unique": int(s.nunique(dropna=True))}
        if pd.api.types.is_numeric_dtype(s):
            item["stats"] = {k: round(float(v), 4) for k, v in s.describe().to_dict().items() if pd.notna(v)}
        else:
            item["top"] = {str(k)[:80]: int(v) for k, v in s.astype(str).value_counts().head(5).to_dict().items()}
        cols.append(item)
    return json.dumps({"rows": len(df), "columns": list(map(str, df.columns)), "profile": cols, "sample": df.head(10).to_dict("records")}, ensure_ascii=False, default=str)


def llm_kpis(dataset_profile: str, context: str, n: int) -> list[dict[str, Any]]:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set")
    prompt = {"task":"Return only JSON with key kpis. Build auditable institutional KPIs from the dataset profile.","count":n,"context":context,"schema":{"kpis":[{"name":"","category":"","definition":"","formula":"","required_columns":[],"frequency":"","owner":"","thresholds":{"green":"","yellow":"","red":""},"decision_use":"","risk_notes":""}]},"dataset_profile":dataset_profile}
    res = Groq(api_key=GROQ_API_KEY).chat.completions.create(model=GROQ_MODEL, temperature=0.2, max_tokens=4096, response_format={"type":"json_object"}, messages=[{"role":"user","content":json.dumps(prompt, ensure_ascii=False)}])
    data = json.loads(res.choices[0].message.content or "{}")
    return [x for x in data.get("kpis", []) if isinstance(x, dict) and x.get("name")]


def flatten(k: dict[str, Any]) -> dict[str, Any]:
    return {"name": k.get("name",""), "category": k.get("category",""), "definition": k.get("definition",""), "formula": k.get("formula",""), "required_columns": ", ".join(map(str, k.get("required_columns", []))), "frequency": k.get("frequency",""), "owner": k.get("owner",""), "thresholds": json.dumps(k.get("thresholds",{})), "decision_use": k.get("decision_use",""), "risk_notes": k.get("risk_notes","")}


def run(email: str, file_path: str, context: str, count: int):
    try:
        ent = entitlement(email)
        n = max(1, min(int(count), 50))
        if REQUIRE_STRIPE and ent["status"] not in {"active", "trialing"}:
            return pd.DataFrame(), "Stripe entitlement required", None, None
        if ent["remaining_today"] < n:
            return pd.DataFrame(), f"Quota exceeded. Remaining: {ent['remaining_today']}", None, None
        df = load_df(file_path)
        fp = hashlib.sha256((str(df.shape)+"|"+"|".join(map(str, df.columns))).encode()).hexdigest()[:16]
        kpis = llm_kpis(profile(df), context, n)[:n]
        add_usage(email, len(kpis))
        with db() as conn:
            conn.execute("INSERT INTO generations VALUES(?,?,?,?,?)", (uuid.uuid4().hex, clean_email(email), fp, len(kpis), utcnow()))
        stem = f"kpis_{dt.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        jp, cp = EXPORT_DIR/f"{stem}.json", EXPORT_DIR/f"{stem}.csv"
        jp.write_text(json.dumps(kpis, indent=2), encoding="utf-8")
        pd.DataFrame([flatten(k) for k in kpis]).to_csv(cp, index=False)
        return pd.DataFrame([flatten(k) for k in kpis]), f"Generated {len(kpis)} KPIs", str(jp), str(cp)
    except Exception as exc:
        return pd.DataFrame(), f"Error: {exc}", None, None


def checkout(email: str) -> str:
    if not STRIPE_SECRET_KEY or not STRIPE_PRICE_ID:
        return "Stripe not configured"
    session = stripe.checkout.Session.create(mode="subscription", customer_email=clean_email(email), line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}], success_url=f"{APP_BASE_URL}/?success=true", cancel_url=f"{APP_BASE_URL}/?cancel=true", metadata={"email": clean_email(email)})
    return session.url

@api.get("/api/health")
def health():
    return {"ok": True, "app": APP_NAME, "groq": bool(GROQ_API_KEY), "stripe": bool(STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET and STRIPE_PRICE_ID)}

@api.get("/api/entitlement")
def get_entitlement(email: str):
    return entitlement(email)

@api.post("/api/admin/grant")
def admin_grant(payload: GrantRequest, authorization: str | None = Header(default=None)):
    if not ADMIN_TOKEN or authorization != f"Bearer {ADMIN_TOKEN}":
        raise HTTPException(401, "Unauthorized")
    grant(payload.email, payload.tier)
    return entitlement(payload.email)

@api.post("/api/stripe/create-checkout-session")
def create_checkout(payload: CheckoutRequest):
    return {"url": checkout(payload.email)}

@api.post("/api/stripe/webhook")
async def webhook(request: Request, stripe_signature: str | None = Header(default=None)):
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(500, "Webhook secret not set")
    body = await request.body()
    try:
        event = stripe.Webhook.construct_event(body, stripe_signature, STRIPE_WEBHOOK_SECRET)
    except Exception as exc:
        raise HTTPException(400, str(exc))
    obj = event["data"]["object"]
    if event["type"] == "checkout.session.completed":
        email = obj.get("customer_email") or obj.get("customer_details", {}).get("email") or obj.get("metadata", {}).get("email")
        if email:
            grant(email, "pro", obj.get("customer"), obj.get("subscription"))
    return JSONResponse({"received": True})

with gr.Blocks(title=APP_NAME) as demo:
    gr.Markdown("# MEMBRA KPI\nInstitutional dataset-to-KPI generator with Stripe entitlement hooks.")
    email = gr.Textbox(label="Account email")
    file_in = gr.File(label="Dataset", file_types=[".csv", ".xlsx", ".xls", ".json", ".jsonl", ".parquet"], type="filepath")
    context = gr.Textbox(label="Business context", lines=4)
    count = gr.Slider(1, 50, value=10, step=1, label="KPI count")
    with gr.Row():
        gen = gr.Button("Generate KPIs", variant="primary")
        pay = gr.Button("Create Stripe checkout")
    out = gr.Dataframe(label="KPIs", interactive=False)
    status = gr.Textbox(label="Status")
    json_file = gr.File(label="JSON")
    csv_file = gr.File(label="CSV")
    pay_out = gr.Textbox(label="Checkout URL")
    gen.click(run, [email, file_in, context, count], [out, status, json_file, csv_file])
    pay.click(checkout, [email], [pay_out])

app = gr.mount_gradio_app(api, demo, path="/")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "7860")))
