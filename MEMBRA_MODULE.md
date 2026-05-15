# MEMBRA Module Contract — KPI

## Role

Primary production wedge for MEMBRA: photo/data upload to inventory, SKU mapping, KPI cards, ProofBook hashes, private listing drafts, owner-confirmed marketplace visibility, QR artifacts, wallet eligibility, admin review, and Replit-native deployment.

## System inputs

- real image uploads
- CSV/XLSX KPI files
- owner context
- assetification notes
- admin decisions
- QR artifact requests

## System outputs

- photo records
- inventory items
- SKU records
- KPI cards
- ProofBook entries
- private listing drafts
- public/internal marketplace listings after owner confirmation
- payout eligibility records
- QR artifact records

## Health

```text
GET /api/health
GET /api/ready
```

## Replit role

`primary_deployable`

This repo can run alone as the first MEMBRA product.

## Production boundary

AI drafts inventory. Owner confirmation is required before visibility. MEMBRA records payout eligibility only. External rails settle money.
