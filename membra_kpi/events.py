"""MEMBRA cross-module event helpers.

Provides a canonical event envelope, HMAC signing, local outbox persistence
payloads, and best-effort HTTP delivery helpers.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import os
import uuid
from dataclasses import asdict, dataclass
from typing import Any

import httpx

EVENT_SECRET = os.getenv("MEMBRA_EVENT_SECRET", "")
EVENT_SINKS = [sink.strip() for sink in os.getenv("MEMBRA_EVENT_SINKS", "").split(",") if sink.strip()]
SOURCE_MODULE = os.getenv("MEMBRA_SOURCE_MODULE", "membra-kpi")


@dataclass(frozen=True)
class MembraEvent:
    event_id: str
    event_type: str
    source_module: str
    subject_type: str
    subject_id: str
    owner_id: str | None
    correlation_id: str | None
    causation_id: str | None
    created_at: str
    consent_scope: str | None
    risk_level: str
    payload: dict[str, Any]
    proof_hash: str | None = None
    signature: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def event_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def sign_event(event: dict[str, Any], secret: str | None = None) -> str | None:
    secret = secret if secret is not None else EVENT_SECRET
    if not secret:
        return None
    unsigned = dict(event)
    unsigned["signature"] = None
    digest = hmac.new(secret.encode("utf-8"), canonical_json(unsigned).encode("utf-8"), hashlib.sha256).hexdigest()
    return f"hmac_sha256:{digest}"


def verify_event_signature(event: dict[str, Any], secret: str | None = None) -> bool:
    expected = sign_event(event, secret)
    supplied = event.get("signature")
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))


def make_event(
    event_type: str,
    *,
    subject_type: str,
    subject_id: str,
    owner_id: str | None = None,
    payload: dict[str, Any] | None = None,
    consent_scope: str | None = None,
    risk_level: str = "normal",
    correlation_id: str | None = None,
    causation_id: str | None = None,
) -> dict[str, Any]:
    base = MembraEvent(
        event_id=f"evt_{uuid.uuid4().hex[:16]}",
        event_type=event_type,
        source_module=SOURCE_MODULE,
        subject_type=subject_type,
        subject_id=subject_id,
        owner_id=owner_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        created_at=utc_now(),
        consent_scope=consent_scope,
        risk_level=risk_level,
        payload=payload or {},
    ).to_dict()
    base["proof_hash"] = event_hash(base)
    base["signature"] = sign_event(base)
    return base


async def deliver_event(event: dict[str, Any], sinks: list[str] | None = None) -> list[dict[str, Any]]:
    sinks = sinks if sinks is not None else EVENT_SINKS
    if not sinks:
        return []
    results: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=5.0) as client:
        for sink in sinks:
            try:
                response = await client.post(sink, json=event)
                results.append({"sink": sink, "status_code": response.status_code, "ok": response.status_code < 300})
            except Exception as exc:
                results.append({"sink": sink, "ok": False, "error": str(exc)})
    return results
