# Connect MEMBRA KPI Vercel Frontend to Render Backend

This repo is split into two deployment roles:

- **Vercel** serves the static frontend: landing page and dashboard.
- **Render** runs the FastAPI backend: uploads, KPI analysis, ProofBook, listings, event outbox, and API routes.

## 1. Deploy backend on Render

Use the included Blueprint:

```text
render.yaml
```

The Render service name is:

```text
membra-kpi-api
```

Expected Render URL:

```text
https://membra-kpi-api.onrender.com
```

If Render gives you a different URL, use that actual URL instead.

## 2. Render environment variables

Set these in Render:

```text
APP_ENV=production
APP_BASE_URL=https://membra-kpi-api.onrender.com
ALLOWED_HOSTS=membra-kpi-api.onrender.com,.onrender.com
CORS_ALLOWED_ORIGINS=https://your-vercel-domain.vercel.app
DB_PATH=/data/membra.db
UPLOAD_DIR=/data/uploads
MAX_UPLOAD_MB=12
RATE_LIMIT_REQUESTS=120
RATE_LIMIT_WINDOW_SECONDS=60
ADMIN_TOKEN_SHA256=<sha256-of-your-admin-token>
```

Optional:

```text
MEMBRA_EVENT_SECRET=<shared-event-secret>
MEMBRA_EVENT_SINKS=
GROQ_API_KEY=
OPENAI_API_KEY=
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_ID=
```

For quick testing only, you can use:

```text
CORS_ALLOWED_ORIGINS=*
```

## 3. Verify Render backend

Open:

```text
https://membra-kpi-api.onrender.com/api/health
https://membra-kpi-api.onrender.com/api/ready
https://membra-kpi-api.onrender.com/api/dashboard
```

Expected result: JSON, not HTML.

If these fail, fix Render first before debugging Vercel.

## 4. Deploy frontend on Vercel

Vercel should use the static build.

Recommended Vercel settings:

```text
Framework Preset: Other
Build Command: npm run build
Output Directory: public
Install Command: npm install
```

The build creates:

```text
public/index.html
public/dashboard.html
public/assets/*
public/membra-config.json
```

## 5. Connect Vercel dashboard to Render

The static frontend has a default backend config:

```text
membra-config.json
```

Default:

```text
https://membra-kpi-api.onrender.com
```

You can override it from the browser:

```text
https://your-vercel-domain.vercel.app/dashboard?api=https://your-render-service.onrender.com
```

Or paste the Render backend URL into the dashboard connection box.

## 6. Common errors

### Vercel 500

The frontend must be static-only. Check Vercel settings:

```text
Build Command: npm run build
Output Directory: public
```

There should be no Vercel serverless function required for the dashboard.

### Dashboard says backend unreachable

Check:

```text
https://your-render-service.onrender.com/api/health
```

Then check CORS:

```text
CORS_ALLOWED_ORIGINS=https://your-vercel-domain.vercel.app
```

### Upload fails

Render must have the disk mounted at:

```text
/data
```

The backend uses:

```text
DB_PATH=/data/membra.db
UPLOAD_DIR=/data/uploads
```

## Production boundary

The Vercel dashboard is only a frontend. Render runs the backend. MEMBRA records proof, listings, analytics, and payout eligibility. It does not custody funds or guarantee earnings.
