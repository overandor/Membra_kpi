-- MEMBRA KPI event outbox for production-grade cross-module delivery

CREATE TABLE IF NOT EXISTS event_outbox (
  outbox_id TEXT PRIMARY KEY,
  event_id TEXT UNIQUE NOT NULL,
  event_type TEXT NOT NULL,
  source_module TEXT NOT NULL,
  subject_type TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  owner_id TEXT,
  payload_json TEXT NOT NULL,
  proof_hash TEXT,
  signature TEXT,
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','delivered','failed','dead_letter')),
  attempt_count INTEGER NOT NULL DEFAULT 0,
  last_attempt_at TEXT,
  last_error TEXT,
  created_at TEXT NOT NULL,
  delivered_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_event_outbox_status_created ON event_outbox(status, created_at);
CREATE INDEX IF NOT EXISTS idx_event_outbox_subject ON event_outbox(subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_event_outbox_owner ON event_outbox(owner_id);
