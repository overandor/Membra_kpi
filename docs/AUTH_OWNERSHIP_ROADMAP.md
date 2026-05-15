# MEMBRA KPI Auth and Ownership Roadmap

This document defines the production-grade multi-user direction for MEMBRA KPI.

## Current new primitives

The repository now includes:

- `membra_kpi/auth.py` for PBKDF2 password hashing, session token generation, role checks, and email normalization.
- `migrations/001_auth_privacy.sql` for users, sessions, consent records, privacy requests, and ownership audit events.
- `scripts/apply_migrations.py` to apply schema migrations.
- `scripts/create_admin_user.py` to bootstrap or rotate a local admin account.
- `membra_kpi/privacy.py` for owner-scoped export/delete query planning.

## Role model

| Role | Purpose |
|---|---|
| `owner` | Uploads photos/data, owns inventory, controls listing visibility |
| `operator` | Reviews proofs, risk flags, and listing safety |
| `admin` | Full administrative control, token rotation, privacy completion, incident response |

## Ownership model

Every production write should attach an owner or actor:

- `photos.owner_id`
- `inventory_items.owner_id`
- `wallet_events.user_id`
- `payout_eligibility.user_id`
- `ai_chat_events.owner_id`
- listing ownership via `listing_drafts -> inventory_items.owner_id`
- public listing ownership via `public_listings -> listing_drafts -> inventory_items.owner_id`

## Required next integration

The schema and primitives are now present. The next code integration should:

1. Add `/auth/register`, `/auth/login`, `/auth/logout`, and `/auth/me`.
2. Set secure HTTP-only session cookies.
3. Resolve the current user from the session cookie.
4. Replace free-form `owner_id` form input with authenticated `user_id`.
5. Limit owner pages to current-owner rows.
6. Require operator/admin role for admin review.
7. Add privacy request endpoints:
   - `POST /api/privacy/export-request`
   - `POST /api/privacy/delete-request`
   - `GET /api/privacy/export/{request_id}`
   - `POST /api/admin/privacy/{request_id}/complete`
8. Record ownership audit events for visibility request, visibility confirmation, admin decisions, exports, and deletions.

## Production acceptance tests

Before broad beta:

- owner A cannot see owner B drafts
- owner A cannot publish owner B draft
- owner cannot call admin mutation endpoints
- operator can review but cannot rotate admin credentials
- admin can complete privacy request
- logout invalidates session
- expired session fails
- consent record exists before public listing visibility

## Boundary

This is the line between a hardened single-app MVP and a multi-user SaaS. The repository now has the foundational auth/privacy pieces, but the main FastAPI routes still need full session integration before broad public use.
