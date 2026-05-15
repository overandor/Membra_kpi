-- MEMBRA KPI production auth/privacy schema extension

CREATE TABLE IF NOT EXISTS users (
  user_id TEXT PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  display_name TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('owner','operator','admin')),
  password_hash TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  session_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  token_hash TEXT UNIQUE NOT NULL,
  user_agent TEXT,
  ip_hash TEXT,
  expires_at TEXT NOT NULL,
  revoked_at TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON sessions(token_hash);

CREATE TABLE IF NOT EXISTS consent_records (
  consent_id TEXT PRIMARY KEY,
  owner_id TEXT NOT NULL,
  subject_type TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  consent_type TEXT NOT NULL,
  visibility_scope TEXT NOT NULL,
  location_scope TEXT NOT NULL,
  proof_retention_scope TEXT NOT NULL,
  permitted_use TEXT NOT NULL,
  revoked_at TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_consent_owner_subject ON consent_records(owner_id, subject_type, subject_id);

CREATE TABLE IF NOT EXISTS privacy_requests (
  request_id TEXT PRIMARY KEY,
  owner_id TEXT NOT NULL,
  request_type TEXT NOT NULL CHECK(request_type IN ('export','delete','anonymize','consent_revocation')),
  status TEXT NOT NULL DEFAULT 'submitted',
  reason TEXT,
  export_json TEXT,
  operator_notes TEXT,
  created_at TEXT NOT NULL,
  completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_privacy_owner_status ON privacy_requests(owner_id, status);

CREATE TABLE IF NOT EXISTS ownership_audit_events (
  event_id TEXT PRIMARY KEY,
  actor_user_id TEXT,
  owner_id TEXT NOT NULL,
  subject_type TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  action TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ownership_audit_owner ON ownership_audit_events(owner_id);
