"""MEMBRA deed and permission backend.

This module implements the rights layer that MEMBRA needs before physical/local
assets can be credibly monetized:
- asset owners
- physical assets
- ownership attestations
- permission grants
- listing authority
- deed/document references
- disputes
- revocations
- activation gate checks

The design is tenant-aware and ProofBook-linked. It does not provide legal
advice or certify ownership. It stores operational records, hashes, evidence
references, and enforcement decisions that a production system can review.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deep_backend import BackendContext, append_chain_event, canonical_json, new_id, sha256_text, utc_now


@dataclass(frozen=True, slots=True)
class ActivationGateResult:
    listing_id: str
    asset_id: str
    allowed: bool
    status: str
    missing: list[str]
    blockers: list[str]
    proofbook_required: bool


def apply_deed_backend_schema(conn) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS asset_owners(
          owner_id TEXT PRIMARY KEY,
          tenant_id TEXT NOT NULL,
          user_id TEXT,
          legal_name TEXT NOT NULL,
          owner_type TEXT NOT NULL,
          contact_email TEXT,
          verification_status TEXT NOT NULL DEFAULT 'unverified',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS physical_assets(
          asset_id TEXT PRIMARY KEY,
          tenant_id TEXT NOT NULL,
          owner_id TEXT NOT NULL,
          asset_name TEXT NOT NULL,
          asset_type TEXT NOT NULL,
          address_text TEXT,
          city TEXT,
          region TEXT,
          country TEXT,
          latitude REAL,
          longitude REAL,
          status TEXT NOT NULL DEFAULT 'draft',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ownership_attestations(
          attestation_id TEXT PRIMARY KEY,
          tenant_id TEXT NOT NULL,
          asset_id TEXT NOT NULL,
          owner_id TEXT NOT NULL,
          attestation_type TEXT NOT NULL,
          attestation_text TEXT NOT NULL,
          evidence_hash TEXT,
          status TEXT NOT NULL DEFAULT 'pending_review',
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS deed_documents(
          document_id TEXT PRIMARY KEY,
          tenant_id TEXT NOT NULL,
          asset_id TEXT NOT NULL,
          owner_id TEXT NOT NULL,
          document_type TEXT NOT NULL,
          object_id TEXT,
          document_hash TEXT NOT NULL,
          review_status TEXT NOT NULL DEFAULT 'pending_review',
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS permission_grants(
          grant_id TEXT PRIMARY KEY,
          tenant_id TEXT NOT NULL,
          asset_id TEXT NOT NULL,
          owner_id TEXT NOT NULL,
          grantee_user_id TEXT,
          permission_scope TEXT NOT NULL,
          allowed_use TEXT NOT NULL,
          starts_at TEXT NOT NULL,
          expires_at TEXT,
          status TEXT NOT NULL DEFAULT 'pending_review',
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          revoked_at TEXT
        );

        CREATE TABLE IF NOT EXISTS listing_authority(
          authority_id TEXT PRIMARY KEY,
          tenant_id TEXT NOT NULL,
          listing_id TEXT NOT NULL,
          asset_id TEXT NOT NULL,
          grant_id TEXT NOT NULL,
          authority_scope TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending_review',
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          approved_at TEXT,
          revoked_at TEXT
        );

        CREATE TABLE IF NOT EXISTS deed_disputes(
          dispute_id TEXT PRIMARY KEY,
          tenant_id TEXT NOT NULL,
          asset_id TEXT NOT NULL,
          listing_id TEXT,
          opened_by TEXT NOT NULL,
          dispute_type TEXT NOT NULL,
          notes TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'open',
          created_at TEXT NOT NULL,
          resolved_at TEXT
        );

        CREATE TABLE IF NOT EXISTS deed_revocations(
          revocation_id TEXT PRIMARY KEY,
          tenant_id TEXT NOT NULL,
          subject_type TEXT NOT NULL,
          subject_id TEXT NOT NULL,
          revoked_by TEXT NOT NULL,
          reason TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        """
    )


