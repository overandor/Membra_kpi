"""Provider API helpers for MEMBRA KPI.

This module is framework-light: app.py or a future router can call these helpers
without duplicating provider safety logic.
"""
from __future__ import annotations

import json
from typing import Any

from .deep_backend import BackendContext, append_chain_event
from .external_providers import (
    google_config_requirements,
    iot_config_requirements,
    provider_registry,
    web3_config_requirements,
)
from .iot_ingest import ingest_iot_event, token_configured, verify_ingest_token
from .solana_devnet import solana_devnet_status


class ProviderApiError(ValueError):
    pass


def get_all_provider_status() -> dict[str, Any]:
    return provider_registry()


def get_provider_requirements() -> dict[str, Any]:
    return {
        "web3": web3_config_requirements(),
        "iot": iot_config_requirements(),
        "google_official_public": google_config_requirements(),
    }


def get_web3_status() -> dict[str, Any]:
    registry = provider_registry()
    return {
        "providers": [p for p in registry["providers"] if p["category"] == "web3_rpc"],
        "solana_devnet": solana_devnet_status(),
        "safety": registry["safety"],
    }


def get_iot_status() -> dict[str, Any]:
    registry = provider_registry()
    return {
        "providers": [p for p in registry["providers"] if p["category"].startswith("iot")],
        "http_ingest_token_configured": token_configured(),
    }


def get_google_status() -> dict[str, Any]:
    registry = provider_registry()
    return {
        "providers": [p for p in registry["providers"] if p["category"] == "google_official_public_api"],
        "requirements": google_config_requirements(),
    }


def handle_iot_ingest(conn, payload: dict[str, Any], token: str | None) -> dict[str, Any]:
    if token_configured() and not verify_ingest_token(token):
        raise ProviderApiError("Invalid IoT ingest token")
    if not token_configured():
        raise ProviderApiError("MEMBRA_IOT_INGEST_TOKEN is not configured; refusing public IoT ingest")

    context = BackendContext(
        tenant_id=str(payload.get("tenant_id", "tenant_default")),
        actor_id=str(payload.get("device_id", "iot-device")),
        role="system",
    )
    return ingest_iot_event(conn, context, payload)


def record_provider_observation(conn, *, tenant_id: str, provider_name: str, observation_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    context = BackendContext(tenant_id=tenant_id, actor_id="provider-registry", role="system")
    return append_chain_event(
        conn,
        context,
        "provider",
        provider_name,
        f"provider.{observation_type}",
        payload,
    )


def safe_google_request_blueprint(provider_name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Return a safe request blueprint without executing Google API calls.

    The production adapter should use this blueprint to build signed requests
    server-side after credentials are configured.
    """
    allowed = {"google-maps-platform", "google-places", "google-civic-information", "google-cloud-vision"}
    if provider_name not in allowed:
        raise ProviderApiError(f"Unsupported Google provider: {provider_name}")
    sanitized = {str(k): str(v)[:500] for k, v in params.items() if v is not None}
    return {
        "provider": provider_name,
        "mode": "blueprint_only",
        "params": sanitized,
        "note": "No external request executed by blueprint helper. Configure official adapter credentials before live calls.",
    }
