# MEMBRA KPI Operations Runbook

This runbook is for operating the production-hardened MEMBRA KPI starter.

## Daily checks

1. Open `/api/health`.
2. Open `/api/ready`.
3. Check container or Replit logs for errors.
4. Confirm upload directory has available storage.
5. Confirm database backup ran.
6. Review new ProofBook entries.
7. Review admin decisions and held listings.

## Backup

Run:

```bash
python scripts/backup_sqlite.py
```

Default backup location:

```text
./backups/membra-YYYYMMDDTHHMMSSZ.db
```

Recommended cadence:

- closed alpha: daily
- public beta: hourly or managed database snapshots
- production: managed database with point-in-time recovery

## Restore

Run:

```bash
python scripts/restore_sqlite.py backups/membra-YYYYMMDDTHHMMSSZ.db
```

The restore script makes a `.pre-restore` copy of the existing database before replacing it.

## Admin token rotation

Generate a new token:

```bash
python scripts/generate_admin_token.py
```

Set `ADMIN_TOKEN_SHA256` to the generated hash.

Store the plain token in a password manager. Do not commit the plain token.

## Smoke test

With the app running:

```bash
APP_BASE_URL=http://localhost:8000 python scripts/smoke_test.py
```

## Incident response

If suspicious activity occurs:

1. Set the app to maintenance at the hosting layer.
2. Rotate `ADMIN_TOKEN_SHA256`.
3. Preserve logs and database backup.
4. Export ProofBook and admin decision records.
5. Review uploaded files for policy violations.
6. Remove public visibility from risky listings.
7. Notify affected users if real personal data is involved.
8. Document root cause and mitigation.

## Listing safety review

Before approving visibility, check:

- owner claims control of the asset
- lease/building/HOA/local rules are not obviously violated
- proof photo is sufficient
- prohibited items or services are not included
- suggested price is labeled as an estimate
- risk flags are addressed
- payout eligibility is not represented as settled money

## Deployment rollback

Docker:

```bash
docker compose down
# restore previous image/tag or previous git commit
docker compose up -d --build
```

SQLite rollback:

```bash
python scripts/restore_sqlite.py backups/<known-good>.db
```

## Non-negotiable boundaries

- No automatic public listing without owner confirmation.
- No private keys or seed phrases.
- No guaranteed earnings.
- No custody of funds.
- No payout settlement claim unless a regulated external rail confirms settlement.
