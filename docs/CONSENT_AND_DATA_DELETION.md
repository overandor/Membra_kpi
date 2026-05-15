# MEMBRA KPI Consent and Data Deletion Policy

MEMBRA KPI is built around owner-controlled assetification. AI may draft records, but the owner controls marketplace visibility.

## Consent principles

- No consent, no public listing.
- No owner confirmation, no marketplace visibility.
- Proof records are audit records, not consent to sell, rent, advertise, or settle money.
- Payout eligibility is not settlement.
- Users should not upload private keys, seed phrases, raw financial credentials, or unconsented personal material.

## Required consent fields for production

For public production, collect and store these fields with each owner-controlled listing:

- owner identifier
- asset identifier
- ownership/control attestation
- lease/building/HOA/local-rule acknowledgement
- visibility scope
- location precision scope
- proof retention scope
- listing category
- permitted use
- payout eligibility acknowledgement
- consent timestamp
- consent revocation instructions

## Current implementation

The current production-hardened starter enforces the visibility lifecycle:

```text
draft -> pending_owner_confirmation -> visible_internal_marketplace
```

The system records ProofBook events for visibility request and confirmation.

## Data deletion process

Until a full self-service deletion UI exists, operators should process deletion requests manually:

1. Verify the requester controls the relevant owner/account identifier.
2. Export the relevant records for internal audit if legally required.
3. Remove or anonymize uploaded files from `static/uploads`.
4. Remove private listing drafts.
5. Remove public listings or set them to unavailable if a historical audit record must remain.
6. Keep minimal ProofBook metadata only where required for fraud/audit/legal defense.
7. Record an admin decision explaining the deletion action.
8. Confirm completion to the requester.

## Future production endpoint recommendation

Add:

```text
POST /api/privacy/delete-request
GET  /api/privacy/delete-request/{request_id}
POST /api/admin/privacy/{request_id}/complete
```

These endpoints should support identity verification, export, deletion/anonymization, and audit logging.

## High-risk categories

Require manual review before visibility for:

- apartment access
- storage of third-party goods
- parking access
- vehicle ad placement
- first-floor window ad placement
- wearable ad campaigns
- tools or equipment lending
- local relay or handoff jobs
- anything involving minors, restricted goods, health data, finance data, or regulated services
