# Membra KPI

Membra KPI is the analytics and reporting module for the MEMBRA ecosystem.

It converts campaign data, owner activity, proof events, QR/NFC scans, relay activity, payouts, and marketplace operations into decision-ready metrics.

## One-line thesis

Membra KPI turns raw MEMBRA activity into proof-backed dashboards, investor metrics, advertiser reports, owner earnings reports, and operational scorecards.

## Product category

- KPI generator
- proof reporting engine
- campaign analytics module
- owner performance dashboard
- advertiser reporting layer
- executive scorecard generator

## Relationship to other repos

- `Membra_ads` produces campaign, media-kit, proof, scan, and payout data.
- `membra-qr-gateway` displays dashboards and proof reports.
- `membra-relay` produces fulfillment, delivery, and proof-route events.
- `Membra_wear` produces wearable campaign and media-kit data.
- `Membra_wallet` produces payment and payout state.
- `membra` contains umbrella doctrine and shared ProofBook / Devnet rules.

## Core KPI categories

### Campaign KPIs

- campaign status
- funded budget
- active placements
- approved proof rate
- QR scans
- NFC taps
- scan-to-destination rate
- proof rejection rate
- cost per verified placement
- cost per scan

### Owner KPIs

- verified assets
- accepted campaigns
- proof approval rate
- estimated earnings
- released payouts
- payout hold reasons
- asset utilization
- trust score

### Advertiser KPIs

- campaign spend
- active placements
- total scans
- total taps
- proof-approved placements
- geographic coverage
- creative performance
- report exports

### Operations KPIs

- kits generated
- vendor orders
- kits shipped
- kits activated
- proofs needing review
- claims opened
- claims resolved
- payout backlog

## Output formats

- JSON report
- CSV export
- dashboard table
- investor summary
- advertiser campaign report
- owner earnings report
- proof audit report

## Production runtime

This repo now contains a Hugging Face-ready `app.py` that profiles uploaded CSV, Excel, JSON, JSONL, or Parquet datasets, generates structured KPI catalogs through Groq, exports JSON/CSV, and exposes Stripe entitlement hooks.

Required secrets:

- `GROQ_API_KEY`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_ID`
- `APP_BASE_URL`

Optional settings:

- `GROQ_MODEL`
- `REQUIRE_STRIPE=true`
- `FREE_DAILY_LIMIT`
- `PAID_DAILY_LIMIT`
- `ADMIN_TOKEN`

## API routes

- `GET /api/health`
- `GET /api/entitlement?email=user@example.com`
- `POST /api/stripe/create-checkout-session`
- `POST /api/stripe/webhook`
- `POST /api/admin/grant`

## Deploy

Create a Hugging Face Gradio Space, connect this repository, add the secrets above, and run the Space from `app.py`.
