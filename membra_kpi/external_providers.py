"""External provider registry for MEMBRA KPI.

Provides safe backend adapter metadata and request builders for:
- Web3 public RPC providers
- IoT telemetry ingestion
- Google official public APIs

This module does not store secrets, custody funds, sign transactions, or execute
mainnet value movement. It centralizes provider configuration, health metadata,
and safe request construction for app endpoints.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, asdict
from typing import Any


@dataclass(slots=True)
class ProviderStatus:
    name: str
    category: str
    configured: bool
    mode: str
    endpoint: str | None
    requires_secret: bool
    safe_default: str
    notes: str


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def web3_providers() -> list[ProviderStatus]:
    return [
        ProviderStatus(
            name="solana-devnet",
            category="web3_rpc",
            configured=True,
            mode="devnet_only",
            endpoint=os.getenv("MEMBRA_SOLANA_DEVNET_RPC_URL", "https://api.devnet.solana.com"),
            requires_secret=False,
            safe_default="dry_run_anchor_intent",
            notes="Devnet listing-anchor adapter. Refuses non-devnet RPC URLs.",
        ),
        ProviderStatus(
            name="ethereum-sepolia",
            category="web3_rpc",
            configured=bool(os.getenv("ETHEREUM_SEPOLIA_RPC_URL")),
            mode="testnet_read_only",
            endpoint=os.getenv("ETHEREUM_SEPOLIA_RPC_URL"),
            requires_secret=False,
            safe_default="read_only_status",
            notes="Sepolia read-only adapter placeholder for listing proof lookups. No signing.",
        ),
        ProviderStatus(
            name="polygon-amoy",
            category="web3_rpc",
            configured=bool(os.getenv("POLYGON_AMOY_RPC_URL")),
            mode="testnet_read_only",
            endpoint=os.getenv("POLYGON_AMOY_RPC_URL"),
            requires_secret=False,
            safe_default="read_only_status",
            notes="Polygon Amoy read-only adapter placeholder for listing proof lookups. No signing.",
        ),
        ProviderStatus(
            name="base-sepolia",
            category="web3_rpc",
            configured=bool(os.getenv("BASE_SEPOLIA_RPC_URL")),
            mode="testnet_read_only",
            endpoint=os.getenv("BASE_SEPOLIA_RPC_URL"),
            requires_secret=False,
            safe_default="read_only_status",
            notes="Base Sepolia read-only adapter placeholder for listing proof lookups. No signing.",
        ),
    ]


def iot_providers() -> list[ProviderStatus]:
    return [
        ProviderStatus(
            name="membra-iot-http-ingest",
            category="iot_ingest",
            configured=True,
            mode="signed_or_token_ingest",
            endpoint="/api/iot/events",
            requires_secret=True,
            safe_default="reject_without_token",
            notes="HTTP endpoint for QR/NFC/beacon/device telemetry. Token required when configured.",
        ),
        ProviderStatus(
            name="mqtt-bridge",
            category="iot_bridge",
            configured=bool(os.getenv("MQTT_BROKER_URL")),
            mode="bridge_status_only",
            endpoint=os.getenv("MQTT_BROKER_URL"),
            requires_secret=True,
            safe_default="disabled_until_configured",
            notes="MQTT bridge configuration surface. Runtime consumer is not auto-started by the web app.",
        ),
    ]


def google_public_providers() -> list[ProviderStatus]:
    return [
        ProviderStatus(
            name="google-maps-platform",
            category="google_official_public_api",
            configured=bool(os.getenv("GOOGLE_MAPS_API_KEY")),
            mode="optional_frontend_or_server_geocoding",
            endpoint="https://maps.googleapis.com/maps/api",
            requires_secret=True,
            safe_default="not_configured_use_manual_location",
            notes="Official Google Maps Platform API. Requires GOOGLE_MAPS_API_KEY.",
        ),
        ProviderStatus(
            name="google-civic-information",
            category="google_official_public_api",
            configured=bool(os.getenv("GOOGLE_CIVIC_API_KEY")),
            mode="public_context_lookup",
            endpoint="https://www.googleapis.com/civicinfo/v2",
            requires_secret=True,
            safe_default="not_configured_skip_civic_context",
            notes="Official Google Civic Information API for public geography context where relevant.",
        ),
        ProviderStatus(
            name="google-places",
            category="google_official_public_api",
            configured=bool(os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")),
            mode="nearby_business_context",
            endpoint="https://places.googleapis.com/v1",
            requires_secret=True,
            safe_default="not_configured_use_manual_business_types",
            notes="Official Google Places API for nearby business context. Requires configured API key.",
        ),
        ProviderStatus(
            name="google-cloud-vision",
            category="google_official_public_api",
            configured=bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("GOOGLE_CLOUD_VISION_API_KEY")),
            mode="vision_ocr_adapter",
            endpoint="https://vision.googleapis.com/v1/images:annotate",
            requires_secret=True,
            safe_default="not_configured_use_local_image_heuristics",
            notes="Official Google Cloud Vision API for OCR/labels if configured.",
        ),
    ]


def provider_registry() -> dict[str, Any]:
    web3 = web3_providers()
    iot = iot_providers()
    google = google_public_providers()
    all_providers = web3 + iot + google
    return {
        "providers": [asdict(p) for p in all_providers],
        "counts": {
            "total": len(all_providers),
            "configured": sum(1 for p in all_providers if p.configured),
            "web3": len(web3),
            "iot": len(iot),
            "google_official_public": len(google),
        },
        "safety": {
            "no_mainnet_signing": True,
            "no_private_key_storage": True,
            "no_fund_movement": True,
            "devnet_and_read_only_defaults": True,
        },
    }


def google_config_requirements() -> dict[str, list[str]]:
    return {
        "maps_or_places": ["GOOGLE_MAPS_API_KEY", "GOOGLE_PLACES_API_KEY"],
        "civic": ["GOOGLE_CIVIC_API_KEY"],
        "vision": ["GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_VISION_API_KEY"],
    }


def web3_config_requirements() -> dict[str, list[str]]:
    return {
        "solana_devnet": ["MEMBRA_SOLANA_DEVNET_RPC_URL", "MEMBRA_SOLANA_DEVNET_ENABLED", "MEMBRA_SOLANA_DRY_RUN"],
        "ethereum_sepolia": ["ETHEREUM_SEPOLIA_RPC_URL"],
        "polygon_amoy": ["POLYGON_AMOY_RPC_URL"],
        "base_sepolia": ["BASE_SEPOLIA_RPC_URL"],
    }


def iot_config_requirements() -> dict[str, list[str]]:
    return {
        "http_ingest": ["MEMBRA_IOT_INGEST_TOKEN"],
        "mqtt_bridge": ["MQTT_BROKER_URL", "MQTT_USERNAME", "MQTT_PASSWORD"],
    }
