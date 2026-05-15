# MEMBRA KPI API Contract

This document defines the production API surface for the MEMBRA KPI Assetification Marketplace.

## API doctrine

MEMBRA KPI converts real-world uploads into structured economic inventory.

The API must preserve four boundaries:

1. AI creates drafts, not public commitments.
2. Owner confirmation is required before marketplace visibility.
3. ProofBook records evidence and audit events, not payment settlement.
4. Payout eligibility is not payment; external rails settle money.

## Health

### GET `/api/health`

Returns runtime readiness.

Expected response:

```json
{
  "ok": true,
  "app": "MEMBRA KPI Assetification Marketplace",
  "version": "1.1.0",
  "database": "connected"
}
```

## Dashboard

### GET `/api/dashboard`

Returns database-backed record counts and latest operational state.

Required fields:

```json
{
  "counts": {
    "photos": 0,
    "inventory_items": 0,
    "sku_map": 0,
    "listing_drafts": 0,
    "public_listings": 0,
    "kpi_cards": 0,
    "proofbook_entries": 0
  }
}
```

## Photo assetification

### POST `/api/photo/analyze`

Accepts multipart form data.

Fields:

```text
image: required JPEG, PNG, or WebP
owner_id: optional
room_type: optional
monetization_goal: optional
user_notes: optional
location_hint: optional
```

Required behavior:

1. Validate image.
2. Save upload.
3. Create photo row.
4. Run AI or deterministic assetification.
5. Create inventory items.
6. Create SKU map records.
7. Create private listing drafts.
8. Create KPI cards.
9. Create ProofBook entries.
10. Return created records.

Response shape:

```json
{
  "success": true,
  "photo_id": "photo_...",
  "inventory_items_created": 5,
  "sku_records_created": 5,
  "listing_drafts_created": 5,
  "kpi_cards_created": 50,
  "proofbook_entries_created": 4,
  "analysis": {},
  "inventory_items": [],
  "sku_map": [],
  "listing_drafts": [],
  "kpi_cards": [],
  "proofbook_entries": []
}
```

Failure response:

```json
{
  "success": false,
  "error": {
    "code": "UPLOAD_INVALID",
    "message": "Only JPEG, PNG, and WebP uploads are supported."
  }
}
```

## Inventory

### GET `/api/photos`

Returns uploaded photo records.

### GET `/api/inventory`

Returns mapped inventory items.

Each item should include:

```text
inventory_item_id
source_photo_id
owner_id
sku
detected_name
asset_type
visual_evidence
monetization_type
listing_type
description
suggested_price_low
suggested_price_high
pricing_unit
confidence
kpi_score
proof_required_json
risk_flags_json
recommended_action
status
created_at
```

## SKU Map

### GET `/api/sku-map`

Returns SKU records.

SKU format:

```text
MEMBRA-{CATEGORY}-{SHORTID}
```

Examples:

```text
MEMBRA-SEAT-8F2A
MEMBRA-STORAGE-19AC
MEMBRA-WINDOW-5E21
```

## KPI Cards

### GET `/api/kpis`

Returns KPI cards created from uploads, inventory, campaign data, or manual KPI uploads.

KPI fields:

```text
kpi_id
source_photo_id
inventory_item_id
title
value
score
category
explanation
created_at
```

## Listing lifecycle

### GET `/api/listings/drafts`

Returns private listing drafts.

Drafts must not appear on `/marketplace`.

### GET `/api/listings/public`

Returns only owner-confirmed visible listings.

### POST `/api/listings/{listing_id}/request-visibility`

Moves listing from:

```text
draft → pending_owner_confirmation
```

Writes ProofBook event:

```text
visibility_requested
```

### POST `/api/listings/{listing_id}/confirm-visibility`

Moves listing from:

```text
pending_owner_confirmation → visible_internal_marketplace
```

Creates a public marketplace record.

Writes ProofBook event:

```text
visibility_confirmed
```

No external posting, external buyer contact, payment request, or settlement may occur from this endpoint.

## ProofBook

### GET `/api/proofbook`

Returns audit entries.

Every important mutation must write a ProofBook entry.

Required events:

```text
photo_analyzed
picture_inventory_mapped
sku_map_created
inventory_items_created
listing_drafts_created
kpis_generated
visibility_requested
visibility_confirmed
ai_concierge_response
qr_artifact_created
scan_recorded
wallet_event_created
payout_eligibility_created
admin_decision_created
```

Hash rule:

```python
json.dumps(payload, sort_keys=True, separators=(",", ":"))
sha256(payload.encode()).hexdigest()
```

## AI Concierge

### POST `/api/ai/chat`

Request:

```json
{
  "message": "What is my strongest SKU?",
  "owner_id": "optional_owner"
}
```

The AI Concierge must read real database context:

- photos
- inventory items
- SKU map
- KPI cards
- listing drafts
- public listings
- ProofBook entries
- payout eligibility where applicable

It may recommend actions, but it may not bypass owner confirmation.

## QR artifacts

### POST `/api/qr/artifacts`

Creates QR-trackable artifact records.

### GET `/api/qr/artifacts`

Lists artifacts.

### GET `/g/{artifact_id}`

Records scan and redirects through MEMBRA-controlled attribution.

## Wallet and payout eligibility

### GET `/api/wallet-events`

Returns recorded wallet events.

### POST `/api/wallet-events`

Creates wallet event records.

### GET `/api/payout-eligibility`

Returns payout eligibility records.

### POST `/api/payout-eligibility`

Creates eligibility records.

Boundary:

```text
Eligibility is not settlement.
External rails settle money.
```

## Admin

### GET `/api/admin/decisions`

Returns admin review decisions.

### POST `/api/admin/decisions`

Protected by admin token.

Creates review, risk, moderation, or operator action records.

## Stripe

### POST `/api/stripe/create-checkout-session`

Optional. Returns configuration error when Stripe is not configured.

### POST `/api/stripe/webhook`

Optional. Requires webhook signature verification when configured.

## Versioning recommendation

Current routes are unversioned for demo velocity.

Production should add:

```text
/v1/api/...
```

while preserving current routes as compatibility aliases.
