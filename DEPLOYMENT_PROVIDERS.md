# MEMBRA KPI Deployment Providers

## Supported deployment targets

### Netlify
Files:
- `netlify.toml`

Recommended:
- frontend delivery
- lightweight API routing
- edge deployment
- static dashboard hosting

Environment variables:
- ADMIN_TOKEN
- HF_TOKEN
- GROQ_API_KEY
- OPENAI_API_KEY
- STRIPE_SECRET_KEY
- STRIPE_WEBHOOK_SECRET
- APP_ENV

Suggested deploy hooks:
- production deploy hook
- preview deploy hook
- nightly validation hook

Recommended architecture:
- Netlify frontend
- Render API backend
- Supabase Postgres
- Neon pgvector
- Redis/Upstash queues

---

### Render
Files:
- `render.yaml`

Recommended:
- FastAPI backend runtime
- worker orchestration
- scheduled jobs
- ProofBook services

Suggested services:
- API node
- KPI worker node
- embedding worker node
- HF inference worker
- queue scheduler

Recommended environment variables:
- APP_ENV
- PORT
- HF_TOKEN
- GROQ_API_KEY
- OPENAI_API_KEY
- STRIPE_SECRET_KEY
- STRIPE_WEBHOOK_SECRET

---

## Recommended production architecture

Frontend:
- Netlify
- Next.js
- React
- Transformers.js

Backend:
- FastAPI
- Render
- Redis
- Celery or Dramatiq

Database:
- Postgres
- pgvector
- TimescaleDB optional

Storage:
- Supabase Storage
- Cloudflare R2
- S3-compatible object storage

AI Providers:
- Hugging Face
- Groq
- Ollama
- OpenAI
- Transformers.js browser runtime

Blockchain:
- Solana devnet
- metadata anchors only by default

Observability:
- OpenTelemetry
- Prometheus
- Grafana
- Sentry

---

## Production readiness checklist

Required before production:
- real auth
- RBAC
- tenant isolation
- async workers
- queue retry logic
- Postgres migrations
- rate limiting
- telemetry
- provider retries
- vector indexing
- object storage
- backup strategy
- monitoring
- CI/CD
- integration tests
- legal/compliance review for tokenized metadata products

---

## Important safety notes

The repository contains:
- deployment plans
- inference plans
- metadata anchoring plans
- worker orchestration plans

The repository does NOT guarantee:
- live inference execution
- guaranteed revenue
- production tokenization legality
- automated financial outcomes
- unrestricted mainnet deployment

Human review and deployment configuration are still required.
