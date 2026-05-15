# MEMBRA KPI Production Checklist

## Minimum production controls

- Set a strong ADMIN_TOKEN.
- Put the app behind HTTPS.
- Use persistent disk storage for ./data and ./static/uploads.
- Rotate Stripe and LLM keys regularly.
- Add request rate limiting at the reverse proxy layer.
- Back up SQLite or migrate to Postgres before high concurrency.
- Restrict admin endpoints through network or identity controls.
- Monitor upload volume and disk growth.

## Recommended platforms

- Railway
- Fly.io
- Render
- Replit Deployments
- Self-hosted Docker VPS

## Docker deploy

```bash
docker build -t membra-kpi .
docker run -p 8000:8000 --env-file .env membra-kpi
```

## Reverse proxy

Use Cloudflare, NGINX, Traefik, or Caddy in front of the app.

## Production environment variables

Required:

- ADMIN_TOKEN
- APP_BASE_URL

Optional:

- GROQ_API_KEY
- OPENAI_API_KEY
- STRIPE_SECRET_KEY
- STRIPE_WEBHOOK_SECRET
- STRIPE_PRICE_ID

## Scaling note

SQLite is acceptable for prototype and low-to-medium traffic operation. For multi-instance scaling or high write concurrency, migrate to Postgres.
