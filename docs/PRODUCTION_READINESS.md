# MEMBRA KPI Production Readiness Plan

## Current production target

MEMBRA KPI is the flagship deployable MEMBRA product.

The production goal is one working loop:

```text
photo upload
→ image/context assetification
→ SKU-mapped inventory
→ KPI valuation
→ private listing draft
→ owner confirmation
→ marketplace visibility
→ ProofBook hash record
→ dashboard reporting
```

## Production readiness score

Current estimate: **60/100**

Why:

- Working FastAPI app foundation exists.
- SQLite persistence exists.
- Image upload workflow exists.
- Assetification and SKU generation exist.
- KPI generation exists.
- ProofBook hash entries exist.
- Listing draft and owner confirmation lifecycle exist.
- Marketplace visibility flow exists.

Still missing:

- user authentication
- role-based permissions
- Postgres/Supabase production database
- hosted object storage for images
- real computer vision bounding boxes
- moderation queue
- CI coverage across all endpoints
- deployment smoke tests
- payment provider review
- legal/compliance review
- real customer validation

## Production gates

### Gate 1 — Runtime

Required:

- app starts with one command
- `/api/health` returns JSON
- `/dashboard` renders
- `/assetify` or `/inventory` accepts image upload
- no missing static assets
- no broken imports

### Gate 2 — Database

Required:

- all tables auto-create on startup
- migrations documented
- no destructive startup behavior
- image records persist
- SKU records persist
- KPI cards persist
- ProofBook records persist
- listing drafts persist
- confirmed marketplace listings persist

### Gate 3 — Upload security

Required:

- file size limit
- extension validation
- MIME validation
- no executable upload
- unique filenames
- static path isolation
- clear error messages

### Gate 4 — Marketplace safety

Required:

- AI creates draft listings only
- drafts are private
- owner must request visibility
- owner must confirm visibility
- confirmed listing appears internally
- no external posting or buyer contact
- all publish actions write ProofBook entries

### Gate 5 — AI fallback

Required:

- app works without Groq key
- deterministic fallback creates usable inventory
- invalid AI JSON does not break workflow
- fallback writes records and ProofBook entries

### Gate 6 — ProofBook

Required:

- every important mutation writes hash
- hash is SHA-256 over canonical JSON
- proof entries are visible in UI
- proof entries are queryable by API

### Gate 7 — KPI engine

Required:

- every inventory item creates KPI cards
- KPI cards are stored
- KPI dashboard loads from database
- KPI values are labeled as estimates
- no guaranteed income claims

### Gate 8 — Auth and roles

Required before real users:

- owner accounts
- admin accounts
- advertiser/operator roles
- protected admin routes
- session or JWT auth
- CSRF strategy for forms
- audit trails for admin decisions

### Gate 9 — Deployment

Required:

- `.env.example`
- Replit instructions
- Dockerfile
- production start command
- health-check command
- secrets policy
- backup policy

### Gate 10 — Customer readiness

Required:

- onboarding copy
- sample demo assets
- support contact
- privacy policy draft
- terms of service draft
- user deletion/export path

## Next engineering tasks

1. Add endpoint smoke tests.
2. Add Dockerfile.
3. Add `.env.example` if missing.
4. Add CI workflow.
5. Add auth skeleton.
6. Add Postgres-ready DB layer.
7. Add image overlay/bounding-box roadmap.
8. Add deployment runbook.

## Production doctrine

MEMBRA KPI does not promise guaranteed income.

MEMBRA KPI converts physical reality into structured inventory, estimated KPIs, draft listings, proof requirements, and owner-controlled marketplace visibility.

Proof is not payment.
Eligibility is not settlement.
External rails settle money.
