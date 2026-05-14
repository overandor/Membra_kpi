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

## Current stage

Module scaffold. The working KPI app currently lives in `overandor/membra/app.py`; this repo should become the dedicated home for the KPI generator and MEMBRA analytics reports.
