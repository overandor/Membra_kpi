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
→ picture-to-inventory mapping
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

## Picture-to-inventory mapping

The core product mechanic is **picture-to-inventory mapping**.

A user uploads a picture. MEMBRA must turn the visual contents into structured inventory records that can be priced, scored, listed, verified, and later approved for marketplace visibility.

The system must not merely caption the image. It must produce normalized inventory objects.

### Required mapping pipeline

```text
uploaded_picture
→ image metadata extraction
→ visual context analysis
→ detected object candidates
→ monetizable asset interpretation
→ SKU assignment
→ inventory record creation
→ listing draft creation
→ KPI scoring
→ proof requirement generation
→ ProofBook hash record
```

### Input fields

`POST /api/photo/analyze` must accept:

```text
image: required file
owner_id: optional
room_type: optional
monetization_goal: optional
user_notes: optional
location_hint: optional
```

### Required output shape

```json
{
  "success": true,
  "photo_id": "photo_...",
  "room_summary": "",
  "inventory_items_created": 0,
  "sku_records_created": 0,
  "listing_drafts_created": 0,
  "kpi_cards_created": 0,
  "proofbook_entries_created": 0,
  "detected_inventory": [
    {
      "sku": "MEMBRA-STORAGE-19AC",
      "source_photo_id": "photo_...",
      "detected_name": "Closet shelf storage",
      "asset_type": "storage_space",
      "visual_evidence": "visible shelf, bin, closet, or storage area",
      "monetization_type": "store",
      "listing_type": "storage shelf rental",
      "suggested_price_low": 12,
      "suggested_price_high": 35,
      "pricing_unit": "monthly",
      "confidence": 0.82,
      "kpi_score": 78,
      "proof_required": ["clear shelf photo", "access rules", "owner confirmation"],
      "risk_flags": ["liability review recommended"],
      "recommended_action": "Measure shelf dimensions and create draft listing.",
      "status": "draft"
    }
  ]
}
```

### Mapping fields per inventory item

Every mapped inventory item must include:

- `sku`
- `source_photo_id`
- `inventory_item_id`
- `detected_name`
- `asset_type`
- `visual_evidence`
- `monetization_type`
- `listing_type`
- `description`
- `suggested_price_low`
- `suggested_price_high`
- `pricing_unit`
- `confidence`
- `kpi_score`
- `proof_required`
- `risk_flags`
- `recommended_action`
- `status`

### Monetization interpretation table

| Visual signal | Inventory interpretation | Monetization type | Listing type | SKU category |
|---|---|---|---|---|
| Couch, chair, seating | Temporary seating or workspace access | rent/access | couch seat rental | SEAT |
| Desk, monitor, lamp | Workspace or creator station | rent/access | workspace access | WORK |
| Closet, shelf, bins | Storage capacity | store/rent | closet or shelf storage | STORAGE |
| Tool, drill, vacuum | Borrowable local tool | lend/rent | tool rental | TOOL |
| Window, glass door | Physical ad surface | advertise | window ad surface | WINDOW |
| Car rear/side surface | Mobile local ad surface | advertise | car ad space | CARAD |
| Hoodie, shirt, backpack | Wearable media | advertise | wearable ad space | WEAR |
| Boxes, bags, entryway | Package handoff point | relay | local handoff point | RELAY |
| Pantry, consumables | Surplus household supply | sell/bundle | pantry surplus | PANTRY |
| Clothing pile | Resale or donation bundle | sell/bundle | clothing resale bundle | RESALE |
| Empty parking or driveway | Vehicle storage/access | rent | parking space | PARKING |
| Wall, poster area | QR/poster campaign surface | advertise | wall QR surface | WALLAD |

### Fallback mapping rule

If Groq or image analysis fails, the app must still create useful picture-to-inventory mappings from:

- `room_type`
- `monetization_goal`
- `user_notes`
- uploaded filename
- image dimensions

Fallback must create at least:

- 5 inventory items
- 5 SKU records
- 5 listing drafts
- 10 KPI cards
- 4 ProofBook entries

### Example fallback for cluttered room, closet, or clothing image

- `MEMBRA-RESALE-*`: Clothing resale bundle
- `MEMBRA-STORAGE-*`: Closet shelf storage
- `MEMBRA-RELAY-*`: Package holding or pickup point
- `MEMBRA-WEAR-*`: Wearable media candidate
- `MEMBRA-STORAGE-*`: Storage bin capacity
- `MEMBRA-TASK-*`: Sorting or decluttering task listing

### Example fallback for apartment/living room image

- `MEMBRA-SEAT-*`: Couch seat + Wi-Fi workspace
- `MEMBRA-WINDOW-*`: Window ad surface
- `MEMBRA-WALLAD-*`: Wall QR poster surface
- `MEMBRA-STORAGE-*`: Shelf storage slot
- `MEMBRA-RELAY-*`: Local handoff pickup point

### Example fallback for car image

- `MEMBRA-CARAD-*`: Rear window ad space
- `MEMBRA-CARAD-*`: Side window QR decal
- `MEMBRA-STORAGE-*`: Trunk storage capacity
- `MEMBRA-RELAY-*`: Local delivery handoff route
- `MEMBRA-CAMPAIGN-*`: Mobile campaign route

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
- picture_inventory_mapped
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