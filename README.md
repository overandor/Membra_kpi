# Membra KPI

**Membra KPI is the reporting and analytics module for MEMBRA Labs and the MEMBRA Proof Network.**

It converts campaign, proof, QR/NFC scan, owner, advertiser, wallet, relay, and marketplace activity into decision-ready metrics.

## Company Context

- Company: **MEMBRA Labs**
- Flagship product: **MEMBRA Proof Network**
- Module: **Membra KPI**
- Category: KPI generator, proof reporting engine, advertiser reports, owner reports, investor scorecards

## One-Line Thesis

Membra KPI turns raw MEMBRA activity into proof-backed dashboards, investor metrics, advertiser reports, owner earnings reports, and operational scorecards.

## Product Role

Membra KPI is the analytics layer for the company package.

It should produce:

- campaign reports
- owner reports
- advertiser reports
- proof audit reports
- payout/reward reports
- relay reports
- investor summaries
- CSV/JSON exports
- dashboard tables

## Core KPI Categories

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

## Production Runtime

This repo contains a Hugging Face-ready `app.py` that profiles uploaded CSV, Excel, JSON, JSONL, or Parquet datasets, generates structured KPI catalogs through Groq, exports JSON/CSV, and exposes Stripe entitlement hooks.

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

## API Routes

- `GET /api/health`
- `GET /api/entitlement?email=user@example.com`
- `POST /api/stripe/create-checkout-session`
- `POST /api/stripe/webhook`
- `POST /api/admin/grant`

## Integration Points

| Repo | KPI Source |
|---|---|
| `overandor/Membra_ads` | campaigns, media kits, proof, scans, owners, advertisers |
| `overandor/membra-qr-gateway` | dashboard rendering target |
| `overandor/Membra_wallet` | funding, reward, payout, reconciliation states |
| `overandor/Membra_wear` | wearable campaigns and media kits |
| `overandor/membra-relay` | route, delivery, handoff, and proof-route events |
| `overandor/Membra_proofbook` | hash records, audit records, verified reports |
| `overandor/membra` | company hub, buyer package, doctrine, productization docs |

## Output Formats

- JSON report
- CSV export
- dashboard table
- investor summary
- advertiser campaign report
- owner earnings report
- proof audit report

## Deploy

Create a Hugging Face Gradio Space, connect this repository, add the secrets above, and run the Space from `app.py`.

## Safety Rules

- report only observed or demo-labeled data
- do not imply guaranteed advertiser performance
- do not imply guaranteed owner income
- separate estimated, eligible, held, released, and failed rewards
- label demo data clearly
- preserve auditability back to proof records

## Current Stage

Runnable KPI/reporting app plus module documentation. Highest priority is connecting reports directly to `Membra_ads`, `Membra_wallet`, `Membra_proofbook`, and `Membra_demo_data`.