def register_asset_owner(conn, context: BackendContext, *, legal_name: str, owner_type: str = "individual", contact_email: str | None = None, user_id: str | None = None) -> dict[str, Any]:
    now = utc_now()
    record = {
        "owner_id": new_id("own"),
        "tenant_id": context.tenant_id,
        "user_id": user_id or context.actor_id,
        "legal_name": legal_name,
        "owner_type": owner_type,
        "contact_email": contact_email,
        "verification_status": "unverified",
        "created_at": now,
        "updated_at": now,
    }
    conn.execute(
        """
        INSERT INTO asset_owners(owner_id, tenant_id, user_id, legal_name, owner_type, contact_email, verification_status, created_at, updated_at)
        VALUES(:owner_id,:tenant_id,:user_id,:legal_name,:owner_type,:contact_email,:verification_status,:created_at,:updated_at)
        """,
        record,
    )
    append_chain_event(conn, context, "asset_owner", record["owner_id"], "deed.owner_registered", record)
    return record


def register_physical_asset(conn, context: BackendContext, *, owner_id: str, asset_name: str, asset_type: str, address_text: str | None = None, city: str | None = None, region: str | None = None, country: str | None = None, latitude: float | None = None, longitude: float | None = None) -> dict[str, Any]:
    now = utc_now()
    record = {
        "asset_id": new_id("asset"),
        "tenant_id": context.tenant_id,
        "owner_id": owner_id,
        "asset_name": asset_name,
        "asset_type": asset_type,
        "address_text": address_text,
        "city": city,
        "region": region,
        "country": country,
        "latitude": latitude,
        "longitude": longitude,
        "status": "draft",
        "created_at": now,
        "updated_at": now,
    }
    conn.execute(
        """
        INSERT INTO physical_assets(asset_id, tenant_id, owner_id, asset_name, asset_type, address_text, city, region, country, latitude, longitude, status, created_at, updated_at)
        VALUES(:asset_id,:tenant_id,:owner_id,:asset_name,:asset_type,:address_text,:city,:region,:country,:latitude,:longitude,:status,:created_at,:updated_at)
        """,
        record,
    )
    append_chain_event(conn, context, "physical_asset", record["asset_id"], "deed.asset_registered", record)
    return record


