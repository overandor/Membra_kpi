# MEMBRA KPI Assetification Marketplace

MEMBRA KPI is now a Replit-native, all-in-one FastAPI system for turning real user uploads into structured MEMBRA records.

It is not a disconnected mockup. The app persists records in SQLite and connects the full operating loop:

```text
real photo upload
→ inventory detection from context
→ SKU assignment
→ KPI cards
→ ProofBook hashes
→ private listing drafts
→ owner visibility request
→ owner confirmation
→ internal marketplace listing
→ payout eligibility record
```

## Product promise

**Turn idle reality into measurable opportunity.**

Users can upload photos or KPI files and use MEMBRA to structure eligible apartment space, storage, car ad space, first-floor window ads, wearable ads, local handoff capacity, tool access, workspace access, and resale bundles into owner-controlled inventory.

## What is included

- Premium dark-gold neomorphic landing page
- FastAPI backend
- Server-rendered Jinja2 UI
- SQLite persistence
- Real image upload handling
- Real CSV/XLSX KPI upload parsing
- Deterministic photo/context-to-SKU assetification engine
- SKU map
- KPI card engine
- ProofBook SHA-256 audit ledger
- Private listing drafts
- Owner-approved marketplace visibility lifecycle
- QR artifact gateway with scan recording
- Wallet / payout eligibility records
- Admin review console with token-protected mutations
- Optional Groq/OpenAI AI Concierge
- Optional Stripe checkout/webhook endpoints
- Replit run configuration

## Safety and operating boundaries

MEMBRA KPI follows these rules:

- AI may draft inventory; owners must approve visibility.
- Drafts are private and do not appear in the marketplace.
- Owner confirmation is required before a public/internal marketplace listing is created.
- Estimates are not guaranteed.
- Eligibility depends on permission, proof, review, local rules, lease/building rules, insurance, zoning, and external settlement rails.
- MEMBRA records payout eligibility only.
- MEMBRA does not custody funds.
- External payment rails settle money.
- Do not upload private keys, seed phrases, raw financial credentials, or unconsented personal material.

## Local / Replit run

```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

The `.replit` file runs the same command automatically.

Open:

```text
http://localhost:8000
```

## Environment variables

Copy `.env.example` into Replit Secrets or your local environment.

Required for basic local operation: none.

Optional:

```text
APP_BASE_URL=http://localhost:8000
DB_PATH=./data/membra.db
UPLOAD_DIR=./static/uploads
ADMIN_TOKEN=change-me
GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_ID=
```

Without an LLM key, the AI Concierge still works through deterministic fallback logic. Without Stripe keys, Stripe endpoints return `Stripe not configured.`

## Main pages

| Page | Purpose |
|---|---|
| `/` | Public landing page and operating-system overview |
| `/dashboard` | Live record counts and recent activity |
| `/ai` | AI Concierge chat |
| `/assetify` | Real photo upload and photo-to-SKU workflow |
| `/kpi` | CSV/XLSX KPI upload and local analysis |
| `/inventory` | Inventory and SKU map |
| `/listings/drafts` | Private listing draft lifecycle |
| `/marketplace` | Owner-confirmed visible listings only |
| `/proofbook` | SHA-256 proof ledger |
| `/wallet` | Payout eligibility and ledger records |
| `/admin` | Operator review console |
| `/api-docs` | Endpoint list and examples |

## Core API endpoints

```text
GET  /api/health
GET  /api/dashboard
POST /api/ai/chat
POST /api/photo/analyze
GET  /api/photos
GET  /api/inventory
GET  /api/sku-map
POST /api/kpi/upload
GET  /api/kpis
GET  /api/proofbook
GET  /api/listings/drafts
GET  /api/listings/public
POST /api/listings/{listing_id}/request-visibility
POST /api/listings/{listing_id}/confirm-visibility
POST /api/qr/artifacts
GET  /api/qr/artifacts
GET  /g/{artifact_id}
GET  /api/wallet-events
POST /api/wallet-events
GET  /api/payout-eligibility
POST /api/payout-eligibility
GET  /api/admin/decisions
POST /api/admin/decisions
POST /api/stripe/create-checkout-session
POST /api/stripe/webhook
```

## Photo-to-SKU flow

`POST /api/photo/analyze` accepts multipart form data:

```text
image: required image file
owner_id: optional
room_type: optional
monetization_goal: optional
user_notes: optional
location_hint: optional
```

The endpoint stores the image, extracts image metadata, creates a photo record, runs the assetification engine, creates inventory records, creates SKU records, creates private listing drafts, creates KPI cards, and writes ProofBook records.

## Owner visibility lifecycle

```text
draft
→ pending_owner_confirmation
→ visible_internal_marketplace
```

Drafts remain private. `/marketplace` only shows records created after owner confirmation.

## Tests

```bash
pytest
```

Current tests cover deterministic assetification, SKU creation, marketplace visibility lifecycle, and ProofBook hash generation.

## Repository role

This repo is now the consolidated MEMBRA KPI wedge: one repo, one Replit-style app, one end-to-end operating loop. The broader MEMBRA ecosystem can still exist as specialized modules, but this repository is the immediate deployable product surface.
