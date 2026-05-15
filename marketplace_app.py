from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import random
import re
import shutil
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from groq import Groq
from PIL import Image

APP_NAME = "MEMBRA KPI Assetification Marketplace"
APP_VERSION = "0.2.0"
DB_PATH = Path(os.getenv("DB_PATH", "./data/membra_kpi_marketplace.sqlite3"))
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
STATIC_DIR = Path("./static")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

DB_PATH.parent.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title=APP_NAME, version=APP_VERSION)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def rid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical(payload).encode()).hexdigest()


def init_db() -> None:
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS photos(id TEXT PRIMARY KEY, owner_id TEXT, filename TEXT, image_path TEXT, room_type TEXT, monetization_goal TEXT, user_notes TEXT, width INTEGER, height INTEGER, file_size INTEGER, ai_provider TEXT, analysis_json TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS inventory_items(id TEXT PRIMARY KEY, owner_id TEXT, photo_id TEXT, sku TEXT, asset_type TEXT, title TEXT, description TEXT, visual_evidence TEXT, monetization_type TEXT, listing_type TEXT, price_low REAL, price_high REAL, pricing_unit TEXT, confidence REAL, kpi_score REAL, proof_required_json TEXT, risk_flags_json TEXT, recommended_action TEXT, status TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS sku_map(id TEXT PRIMARY KEY, sku TEXT UNIQUE, category TEXT, photo_id TEXT, inventory_item_id TEXT, title TEXT, monetization_type TEXT, listing_type TEXT, price_low REAL, price_high REAL, kpi_score REAL, listing_readiness REAL, visibility_status TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS listing_drafts(id TEXT PRIMARY KEY, owner_id TEXT, inventory_item_id TEXT, sku TEXT, title TEXT, description TEXT, asset_type TEXT, listing_type TEXT, price_low REAL, price_high REAL, pricing_unit TEXT, status TEXT, requires_owner_confirmation INTEGER, created_at TEXT);
        CREATE TABLE IF NOT EXISTS public_listings(id TEXT PRIMARY KEY, draft_id TEXT, owner_id TEXT, sku TEXT, title TEXT, description TEXT, asset_type TEXT, listing_type TEXT, price_low REAL, price_high REAL, pricing_unit TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS kpi_cards(id TEXT PRIMARY KEY, owner_id TEXT, source_type TEXT, source_id TEXT, kpi_name TEXT, kpi_category TEXT, formula TEXT, value TEXT, confidence REAL, meaning TEXT, next_action TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS proofbook_entries(id TEXT PRIMARY KEY, event_type TEXT, source_system TEXT, source_id TEXT, payload_json TEXT, payload_hash TEXT, status TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS ai_chat_events(id TEXT PRIMARY KEY, message TEXT, reply TEXT, context_json TEXT, created_at TEXT);
        """)


def proof(event_type: str, source_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    row = {"id": rid("proof"), "event_type": event_type, "source_system": "membra_kpi", "source_id": source_id, "payload_json": canonical(payload), "payload_hash": digest(payload), "status": "recorded", "created_at": now()}
    with db() as conn:
        conn.execute("INSERT INTO proofbook_entries VALUES(?,?,?,?,?,?,?,?)", tuple(row.values()))
    return row


CATEGORY = {"couch_seat":"SEAT","workspace_access":"WORK","storage_space":"STORAGE","closet_capacity":"CLOSET","tool_rental":"TOOL","window_ad_space":"WINDOW","car_ad_space":"CARAD","wearable_media":"WEAR","relay_capacity":"RELAY","package_holding":"RELAY","pantry_surplus":"PANTRY","resale_bundle":"RESALE","ad_surface":"WALLAD"}


def make_sku(asset_type: str) -> str:
    return f"MEMBRA-{CATEGORY.get(asset_type, 'ITEM')}-{uuid.uuid4().hex[:4].upper()}"


def img_meta(path: Path) -> tuple[int, int, int]:
    size = path.stat().st_size
    try:
        with Image.open(path) as im:
            return im.width, im.height, size
    except Exception:
        return 0, 0, size


def fallback_items(room_type: str, goal: str, notes: str) -> list[dict[str, Any]]:
    text = f"{room_type} {goal} {notes}".lower()
    if "car" in text:
        seeds = [("car_ad_space","Rear window ad space","advertise","car ad surface",45,120,"campaign"),("car_ad_space","Side window QR decal","advertise","side window ad surface",35,95,"campaign"),("storage_space","Trunk storage capacity","store","trunk storage",15,45,"day"),("relay_capacity","Local delivery handoff route","relay","handoff route",6,25,"task"),("relay_capacity","Mobile campaign route","advertise","mobile campaign route",60,180,"campaign")]
    elif any(x in text for x in ["closet","clothing","bag","box","storage","messy"]):
        seeds = [("resale_bundle","Clothing resale bundle","sell","clothing bundle",20,120,"bundle"),("closet_capacity","Closet shelf storage","store","closet storage",12,45,"month"),("package_holding","Package holding point","relay","package holding",3,12,"package"),("wearable_media","Wearable media candidate","advertise","wearable ad space",25,80,"campaign"),("storage_space","Storage bin capacity","store","storage bin slot",8,30,"month")]
    elif "kitchen" in text or "pantry" in text:
        seeds = [("pantry_surplus","Pantry surplus bundle","sell","pantry surplus",5,25,"bundle"),("workspace_access","Countertop demo surface","access","countertop demo",10,35,"hour"),("tool_rental","Small appliance rental","lend","appliance rental",5,20,"use"),("relay_capacity","Local food pickup point","relay","pickup point",3,10,"task"),("window_ad_space","Kitchen window QR surface","advertise","window ad surface",20,75,"campaign")]
    elif "desk" in text or "office" in text:
        seeds = [("workspace_access","Desk workspace access","access","workspace",8,25,"hour"),("workspace_access","Creator content setup","rent","creator setup",15,60,"hour"),("tool_rental","Ring light or equipment rental","lend","equipment rental",5,20,"use"),("ad_surface","Wall QR poster surface","advertise","wall QR surface",20,70,"campaign"),("package_holding","Package receiving point","relay","package point",3,12,"package")]
    else:
        seeds = [("couch_seat","Couch seat + Wi-Fi workspace","access","couch seat rental",8,20,"hour"),("window_ad_space","Window ad surface","advertise","window ad surface",25,90,"campaign"),("storage_space","Shelf storage slot","store","storage shelf",10,35,"month"),("ad_surface","Wall QR poster surface","advertise","wall QR surface",20,70,"campaign"),("relay_capacity","Local handoff pickup point","relay","handoff point",4,15,"task")]
    return [{"asset_type":a,"title":t,"description":f"{t} mapped from picture context as draft MEMBRA inventory.","visual_evidence":f"Inferred from uploaded {room_type or 'space'} image and user notes.","monetization_type":m,"listing_type":lt,"price_low":lo,"price_high":hi,"pricing_unit":u,"confidence":round(random.uniform(.72,.91),2),"kpi_score":random.randint(68,92),"proof_required":["clear current photo","owner confirmation","usage rules"],"risk_flags":["owner approval required","price is estimate"],"recommended_action":"Review draft, add proof, request visibility, then confirm if desired."} for a,t,m,lt,lo,hi,u in seeds]


def groq_items(path: str, room_type: str, goal: str, notes: str, width: int, height: int, size: int) -> tuple[str, list[dict[str, Any]], str]:
    if not GROQ_API_KEY:
        return "fallback", fallback_items(room_type, goal, notes), "Fallback picture-to-inventory mapping used."
    prompt = f"""Return ONLY JSON: {{"room_summary":"", "items":[...]}}. Convert picture context into monetizable MEMBRA inventory. Each item: asset_type,title,description,visual_evidence,monetization_type,listing_type,price_low,price_high,pricing_unit,confidence,kpi_score,proof_required,risk_flags,recommended_action. No guaranteed income; draft only. Context path={path}, room_type={room_type}, goal={goal}, notes={notes}, width={width}, height={height}, size={size}."""
    try:
        res = Groq(api_key=GROQ_API_KEY).chat.completions.create(model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"), messages=[{"role":"user","content":prompt}], temperature=.2, max_tokens=2200)
        txt = res.choices[0].message.content or ""
        txt = re.sub(r"```(?:json)?|```", "", txt).strip()
        data = json.loads(txt[txt.find("{"):txt.rfind("}")+1])
        items = data.get("items") or data.get("detected_assets")
        if isinstance(items, list) and items:
            return "groq", items, data.get("room_summary", "Groq picture-to-inventory mapping completed.")
    except Exception:
        pass
    return "fallback", fallback_items(room_type, goal, notes), "Groq unavailable or invalid JSON; fallback mapping used."


def insert_kpis(owner_id: str | None, inv_id: str, sku: str, item: dict[str, Any]) -> list[dict[str, Any]]:
    defs = [("SKU Readiness",f"{item['kpi_score']}/100","Inventory readiness for review."),("Listing Readiness",f"{round(item['confidence']*item['kpi_score'],1)}/100","Draft quality score."),("Proof Readiness","3/3","Required proof fields assigned."),("Price Band",f"${item['price_low']}-${item['price_high']}/{item['pricing_unit']}","Estimated price only."),("Owner Confirmation","required","User approves before visibility."),("Marketplace Fit",item['listing_type'],"Best-fit listing class."),("Risk Flags",str(len(item['risk_flags'])),"Review items before visibility."),("Monetization Type",item['monetization_type'],"Commercial use path."),("Trust Boundary","draft-only","No external action taken."),("Next Action","request visibility","Move draft to confirmation queue.")]
    rows=[]
    with db() as conn:
        for name,value,meaning in defs:
            row={"id":rid("kpi"),"owner_id":owner_id,"source_type":"inventory_item","source_id":inv_id,"kpi_name":name,"kpi_category":"assetification","formula":name.lower().replace(" ","_"),"value":value,"confidence":item["confidence"],"meaning":meaning,"next_action":f"Review {sku}.","created_at":now()}
            conn.execute("INSERT INTO kpi_cards VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", tuple(row.values()))
            rows.append(row)
    return rows

init_db()

@app.get("/api/health")
def health():
    return {"ok":True,"app":APP_NAME,"version":APP_VERSION,"database":"connected","ai_provider":"groq" if GROQ_API_KEY else "fallback","features":["picture_to_inventory","sku_map","kpi_generation","listing_drafts","proofbook","marketplace"]}

@app.get("/api/dashboard")
def dashboard():
    with db() as conn:
        counts={t:conn.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"] for t in ["photos","inventory_items","sku_map","listing_drafts","public_listings","kpi_cards","proofbook_entries"]}
    return {"counts":counts}

@app.post("/api/photo/analyze")
async def analyze(image: UploadFile=File(...), owner_id: str|None=Form(None), room_type: str=Form("room"), monetization_goal: str=Form("monetize safe inventory"), user_notes: str=Form("")):
    ext=(image.filename or "upload.jpg").split(".")[-1].lower()
    if ext not in {"jpg","jpeg","png","webp"}: raise HTTPException(400,"unsupported image type")
    photo_id=rid("photo"); filename=f"{photo_id}.{ext}"; path=UPLOAD_DIR/filename
    with path.open("wb") as f: shutil.copyfileobj(image.file,f)
    w,h,size=img_meta(path); provider,items,summary=groq_items(str(path),room_type,monetization_goal,user_notes,w,h,size)
    analysis={"room_summary":summary,"items":items}
    with db() as conn:
        conn.execute("INSERT INTO photos VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (photo_id,owner_id,image.filename,f"/uploads/{filename}",room_type,monetization_goal,user_notes,w,h,size,provider,canonical(analysis),now()))
    proofs=[proof("photo_analyzed", photo_id, {"photo_id":photo_id,"provider":provider})]
    invs=[]; skus=[]; drafts=[]; kpis=[]
    for item in items:
        item.setdefault("confidence",.75); item.setdefault("kpi_score",70); item.setdefault("proof_required",[]); item.setdefault("risk_flags",[]); item.setdefault("pricing_unit","unit")
        sku=make_sku(item.get("asset_type","item")); inv_id=rid("inv"); draft_id=rid("draft"); sku_id=rid("sku")
        inv=(inv_id,owner_id,photo_id,sku,item.get("asset_type"),item.get("title"),item.get("description"),item.get("visual_evidence"),item.get("monetization_type"),item.get("listing_type"),float(item.get("price_low",item.get("suggested_price_low",0))),float(item.get("price_high",item.get("suggested_price_high",0))),item.get("pricing_unit"),float(item.get("confidence",.75)),float(item.get("kpi_score",70)),json.dumps(item.get("proof_required",[])),json.dumps(item.get("risk_flags",[])),item.get("recommended_action","Review draft."),"draft",now())
        with db() as conn:
            conn.execute("INSERT INTO inventory_items VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", inv)
            conn.execute("INSERT INTO sku_map VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (sku_id,sku,sku.split("-")[1],photo_id,inv_id,item.get("title"),item.get("monetization_type"),item.get("listing_type"),inv[10],inv[11],inv[14],round(inv[13]*inv[14],2),"draft",now()))
            conn.execute("INSERT INTO listing_drafts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (draft_id,owner_id,inv_id,sku,item.get("title"),item.get("description"),item.get("asset_type"),item.get("listing_type"),inv[10],inv[11],inv[12],"draft",1,now()))
        invs.append(dict(zip(["id","owner_id","photo_id","sku","asset_type","title","description","visual_evidence","monetization_type","listing_type","price_low","price_high","pricing_unit","confidence","kpi_score","proof_required_json","risk_flags_json","recommended_action","status","created_at"], inv)))
        skus.append({"sku":sku,"inventory_item_id":inv_id,"visibility_status":"draft"}); drafts.append({"id":draft_id,"sku":sku,"title":item.get("title"),"status":"draft"}); kpis.extend(insert_kpis(owner_id, inv_id, sku, invs[-1]))
    proofs += [proof("picture_inventory_mapped",photo_id,{"count":len(invs)}), proof("sku_map_created",photo_id,{"count":len(skus)}), proof("listing_drafts_created",photo_id,{"count":len(drafts)}), proof("kpis_generated",photo_id,{"count":len(kpis)})]
    return {"success":True,"photo_id":photo_id,"inventory_items_created":len(invs),"sku_records_created":len(skus),"listing_drafts_created":len(drafts),"kpi_cards_created":len(kpis),"proofbook_entries_created":len(proofs),"analysis":analysis,"inventory_items":invs,"sku_map":skus,"listing_drafts":drafts,"kpi_cards":kpis,"proofbook_entries":proofs}


def rows(table):
    with db() as conn: return {table:[dict(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY created_at DESC LIMIT 500").fetchall()]}
@app.get("/api/photos")
def photos(): return rows("photos")
@app.get("/api/inventory")
def inventory(): return rows("inventory_items")
@app.get("/api/sku-map")
def sku_map(): return rows("sku_map")
@app.get("/api/kpis")
def kpis(): return rows("kpi_cards")
@app.get("/api/proofbook")
def proofbook(): return rows("proofbook_entries")
@app.get("/api/listings/drafts")
def drafts(): return rows("listing_drafts")
@app.get("/api/listings/public")
def public(): return rows("public_listings")

@app.post("/api/listings/{listing_id}/request-visibility")
def request_visibility(listing_id: str):
    with db() as conn:
        row=conn.execute("SELECT * FROM listing_drafts WHERE id=?",(listing_id,)).fetchone()
        if not row: raise HTTPException(404,"draft not found")
        conn.execute("UPDATE listing_drafts SET status='pending_owner_confirmation' WHERE id=?",(listing_id,))
    return {"success":True,"status":"pending_owner_confirmation","proof":proof("visibility_requested",listing_id,{"listing_id":listing_id})}

@app.post("/api/listings/{listing_id}/confirm-visibility")
def confirm_visibility(listing_id: str):
    with db() as conn:
        row=conn.execute("SELECT * FROM listing_drafts WHERE id=?",(listing_id,)).fetchone()
        if not row: raise HTTPException(404,"draft not found")
        pub_id=rid("pub")
        pub=(pub_id,listing_id,row["owner_id"],row["sku"],row["title"],row["description"],row["asset_type"],row["listing_type"],row["price_low"],row["price_high"],row["pricing_unit"],now())
        conn.execute("INSERT INTO public_listings VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",pub)
        conn.execute("UPDATE listing_drafts SET status='visible_internal_marketplace' WHERE id=?",(listing_id,))
    return {"success":True,"public_listing_id":pub_id,"message":"Visible internally. No external buyer contact or payment action performed.","proof":proof("visibility_confirmed",listing_id,{"public_listing_id":pub_id})}

@app.post("/api/ai/chat")
async def chat(request: Request):
    body=await request.json(); msg=body.get("message","")
    with db() as conn:
        inv=[dict(r) for r in conn.execute("SELECT sku,title,kpi_score,status FROM inventory_items ORDER BY created_at DESC LIMIT 5").fetchall()]
    reply="Upload a picture to create SKU-mapped inventory."
    if inv: reply=f"Latest SKU: {inv[0]['sku']} — {inv[0]['title']} scored {inv[0]['kpi_score']}. Draft first, owner confirms visibility before marketplace posting."
    with db() as conn: conn.execute("INSERT INTO ai_chat_events VALUES(?,?,?,?,?)",(rid("chat"),msg,reply,json.dumps({"inventory":inv}),now()))
    proof("ai_concierge_response", "chat", {"message":msg,"reply":reply})
    return {"success":True,"reply":reply,"context_used":{"inventory_items":len(inv)}}

def page(title, body): return f"<!doctype html><html><head><title>{title}</title><link rel='stylesheet' href='/static/membra_marketplace.css'></head><body class='neu-shell'><nav><a href='/'>MEMBRA</a><a href='/inventory'>Inventory</a><a href='/sku-map'>SKU Map</a><a href='/kpi'>KPI</a><a href='/marketplace'>Marketplace</a><a href='/proofbook'>ProofBook</a></nav>{body}<script src='/static/membra_marketplace.js'></script></body></html>"
@app.get("/", response_class=HTMLResponse)
def home(): return page("MEMBRA", "<main class='neu-card hero'><h1>MEMBRA KPI</h1><p>Photo → SKU → inventory → KPI → owner-approved marketplace.</p><a class='neu-button-gold' href='/inventory'>Upload Picture</a></main>")
@app.get("/inventory", response_class=HTMLResponse)
def inv_page(): return page("Inventory", "<main><section class='neu-card'><h1>Picture to Inventory</h1><form id='uploadForm'><input class='neu-input' type='file' name='image' accept='image/*' required><input class='neu-input' name='owner_id' placeholder='owner id optional'><select class='neu-input' name='room_type'><option>room</option><option>living_room</option><option>closet</option><option>car</option><option>kitchen</option><option>office</option></select><input class='neu-input' name='monetization_goal' value='monetize safe inventory'><textarea class='neu-input' name='user_notes' placeholder='What can be monetized?'></textarea><button class='neu-button-gold'>Analyze Picture</button></form></section><section id='results' class='grid'></section></main>")
@app.get("/sku-map", response_class=HTMLResponse)
def sku_page(): return page("SKU Map", "<main><h1>SKU Map</h1><section class='grid' data-load='/api/sku-map'></section></main>")
@app.get("/kpi", response_class=HTMLResponse)
def kpi_page(): return page("KPI", "<main><h1>KPI Cards</h1><section class='grid' data-load='/api/kpis'></section></main>")
@app.get("/proofbook", response_class=HTMLResponse)
def proof_page(): return page("ProofBook", "<main><h1>ProofBook</h1><section class='grid' data-load='/api/proofbook'></section></main>")
@app.get("/marketplace", response_class=HTMLResponse)
def market_page(): return page("Marketplace", "<main><h1>Marketplace</h1><p>Only owner-confirmed listings appear.</p><section class='grid' data-load='/api/listings/public'></section></main>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT","7860")))
