# MEMBRA KPI Software Architecture

MEMBRA KPI now has a reusable Python package layer under `membra_kpi/`.

The goal is to move the product from a single script into importable engines that can power FastAPI, Gradio, Replit, Hugging Face, tests, and future background workers.

## Package modules

| Module | Responsibility |
|---|---|
| `membra_kpi.assetification` | Deterministic photo/context-to-inventory mapping, SKU assignment, listing draft creation payloads, KPI payloads |
| `membra_kpi.pricing` | Category price bands, location multipliers, conservative estimate labels |
| `membra_kpi.kpi_engine` | KPI card generation, readiness scoring, proof readiness, risk score, local demand match |
| `membra_kpi.proofbook` | Canonical SHA-256 ProofBook entries for photo, inventory, SKU, listing, KPI, visibility, QR, scan, and payout events |
| `membra_kpi.marketplace` | Owner-approved visibility lifecycle: draft -> pending_owner_confirmation -> visible_internal_marketplace |
| `membra_kpi.seed_data` | Demo bundle and product prompts for local tests and seeded demos |

## Core software flow

```text
photo/context input
-> assetify_from_context()
-> detected inventory objects
-> SKU records
-> KPI cards
-> listing drafts
-> ProofBook entries
-> request_visibility()
-> confirm_visibility()
-> public marketplace listing
```

## Safety boundaries

- AI may draft inventory.
- Owner confirmation is required before marketplace visibility.
- Estimates are not guaranteed.
- Proof records do not equal payment.
- External rails settle money.
- No buyer outreach, social posting, email, SMS, or settlement action is performed by these modules.

## Deterministic fallback

The deterministic engine creates useful records even with no LLM or vision API. It uses:

- `room_type`
- `monetization_goal`
- `user_notes`
- `location_hint`
- uploaded filename
- image metadata

This keeps the Replit/Hugging Face demo reliable without external AI credentials.

## Test targets

Run:

```bash
pytest
```

Current tests verify:

- fallback assetification creates required records
- SKU prefixes conform to `MEMBRA-{CATEGORY}-{SHORTID}`
- marketplace visibility lifecycle is owner-confirmation gated
- ProofBook hashes are SHA-256 sized

## Next integration step

The existing `app.py` can import these modules instead of maintaining business logic inline. Recommended integration sequence:

1. wire `/api/photo/analyze` to `assetify_from_context()`
2. persist inventory items and KPI cards
3. persist listing drafts via `create_listing_draft()`
4. persist ProofBook entries via `create_proof_entry()`
5. implement owner visibility request/confirm through `marketplace.py`
6. expose public marketplace listings only after confirmation
