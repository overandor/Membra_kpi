# Security Policy

MEMBRA KPI is a proof and eligibility system. It must not be used to collect private keys, seed phrases, raw financial credentials, or unconsented sensitive personal material.

## Production security controls currently implemented

- Security response headers: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, and a conservative Content Security Policy.
- Request rate limiting with `RATE_LIMIT_REQUESTS` and `RATE_LIMIT_WINDOW_SECONDS`.
- Trusted host support with `ALLOWED_HOSTS`.
- Image upload validation by extension, content type, size, and Pillow verification.
- CSV/XLSX upload validation by extension and size.
- Upload size limit through `MAX_UPLOAD_MB`.
- Admin mutation protection using either `ADMIN_TOKEN` or preferred `ADMIN_TOKEN_SHA256`.
- Stripe webhook signature verification when `STRIPE_WEBHOOK_SECRET` is configured.
- QR scan IPs are stored as hashes rather than raw IPs.
- Wallet records payout eligibility only; the app does not custody funds.

## Required production secrets

Set these before public deployment:

```text
APP_ENV=production
APP_BASE_URL=https://your-domain.example
ALLOWED_HOSTS=your-domain.example,.replit.app
ADMIN_TOKEN_SHA256=<sha256-of-strong-admin-token>
GROQ_API_KEY=<optional>
OPENAI_API_KEY=<optional>
STRIPE_SECRET_KEY=<optional>
STRIPE_WEBHOOK_SECRET=<optional>
STRIPE_PRICE_ID=<optional>
```

Generate an admin-token hash:

```bash
python -c "import hashlib; print(hashlib.sha256(b'your-strong-admin-token').hexdigest())"
```

## Production boundaries

- AI drafts are not listings.
- Drafts remain private until owner confirmation.
- Estimates are not guaranteed.
- ProofBook records are audit records, not payment authorization.
- Payout eligibility is not settlement.
- External regulated rails settle money.

## Before using real user data

Complete these items first:

- Add real authentication and user sessions.
- Add durable object storage for uploads.
- Add backup/restore for the database.
- Add data deletion and consent revocation workflows.
- Add content moderation for uploaded images and listing text.
- Add abuse monitoring and admin audit exports.
- Have Terms, Privacy Policy, and local compliance reviewed.

## Reporting vulnerabilities

Do not publish exploitable details publicly. Open a private security advisory or contact the repository owner directly.
