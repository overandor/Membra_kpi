# MEMBRA KPI Start-to-End System

This repository is the consolidated Replit-style MEMBRA KPI wedge. It begins with a user-controlled real upload and ends with an owner-confirmed marketplace listing plus ProofBook and payout-eligibility records.

## System loop

```text
1. User opens landing page
2. User chats with AI Concierge or uploads a real photo/dataset
3. Photo is stored locally
4. Image metadata is extracted
5. Deterministic MEMBRA assetification engine maps context to inventory
6. SKU records are created
7. KPI cards are generated
8. ProofBook SHA-256 records are written
9. Private listing drafts are created
10. Owner requests visibility
11. Owner confirms visibility
12. Internal marketplace listing is created
13. Wallet records payout eligibility
14. QR artifact can be created
15. QR scan creates a scan event and ProofBook record
16. Admin console can record review/risk decisions
```

## What is operational

- FastAPI app
- Jinja2 server-rendered UI
- Replit boot config
- SQLite persistence
- Real photo upload handling
- Real CSV/XLSX parsing
- Inventory table
- SKU map table
- KPI card table
- ProofBook table
- Draft listing table
- Owner-confirmed public listing table
- QR artifact table
- Scan event table
- Wallet event table
- Payout eligibility table
- Admin decision table
- AI chat event table

## What is intentionally not automated

- No automatic public listing without owner confirmation
- No automatic buyer outreach
- No automatic social posting
- No automatic settlement
- No custody
- No guaranteed earnings
- No private key or seed phrase collection

## Replit development model

Replit starts the app with:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

The repository is designed to run as one application:

```text
app.py                 FastAPI routes, database setup, workflow orchestration
membra_kpi/            reusable business engines
templates/             neomorphic server-rendered UI
static/                CSS, JavaScript, uploads
requirements.txt       runtime dependencies
.replit                Replit boot command
.env.example           secret and runtime variable template
tests/                 smoke and engine tests
```

## Product boundary

MEMBRA KPI records proof and eligibility. It does not settle money. External payment rails settle money after appropriate permission, proof, review, and compliance checks.
