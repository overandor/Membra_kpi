"""Deep backend primitives for MEMBRA KPI.

This module adds production-oriented backend foundations without breaking the
existing Replit/FastAPI runtime:

- tenant-aware identity tables
- append-only hash-chained ProofBook events
- object storage registry for uploaded files
- backend migrations table
- KPI observation/event records
- RBAC role and permission tables

It intentionally does not execute payouts or custody funds. Wallet and payout
records remain eligibility/accounting records unless an external provider is
explicitly integrated by the host application.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_TENANT_ID = "tenant_default"
GENESIS_HASH = "GENESIS"


@dataclass(slots=True)
class BackendContext:
    tenant_id: str = DEFAULT_TENANT_ID
    actor_id: str = "system"
    role: str = "system"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def apply_deep_backend_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS backend_migrations(
          migration_id TEXT PRIMARY KEY,
          applied_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tenants(
          tenant_id TEXT PRIMARY KEY,
          tenant_name TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'active',
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS users(
          user_id TEXT PRIMARY KEY,
          tenant_id TEXT NOT NULL,
          email TEXT,
          display_name TEXT,
          role TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'active',
          created_at TEXT NOT NULL,
          last_login_at TEXT
        );

        CREATE TABLE IF NOT EXISTS rbac_roles(
          role TEXT PRIMARY KEY,
          description TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS rbac_permissions(
          permission TEXT PRIMARY KEY,
          description TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS rbac_role_permissions(
          role TEXT NOT NULL,
          permission TEXT NOT NULL,
          PRIMARY KEY(role, permission)
        );

        CREATE TABLE IF NOT EXISTS object_registry(
          object_id TEXT PRIMARY KEY,
          tenant_id TEXT NOT NULL,
          owner_id TEXT,
          source_table TEXT,
          source_id TEXT,
          storage_provider TEXT NOT NULL,
          object_key TEXT NOT NULL,
          filename TEXT,
          content_type TEXT,
          byte_size INTEGER NOT NULL DEFAULT 0,
          sha256 TEXT NOT NULL,
          purpose TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS proofbook_chain_events(
          event_id TEXT PRIMARY KEY,
          tenant_id TEXT NOT NULL,
          actor_id TEXT NOT NULL,
          subject_type TEXT NOT NULL,
          subject_id TEXT NOT NULL,
          event_type TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          previous_hash TEXT NOT NULL,
          event_hash TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS kpi_observations(
          observation_id TEXT PRIMARY KEY,
          tenant_id TEXT NOT NULL,
          subject_type TEXT NOT NULL,
          subject_id TEXT NOT NULL,
          metric_name TEXT NOT NULL,
          metric_value REAL NOT NULL,
          metric_unit TEXT,
          confidence REAL,
          source TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS audit_events(
          audit_id TEXT PRIMARY KEY,
          tenant_id TEXT NOT NULL,
          actor_id TEXT NOT NULL,
          action TEXT NOT NULL,
          subject_type TEXT NOT NULL,
          subject_id TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        """
    )
    seed_deep_backend_defaults(conn)