def create_ownership_attestation(conn, context: BackendContext, *, asset_id: str, owner_id: str, attestation_text: str, attestation_type: str = "owner_statement", evidence_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    evidence_hash = sha256_text(canonical_json(evidence_payload or {"attestation_text": attestation_text}))
    record = {
        "attestation_id": new_id("att"),
        "tenant_id": context.tenant_id,
        "asset_id": asset_id,
        "owner_id": owner_id,
        "attestation_type": attestation_type,
        "attestation_text": attestation_text,
        "evidence_hash": evidence_hash,
        "status": "pending_review",
        "created_by": context.actor_id,
        "created_at": utc_now(),
    }
    conn.execute(
        """
        INSERT INTO ownership_attestations(attestation_id, tenant_id, asset_id, owner_id, attestation_type, attestation_text, evidence_hash, status, created_by, created_at)
        VALUES(:attestation_id,:tenant_id,:asset_id,:owner_id,:attestation_type,:attestation_text,:evidence_hash,:status,:created_by,:created_at)
        """,
        record,
    )
    append_chain_event(conn, context, "ownership_attestation", record["attestation_id"], "deed.ownership_attested", record)
    return record


def create_permission_grant(conn, context: BackendContext, *, asset_id: str, owner_id: str, permission_scope: str, allowed_use: str, starts_at: str | None = None, expires_at: str | None = None, grantee_user_id: str | None = None) -> dict[str, Any]:
    record = {
        "grant_id": new_id("grant"),
        "tenant_id": context.tenant_id,
        "asset_id": asset_id,
        "owner_id": owner_id,
        "grantee_user_id": grantee_user_id,
        "permission_scope": permission_scope,
        "allowed_use": allowed_use,
        "starts_at": starts_at or utc_now(),
        "expires_at": expires_at,
        "status": "pending_review",
        "created_by": context.actor_id,
        "created_at": utc_now(),
        "revoked_at": None,
    }
    conn.execute(
        """
        INSERT INTO permission_grants(grant_id, tenant_id, asset_id, owner_id, grantee_user_id, permission_scope, allowed_use, starts_at, expires_at, status, created_by, created_at, revoked_at)
        VALUES(:grant_id,:tenant_id,:asset_id,:owner_id,:grantee_user_id,:permission_scope,:allowed_use,:starts_at,:expires_at,:status,:created_by,:created_at,:revoked_at)
        """,
        record,
    )
    append_chain_event(conn, context, "permission_grant", record["grant_id"], "deed.permission_granted", record)
    return record


def create_listing_authority(conn, context: BackendContext, *, listing_id: str, asset_id: str, grant_id: str, authority_scope: str = "monetize_listing") -> dict[str, Any]:
    record = {
        "authority_id": new_id("authz"),
        "tenant_id": context.tenant_id,
        "listing_id": listing_id,
        "asset_id": asset_id,
        "grant_id": grant_id,
        "authority_scope": authority_scope,
        "status": "pending_review",
        "created_by": context.actor_id,
        "created_at": utc_now(),
        "approved_at": None,
        "revoked_at": None,
    }
    conn.execute(
        """
        INSERT INTO listing_authority(authority_id, tenant_id, listing_id, asset_id, grant_id, authority_scope, status, created_by, created_at, approved_at, revoked_at)
        VALUES(:authority_id,:tenant_id,:listing_id,:asset_id,:grant_id,:authority_scope,:status,:created_by,:created_at,:approved_at,:revoked_at)
        """,
        record,
    )
    append_chain_event(conn, context, "listing_authority", record["authority_id"], "deed.listing_authority_created", record)
    return record


def approve_permission_grant(conn, context: BackendContext, grant_id: str) -> dict[str, Any]:
    conn.execute("UPDATE permission_grants SET status='approved' WHERE tenant_id=? AND grant_id=?", (context.tenant_id, grant_id))
    event = {"grant_id": grant_id, "status": "approved", "approved_by": context.actor_id, "approved_at": utc_now()}
    append_chain_event(conn, context, "permission_grant", grant_id, "deed.permission_grant_approved", event)
    return event


def approve_listing_authority(conn, context: BackendContext, authority_id: str) -> dict[str, Any]:
    now = utc_now()
    conn.execute("UPDATE listing_authority SET status='approved', approved_at=? WHERE tenant_id=? AND authority_id=?", (now, context.tenant_id, authority_id))
    event = {"authority_id": authority_id, "status": "approved", "approved_by": context.actor_id, "approved_at": now}
    append_chain_event(conn, context, "listing_authority", authority_id, "deed.listing_authority_approved", event)
    return event


def open_dispute(conn, context: BackendContext, *, asset_id: str, dispute_type: str, notes: str, listing_id: str | None = None) -> dict[str, Any]:
    record = {
        "dispute_id": new_id("disp"),
        "tenant_id": context.tenant_id,
        "asset_id": asset_id,
        "listing_id": listing_id,
        "opened_by": context.actor_id,
        "dispute_type": dispute_type,
        "notes": notes,
        "status": "open",
        "created_at": utc_now(),
        "resolved_at": None,
    }
    conn.execute(
        """
        INSERT INTO deed_disputes(dispute_id, tenant_id, asset_id, listing_id, opened_by, dispute_type, notes, status, created_at, resolved_at)
        VALUES(:dispute_id,:tenant_id,:asset_id,:listing_id,:opened_by,:dispute_type,:notes,:status,:created_at,:resolved_at)
        """,
        record,
    )
    append_chain_event(conn, context, "deed_dispute", record["dispute_id"], "deed.dispute_opened", record)
    return record


def revoke_subject(conn, context: BackendContext, *, subject_type: str, subject_id: str, reason: str) -> dict[str, Any]:
    record = {
        "revocation_id": new_id("revoke"),
        "tenant_id": context.tenant_id,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "revoked_by": context.actor_id,
        "reason": reason,
        "created_at": utc_now(),
    }
    conn.execute(
        """
        INSERT INTO deed_revocations(revocation_id, tenant_id, subject_type, subject_id, revoked_by, reason, created_at)
        VALUES(:revocation_id,:tenant_id,:subject_type,:subject_id,:revoked_by,:reason,:created_at)
        """,
        record,
    )
    if subject_type == "permission_grant":
        conn.execute("UPDATE permission_grants SET status='revoked', revoked_at=? WHERE tenant_id=? AND grant_id=?", (record["created_at"], context.tenant_id, subject_id))
    if subject_type == "listing_authority":
        conn.execute("UPDATE listing_authority SET status='revoked', revoked_at=? WHERE tenant_id=? AND authority_id=?", (record["created_at"], context.tenant_id, subject_id))
    append_chain_event(conn, context, subject_type, subject_id, "deed.subject_revoked", record)
    return record


def check_listing_activation_gate(conn, context: BackendContext, *, listing_id: str, asset_id: str) -> dict[str, Any]:
    missing: list[str] = []
    blockers: list[str] = []
    asset = conn.execute("SELECT * FROM physical_assets WHERE tenant_id=? AND asset_id=?", (context.tenant_id, asset_id)).fetchone()
    if not asset:
        missing.append("physical_asset")
    owner_id = asset["owner_id"] if asset else None
    owner = conn.execute("SELECT * FROM asset_owners WHERE tenant_id=? AND owner_id=?", (context.tenant_id, owner_id)).fetchone() if owner_id else None
    if not owner:
        missing.append("asset_owner")
    attestation = conn.execute("SELECT * FROM ownership_attestations WHERE tenant_id=? AND asset_id=? AND owner_id=? ORDER BY created_at DESC LIMIT 1", (context.tenant_id, asset_id, owner_id)).fetchone() if owner_id else None
    if not attestation:
        missing.append("ownership_attestation")
    grant = conn.execute("SELECT * FROM permission_grants WHERE tenant_id=? AND asset_id=? AND owner_id=? AND status='approved' ORDER BY created_at DESC LIMIT 1", (context.tenant_id, asset_id, owner_id)).fetchone() if owner_id else None
    if not grant:
        missing.append("approved_permission_grant")
    authority = conn.execute("SELECT * FROM listing_authority WHERE tenant_id=? AND listing_id=? AND asset_id=? AND status='approved' ORDER BY created_at DESC LIMIT 1", (context.tenant_id, listing_id, asset_id)).fetchone()
    if not authority:
        missing.append("approved_listing_authority")
    dispute = conn.execute("SELECT * FROM deed_disputes WHERE tenant_id=? AND asset_id=? AND status='open' LIMIT 1", (context.tenant_id, asset_id)).fetchone()
    if dispute:
        blockers.append("open_dispute")
    revoked_grant = conn.execute("SELECT * FROM permission_grants WHERE tenant_id=? AND asset_id=? AND status='revoked' LIMIT 1", (context.tenant_id, asset_id)).fetchone()
    if revoked_grant and not grant:
        blockers.append("permission_revoked")
    allowed = not missing and not blockers
    result = ActivationGateResult(
        listing_id=listing_id,
        asset_id=asset_id,
        allowed=allowed,
        status="allowed" if allowed else "blocked",
        missing=missing,
        blockers=blockers,
        proofbook_required=True,
    )
    payload = result.__dict__
    append_chain_event(conn, context, "listing", listing_id, "deed.activation_gate_checked", payload)
    return payload
