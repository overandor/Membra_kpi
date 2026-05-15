# MEMBRA KPI Vercel Frontend

This repo now includes a static Vercel frontend that shows a real landing page and a backend-connected dashboard.

## Files

```text
index.html              landing page
dashboard.html          dashboard shell
assets/membra.css       neomorphic dark-gold UI
assets/membra.js        dashboard backend connector
api/config.js           Vercel serverless config endpoint
vercel.json             Vercel routing and headers
package.json            Vercel build verification
scripts/verify_frontend.js
```

## Vercel behavior

- `/` renders the MEMBRA KPI landing page.
- `/dashboard` renders the MEMBRA KPI dashboard.
- `/app`, `/marketplace`, `/proofbook`, and `/wallet` route to the dashboard shell.
- Unknown non-API routes fall back to the landing page.

## Connect dashboard to backend

The Vercel dashboard is static. It needs a deployed FastAPI backend URL.

Use one of these methods:

### Option A — Vercel env variable

Set this in Vercel project settings:

```text
MEMBRA_API_BASE=https://your-membra-kpi-backend.example.com
```

The frontend reads it from:

```text
/api/config
```

### Option B — URL parameter

Open:

```text
https://your-vercel-domain.vercel.app/dashboard?api=https://your-membra-kpi-backend.example.com
```

### Option C — dashboard input

Open `/dashboard`, paste the backend URL into the connection box, and click Connect. The URL is stored in browser `localStorage`.

## Backend CORS

The FastAPI backend security helper now emits CORS headers for the dashboard.

Recommended backend environment:

```text
CORS_ALLOWED_ORIGINS=https://your-vercel-domain.vercel.app
```

For testing only:

```text
CORS_ALLOWED_ORIGINS=*
```

## Live dashboard sections

The dashboard calls these backend endpoints:

```text
GET  /api/health
GET  /api/ready
GET  /api/dashboard
GET  /api/listings/public
GET  /api/proofbook
GET  /api/events/outbox/stats
POST /api/photo/analyze
POST /api/events/outbox/replay
```

## Important boundary

The Vercel frontend does not fake production records. If the backend is not configured or unreachable, the dashboard shows a disconnected state instead of invented metrics.