def seed_deep_backend_defaults(conn: sqlite3.Connection) -> None:
    now = utc_now()
    conn.execute(
        "INSERT OR IGNORE INTO tenants(tenant_id, tenant_name, status, created_at) VALUES(?,?,?,?)",
        (DEFAULT_TENANT_ID, "Default Local Tenant", "active", now),
    )
    roles = {
        "platform_admin": "Full platform operator",
        "tenant_admin": "Tenant administrator",
        "reviewer": "Proof and listing reviewer",
        "asset_owner": "Owner of physical inventory",
        "advertiser": "Campaign buyer",
        "investor_viewer": "Read-only investor/data room viewer",
        "system": "Internal system actor",
    }
    for role, description in roles.items():
        conn.execute(
            "INSERT OR IGNORE INTO rbac_roles(role, description) VALUES(?,?)",
            (role, description),
        )
    permissions = {
        "assets.read": "Read inventory and listing assets",
        "assets.write": "Create or update asset records",
        "kpis.read": "Read KPI observations",
        "kpis.write": "Create KPI observations",
        "proofbook.read": "Read ProofBook events",
        "proofbook.append": "Append ProofBook events",
        "wallet.read": "Read wallet eligibility records",
        "admin.review": "Create admin decisions",
        "tenant.manage": "Manage tenant settings",
    }
    for permission, description in permissions.items():
        conn.execute(
            "INSERT OR IGNORE INTO rbac_permissions(permission, description) VALUES(?,?)",
            (permission, description),
        )
    admin_perms = list(permissions)
    reviewer_perms = ["assets.read", "kpis.read", "proofbook.read", "proofbook.append", "admin.review"]
    owner_perms = ["assets.read", "assets.write", "kpis.read", "proofbook.read", "wallet.read"]
    system_perms = admin_perms
    assignments = {
        "platform_admin": admin_perms,
        "tenant_admin": admin_perms,
        "reviewer": reviewer_perms,
        "asset_owner": owner_perms,
        "system": system_perms,
    }
    for role, perms in assignments.items():
        for permission in perms:
            conn.execute(
                "INSERT OR IGNORE INTO rbac_role_permissions(role, permission) VALUES(?,?)",
                (role, permission),
            )


def get_role_permissions(conn: sqlite3.Connection, role: str) -> set[str]:
    rows = conn.execute("SELECT permission FROM rbac_role_permissions WHERE role=?", (role,)).fetchall()
    return {row[0] for row in rows}


def require_permission(conn: sqlite3.Connection, context: BackendContext, permission: str) -> None:
    if permission not in get_role_permissions(conn, context.role):
        raise PermissionError(f"role {context.role!r} lacks permission {permission!r}")


def last_chain_hash(conn: sqlite3.Connection, tenant_id: str) -> str:
    row = conn.execute(
        "SELECT event_hash FROM proofbook_chain_events WHERE tenant_id=? ORDER BY created_at DESC, event_id DESC LIMIT 1",
        (tenant_id,),
    ).fetchone()
    return row[0] if row else GENESIS_HASH


def calculate_chain_hash(previous_hash: str, tenant_id: str, actor_id: str, subject_type: str, subject_id: str, event_type: str, payload: dict[str, Any], created_at: str) -> str:
    raw = "|".join([
        previous_hash,
        tenant_id,
        actor_id,
        subject_type,
        subject_id,
        event_type,
        canonical_json(payload),
        created_at,
    ])
    return sha256_text(raw)


