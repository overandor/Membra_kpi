# Backup Strategy

## SQLite

Back up the database file regularly:

```bash
cp data/membra.db backups/membra-$(date +%F-%H%M).db
```

## Uploads

Back up static/uploads to object storage.

## Recommended production approach

- Managed Postgres with automated snapshots
- S3/R2 object storage lifecycle rules
- Daily encrypted backups
- Restore verification drills

## Retention

- Hourly: 24 hours
- Daily: 14 days
- Weekly: 8 weeks
- Monthly: 12 months
