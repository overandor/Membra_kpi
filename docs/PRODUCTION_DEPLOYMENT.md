# MEMBRA KPI Production Deployment Guide

This guide converts the Replit-ready app into a production-hardened deployment posture.

## Production readiness level

This repository is now a production-hardened starter for the MEMBRA KPI wedge. It includes runtime security headers, upload validation, rate limiting, admin-token hashing support, health/readiness endpoints, CI, Docker support, and clear safety boundaries.

It is still the operator's responsibility to configure secrets, database backups, object storage, legal policies, and monitoring before exposing real public users.

## Required deployment variables

```text
APP_ENV=production
APP_BASE_URL=https://your-domain.example
ALLOWED_HOSTS=your-domain.example,.replit.app
DB_PATH=/app/data/membra.db
UPLOAD_DIR=/app/static/uploads
MAX_UPLOAD_MB=12
RATE_LIMIT_REQUESTS=120
RATE_LIMIT_WINDOW_SECONDS=60
ADMIN_TOKEN_SHA256=<sha256-of-strong-token>
GROQ_API_KEY=<optional>
GROQ_MODEL=llama-3.3-70b-versatile
OPENAI_API_KEY=<optional>
OPENAI_MODEL=gpt-4o-mini
STRIPE_SECRET_KEY=<optional>
STRIPE_WEBHOOK_SECRET=<optional>
STRIPE_PRICE_ID=<optional>
```

Generate `ADMIN_TOKEN_SHA256`:

```bash
python -c "import hashlib; print(hashlib.sha256(b'your-strong-token').hexdigest())"
```

When using the admin UI or admin API, send the original token value, not the hash.

## Replit deployment

1. Import the GitHub repository into Replit.
2. Add secrets from `.env.example`.
3. Set a strong `ADMIN_TOKEN_SHA256`.
4. Start the app. `.replit` runs:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

5. Open `/api/health` and `/api/ready`.
6. Resolve any `/api/ready` warnings before public traffic.

## Docker deployment

```bash
docker build -t membra-kpi .
docker run --rm -p 8000:8000 \
  -e APP_ENV=production \
  -e APP_BASE_URL=http://localhost:8000 \
  -e ADMIN_TOKEN_SHA256=<hash> \
  -v "$PWD/data:/app/data" \
  -v "$PWD/static/uploads:/app/static/uploads" \
  membra-kpi
```

Then verify:

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/ready
```

## Production smoke test checklist

- [ ] `/` loads the landing page.
- [ ] `/api/health` returns `ok: true`.
- [ ] `/api/ready` returns `ok: true` and no critical warnings.
- [ ] `/assetify` accepts a valid JPG/PNG/WebP image.
- [ ] Invalid uploads are rejected.
- [ ] `/api/photo/analyze` creates inventory, SKU, KPI, ProofBook, and private draft records.
- [ ] Drafts do not appear in `/marketplace`.
- [ ] Owner visibility request sets `pending_owner_confirmation`.
- [ ] Owner confirmation creates a public listing and payout-eligibility record.
- [ ] QR artifact creation works.
- [ ] `/g/{artifact_id}` records a scan event.
- [ ] `/kpi` accepts CSV/XLSX and rejects unsupported file types.
- [ ] Admin decisions require the configured admin token.
- [ ] Stripe endpoints return `Stripe not configured` when secrets are absent.
- [ ] Stripe webhook signature verification works when configured.
- [ ] CI passes.

## Data protection requirements before real users

Before collecting real public user data, add or configure:

- managed database or reliable SQLite volume backup
- object storage for uploads, or persistent Replit storage with backup policy
- image/content moderation workflow
- data deletion endpoint and operator process
- privacy policy and terms of service
- consent revocation process
- admin audit export
- incident response contact

## Operating boundaries

MEMBRA KPI records proof and payout eligibility. It does not custody funds or settle payments. Estimates are not guaranteed. Owner approval is required before listing visibility.
