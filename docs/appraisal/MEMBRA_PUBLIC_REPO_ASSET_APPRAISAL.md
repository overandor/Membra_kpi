# MEMBRA Public Repo Asset Appraisal

Date: 2026-05-15

## Scope

This is a rough public-repository asset appraisal, not an acquisition valuation, tax valuation, securities valuation, or investment offer.

The appraisal applies a deed/permission-backend penalty because MEMBRA's core value depends on proving the right to monetize physical and local assets.

## Repo appraisal table

| Repo | Appraised value |
|---|---:|
| `membra` | $18,000 |
| `Membra_api` | $7,500 |
| `Membra_proofbook` | $6,500 |
| `Membra_contracts` | $5,000 |
| `Membra_admin-` | $4,000 |
| `Membra_wallet` | $3,500 |
| `Membra_vendor_adapters` | $3,000 |
| `membra-qr-gateway` | $2,750 |
| `Membra_mobile` | $2,500 |
| `Membra_ads` | $2,250 |
| `Membra_kpi` | $1,750 |
| `Membra_demo_data` | $1,250 |
| `membra-relay` | $1,250 |
| `Membra_wear` | $1,000 |
| `Membra_investor_room-` | $750 |

## Gross repo-asset value

**$61,000**

## Deed-backend penalty

Because the public repo set does not clearly show a complete deed/permission backend with ownership attestations, listing authority, tenant-isolated rights records, dispute workflow, and enforced approval chain, a penalty is applied.

Penalty: **35%**

Penalty amount: **$21,350**

## Final adjusted appraisal

**$39,650**

Rounded:

**Approximately $40,000**

## Valuation interpretation

The valuation should be read as a repo-asset value for public code, structure, architecture, and product thesis.

It is not a valuation of operating revenue, customer traction, production infrastructure, or enforceable legal rights.

## Main value driver

The strongest asset is the MEMBRA architecture thesis:

> MEMBRA is a proof-backed permission layer for local commerce that turns physical-world inventory into reviewable, KPI-scored, multilingual, auditable monetization opportunities.

## Main valuation suppressor

The largest discount comes from the absence of a visibly complete deed/permission backend.

MEMBRA must prove:

1. who owns or controls the physical asset
2. who has authority to list it
3. who approved monetization
4. what the permission scope is
5. when the permission expires
6. whether disputes exist
7. whether the asset is tenant-isolated
8. whether ProofBook records are immutable
9. whether admin review is enforced
10. whether public activation is blocked until approval

## Best upside path

Make `Membra_api`, `Membra_proofbook`, and `Membra_contracts` into the real deed/permission backend.

That means implementing:

- ownership attestations
- permission grants
- listing authority records
- tenant-isolated rights tables
- asset-owner identity records
- contract/deed references
- dispute workflow
- enforced approval chain
- immutable ProofBook events
- API-level RBAC
- production persistence
- deployable workflows

## Upside appraisal target

If the deed/permission backend is implemented cleanly with auth, persistence, audit trails, tenant isolation, and deployable workflows, the appraisal could plausibly move from:

**~$40,000**

toward:

**$150,000 to $300,000+**

This upside depends on execution quality, not just documentation.

## Implementation priority

### Phase 1: deed backend schema

Create canonical backend records:

- `asset_owners`
- `physical_assets`
- `ownership_attestations`
- `permission_grants`
- `listing_authority`
- `deed_documents`
- `approval_chain_events`
- `disputes`
- `revocations`

### Phase 2: API enforcement

Every listing activation must verify:

- owner exists
- asset exists
- permission grant exists
- listing authority exists
- no active dispute
- no revocation
- tenant_id matches
- admin approval completed

### Phase 3: ProofBook integration

Append ProofBook events for:

- owner registered
- asset registered
- deed uploaded
- permission granted
- listing authority granted
- admin approved
- listing activated
- dispute opened
- permission revoked

### Phase 4: production hardening

Add:

- Postgres migrations
- RBAC middleware
- tenant isolation tests
- route integration tests
- object storage for documents
- audit dashboards
- backup/restore
- deployment checks

## Deed-backend acceptance criteria

The deed/permission backend is considered appraisal-grade only when:

1. a user can register an asset owner
2. a physical asset can be registered
3. ownership can be attested
4. a deed or permission document can be referenced
5. listing authority can be granted
6. a listing cannot activate without authority
7. disputes can block activation
8. revocations immediately stop monetization
9. all state changes append ProofBook events
10. tests prove tenant isolation and approval enforcement

## Strategic conclusion

The current public repo set is worth roughly **$40K adjusted** as public code/IP architecture.

The fastest path to **$150K-$300K+** is not adding more surface modules. It is completing the deed/permission backend that proves MEMBRA can legally and operationally monetize physical-world assets.
