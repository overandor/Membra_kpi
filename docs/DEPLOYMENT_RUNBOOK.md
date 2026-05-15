# MEMBRA KPI Deployment Runbook

This runbook turns MEMBRA KPI from a local prototype into a controlled public deployment.

## Production target

Run one reliable public app that demonstrates:

```text
photo upload
→ SKU-mapped inventory
→ KPI generation
→ ProofBook hash
→ private listing draft
→ owner-confirmed marketplace visibility
```

## Required preflight checks

Before deploying publicly, verify:

```bash
pip install -r requirements.txt
pytest -q
uvicorn app:app --host 0.0.0.0 --port 8000
curl -fsS http://localhost:8000/api/health
```

Expected health response includes:

```json
{
  "ok": true,
  "app": "MEMBRA KPI Assetification Marketplace"
}
```

## Environment variables

Use `.env.example` as the source of truth.

Minimum public deployment:

```text
APP_ENV=production
APP_BASE_URL=https://your-domain.example
ALLOWED_HOSTS=your-domain.example,.replit.app,.replit.dev
DB_PATH=./data/membra.db
UPLOAD_DIR=./static/uploads
MAX_UPLOAD_MB=12
RATE_LIMIT_REQUESTS=120
RATE_LIMIT_WINDOW_SECONDS=60
ADMIN_TOKEN_SHA256=<sha256-of-strong-admin-token>
```

Optional AI:

```text
GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
```

Optional Stripe:

```text
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_ID=
```

## Replit deployment

1. Import the repository into Replit.
2. Add secrets from `.env.example`.
3. Run:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

4. Open `/api/health`.
5. Open `/assetify` or `/inventory`.
6. Upload a JPEG/PNG/WebP image.
7. Confirm records appear in:
   - `/api/photos`
   - `/api/inventory`
   - `/api/sku-map`
   - `/api/kpis`
   - `/api/proofbook`
8. Request listing visibility.
9. Confirm listing visibility.
10. Confirm the listing appears on `/marketplace`.

## Docker deployment

Build:

```bash
docker build -t membra-kpi .
```

Run:

```bash
docker run --rm -p 8000:8000 \
  -e APP_ENV=production \
  -e ALLOWED_HOSTS=localhost,127.0.0.1 \
  -e ADMIN_TOKEN_SHA256=<hash> \
  membra-kpi
```

Health:

```bash
curl -fsS http://localhost:8000/api/health
```

## Data persistence

SQLite is acceptable for prototype and controlled demo deployment.

For production users, migrate to Postgres/Supabase and external object storage.

Current local persistence paths:

```text
./data/membra.db
./static/uploads
```

Back these up before redeploying.

## Smoke test checklist

- `/api/health` returns ok
- `/dashboard` loads
- `/assetify` or `/inventory` accepts image upload
- inventory item rows are created
- SKU rows are created
- KPI cards are created
- ProofBook hashes are created
- listing drafts remain private
- confirmed listings appear on `/marketplace`
- admin mutations require token
- no API keys appear client-side

## Rollback

If deployment breaks:

1. Stop the app.
2. Restore the previous database backup.
3. Revert to the previous known-good commit.
4. Re-run tests.
5. Redeploy.

## Production boundaries

- AI outputs are drafts.
- Owners approve visibility.
- Marketplace visibility is internal to MEMBRA unless a future external integration is explicitly added.
- Payout eligibility is not payment.
- External rails settle money.
- No guaranteed income claims.
