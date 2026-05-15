# Backup Strategy

## SQLite backups

Create rolling backups of the SQLite database:

```bash
mkdir -p backups
cp data/membra.db backups/membra-$(date +%F-%H%M).db
```

## Upload backups

Synchronize uploads to object storage:

```bash
aws s3 sync static/uploads s3://your-bucket/uploads
```

## Recommended production approach

- Managed Postgres with automated snapshots
- S3 or R2 object storage
- Encrypted offsite retention
- Restore verification drills

## Suggested retention policy

- Hourly backups: 24 hours
- Daily backups: 14 days
- Weekly backups: 8 weeks
- Monthly backups: 12 months