def append_chain_event(conn: sqlite3.Connection, context: BackendContext, subject_type: str, subject_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    require_permission(conn, context, "proofbook.append")
    created_at = utc_now()
    previous_hash = last_chain_hash(conn, context.tenant_id)
    event_hash = calculate_chain_hash(previous_hash, context.tenant_id, context.actor_id, subject_type, subject_id, event_type, payload, created_at)
    event = {
        "event_id": new_id("pbc"),
        "tenant_id": context.tenant_id,
        "actor_id": context.actor_id,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "event_type": event_type,
        "payload_json": canonical_json(payload),
        "previous_hash": previous_hash,
        "event_hash": event_hash,
        "created_at": created_at,
    }
    conn.execute(
        """
        INSERT INTO proofbook_chain_events(event_id, tenant_id, actor_id, subject_type, subject_id, event_type, payload_json, previous_hash, event_hash, created_at)
        VALUES(:event_id,:tenant_id,:actor_id,:subject_type,:subject_id,:event_type,:payload_json,:previous_hash,:event_hash,:created_at)
        """,
        event,
    )
    return event


def verify_chain(conn: sqlite3.Connection, tenant_id: str = DEFAULT_TENANT_ID) -> dict[str, Any]:
    events = conn.execute(
        "SELECT * FROM proofbook_chain_events WHERE tenant_id=? ORDER BY created_at ASC, event_id ASC",
        (tenant_id,),
    ).fetchall()
    previous = GENESIS_HASH
    for index, row in enumerate(events):
        payload = json.loads(row["payload_json"])
        expected = calculate_chain_hash(previous, row["tenant_id"], row["actor_id"], row["subject_type"], row["subject_id"], row["event_type"], payload, row["created_at"])
        if expected != row["event_hash"] or row["previous_hash"] != previous:
            return {"valid": False, "broken_index": index, "event_id": row["event_id"], "expected_hash": expected, "actual_hash": row["event_hash"]}
        previous = row["event_hash"]
    return {"valid": True, "event_count": len(events), "latest_hash": previous}


def register_object(conn: sqlite3.Connection, context: BackendContext, file_path: str | Path, *, source_table: str, source_id: str, filename: str, content_type: str, purpose: str, storage_provider: str = "local") -> dict[str, Any]:
    path = Path(file_path)
    digest = sha256_file(path)
    record = {
        "object_id": new_id("obj"),
        "tenant_id": context.tenant_id,
        "owner_id": context.actor_id,
        "source_table": source_table,
        "source_id": source_id,
        "storage_provider": storage_provider,
        "object_key": str(path),
        "filename": filename,
        "content_type": content_type,
        "byte_size": path.stat().st_size,
        "sha256": digest,
        "purpose": purpose,
        "created_at": utc_now(),
    }
    conn.execute(
        """
        INSERT INTO object_registry(object_id, tenant_id, owner_id, source_table, source_id, storage_provider, object_key, filename, content_type, byte_size, sha256, purpose, created_at)
        VALUES(:object_id,:tenant_id,:owner_id,:source_table,:source_id,:storage_provider,:object_key,:filename,:content_type,:byte_size,:sha256,:purpose,:created_at)
        """,
        record,
    )
    append_chain_event(conn, context, "object", record["object_id"], "object.registered", {"source_table": source_table, "source_id": source_id, "sha256": digest, "purpose": purpose})
    return record


def record_kpi_observation(conn: sqlite3.Connection, context: BackendContext, *, subject_type: str, subject_id: str, metric_name: str, metric_value: float, metric_unit: str = "score", confidence: float | None = None, source: str = "system", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    require_permission(conn, context, "kpis.write")
    record = {
        "observation_id": new_id("kpio"),
        "tenant_id": context.tenant_id,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "metric_name": metric_name,
        "metric_value": float(metric_value),
        "metric_unit": metric_unit,
        "confidence": confidence,
        "source": source,
        "payload_json": canonical_json(payload or {}),
        "created_at": utc_now(),
    }
    conn.execute(
        """
        INSERT INTO kpi_observations(observation_id, tenant_id, subject_type, subject_id, metric_name, metric_value, metric_unit, confidence, source, payload_json, created_at)
        VALUES(:observation_id,:tenant_id,:subject_type,:subject_id,:metric_name,:metric_value,:metric_unit,:confidence,:source,:payload_json,:created_at)
        """,
        record,
    )
    append_chain_event(conn, context, subject_type, subject_id, "kpi.observed", {"metric_name": metric_name, "metric_value": metric_value, "metric_unit": metric_unit})
    return record


def backend_status(conn: sqlite3.Connection, tenant_id: str = DEFAULT_TENANT_ID) -> dict[str, Any]:
    def count(table: str) -> int:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    return {
        "tenant_id": tenant_id,
        "tenants": count("tenants"),
        "users": count("users"),
        "objects": count("object_registry"),
        "proofbook_chain_events": count("proofbook_chain_events"),
        "kpi_observations": count("kpi_observations"),
        "audit_events": count("audit_events"),
        "proofbook_chain": verify_chain(conn, tenant_id),
    }
