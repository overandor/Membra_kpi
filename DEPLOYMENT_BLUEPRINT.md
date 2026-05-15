# MEMBRA KPI Assetification Marketplace Blueprint

This repository is the deployable build target for the first MEMBRA product wedge: **photo-to-SKU inventory intelligence with owner-approved marketplace visibility**.

## Product

**MEMBRA KPI — Assetification Marketplace**

## One-line promise

Upload a picture of a room, closet, couch, tool, car, shelf, pantry, storage area, or wearable item; MEMBRA converts it into SKU-mapped inventory, monetization suggestions, KPI cards, proof requirements, and listing drafts.

## Core flow

```text
Photo upload
→ AI/fallback inventory analysis
→ SKU map
→ inventory records
→ monetization suggestions
→ KPI cards
→ proof requirements
→ listing drafts
→ owner approval
→ visible marketplace listing
```

## Safety rule

AI may draft. The user approves before any listing becomes visible.

No external buyer contact, payment request, social posting, email, SMS, or settlement action is allowed from this app.

## SKU standard

```text
MEMBRA-{CATEGORY}-{SHORTID}
```

Examples:

```text
MEMBRA-SEAT-8F2A
MEMBRA-STORAGE-19AC
MEMBRA-TOOL-77BD
MEMBRA-WINDOW-5E21
MEMBRA-CLOSET-91FA
MEMBRA-CARAD-34BD
MEMBRA-WEAR-90DA
MEMBRA-RELAY-26FA
```

## Suggested tables

```text
photos
inventory_items
sku_map
listing_drafts
public_listings
kpi_cards
proofbook_entries
publish_requests
ai_chat_events
marketplace_events
```

## Required endpoints

```http
GET  /api/health
GET  /api/dashboard
POST /api/photo/analyze
GET  /api/photos
GET  /api/inventory
GET  /api/sku-map
GET  /api/kpis
GET  /api/proofbook
GET  /api/listings/drafts
GET  /api/listings/public
POST /api/listings/{listing_id}/request-visibility
POST /api/listings/{listing_id}/confirm-visibility
POST /api/ai/chat
GET  /marketplace
GET  /marketplace/{listing_id}
```

## Visibility lifecycle

```text
draft
→ pending_owner_confirmation
→ visible_internal_marketplace
```

Drafts remain private. Only owner-confirmed listings appear on `/marketplace`.

## Image mapping rules

If an image shows clothing, bags, boxes, or closet clutter, suggest:

- clothing resale bundle
- closet shelf storage
- package holding point
- wearable media candidate
- local pickup handoff point
- sorting task listing
- storage bin capacity

If an image shows couch or living room space, suggest:

- couch seat and Wi-Fi workspace
- living room short-use access
- wall poster or QR surface
- window ad surface
- shelf storage slot
- local pickup point

If an image shows a car, suggest:

- rear window ad surface
- side window QR decal
- trunk storage capacity
- local delivery handoff
- mobile campaign route

If an image shows tools, suggest:

- tool rental
- local borrowing
- repair kit access
- pickup/dropoff listing

If an image shows desk or office equipment, suggest:

- workspace access
- content creator setup
- ring light rental
- remote work station
- creator kit rental

## KPI examples

- SKU readiness score
- listing readiness score
- proof readiness score
- local demand match
- asset utilization score
- monthly earning estimate
- owner value score
- advertiser surface value
- trust score
- risk score

## ProofBook events

Write SHA-256 proof entries for:

- photo_analyzed
- sku_map_created
- inventory_items_created
- listing_drafts_created
- kpis_generated
- visibility_requested
- visibility_confirmed

## AI configuration

Use backend-only secrets:

```text
LLM_PROVIDER=groq
GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile
```

If no Groq key exists, deterministic fallback analysis must still create useful records.

## Replit build target

Build a FastAPI + SQLite + neomorphic UI app that works immediately on Replit.

The app is complete when a user can upload an image, get SKU-mapped inventory suggestions, generate KPI cards, create listing drafts, approve visibility, and see confirmed listings on `/marketplace`.
