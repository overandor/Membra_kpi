# MEMBRA KPI Event Outbox

The event outbox is the production pattern for cross-module integration.

## Why it exists

Direct synchronous calls between modules are fragile. If KPI creates a listing and then the Wallet or ProofBook service is offline, MEMBRA still needs to preserve the fact that the event happened.

The outbox pattern does this:

```text
domain write
→ local event_outbox write
→ async/best-effort delivery
→ delivered / failed / dead_letter status
→ replay support
```

## Files

```text
membra_kpi/events.py
membra_kpi/event_outbox.py
migrations/002_event_outbox.sql
scripts/replay_outbox.py
```

## Environment

```text
MEMBRA_EVENT_SECRET=strong-shared-hmac-secret
MEMBRA_EVENT_SINKS=http://localhost:8002/api/events/ingest,http://localhost:8003/api/events/ingest
MEMBRA_SOURCE_MODULE=membra-kpi
```

## Replay

```bash
MEMBRA_EVENT_SINKS=http://localhost:8002/api/events/ingest python scripts/replay_outbox.py
```

## Event envelope

Root schema:

```text
https://github.com/overandor/membra/blob/main/contracts/membra_event_envelope.schema.json
```

## Production rule

A cross-module event should be considered durable only after it is recorded locally in `event_outbox`. Downstream delivery can fail and be retried without losing the domain event.
