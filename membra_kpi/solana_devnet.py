"""Solana devnet listing anchor adapter for MEMBRA KPI.

This module is intentionally devnet-only. It creates deterministic listing
anchor payloads and records adapter status. It does not custody funds, does not
move tokens, and does not support mainnet execution.

Runtime behavior:
- default: dry-run anchor intent only
- enabled devnet send requires MEMBRA_SOLANA_DEVNET_ENABLED=true plus a devnet keypair path
- any non-devnet RPC URL is rejected
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .deep_backend import BackendContext, append_chain_event, canonical_json, sha256_text, utc_now

DEVNET_RPC_DEFAULT = "https://api.devnet.solana.com"


@dataclass(slots=True)
class SolanaDevnetConfig:
    enabled: bool
    rpc_url: str
    keypair_path: str
    dry_run: bool


def load_solana_devnet_config() -> SolanaDevnetConfig:
    return SolanaDevnetConfig(
        enabled=os.getenv("MEMBRA_SOLANA_DEVNET_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"},
        rpc_url=os.getenv("MEMBRA_SOLANA_DEVNET_RPC_URL", DEVNET_RPC_DEFAULT).strip() or DEVNET_RPC_DEFAULT,
        keypair_path=os.getenv("MEMBRA_SOLANA_DEVNET_KEYPAIR", "").strip(),
        dry_run=os.getenv("MEMBRA_SOLANA_DRY_RUN", "true").strip().lower() not in {"0", "false", "no", "off"},
    )


def ensure_devnet_rpc(rpc_url: str) -> None:
    lowered = rpc_url.lower()
    if "devnet" not in lowered:
        raise ValueError("Solana adapter is devnet-only. Refusing non-devnet RPC URL.")


def listing_anchor_payload(listing: dict[str, Any], proof_hash: str | None = None) -> dict[str, Any]:
    listing_id = str(listing.get("listing_id") or listing.get("public_listing_id") or listing.get("inventory_item_id") or "unknown")
    payload = {
        "protocol": "MEMBRA_LISTING_ANCHOR_V1",
        "network": "solana-devnet",
        "listing_id": listing_id,
        "sku": listing.get("sku"),
        "title": listing.get("title"),
        "description_hash": sha256_text(str(listing.get("description", ""))),
        "price_low": listing.get("price_low") or listing.get("suggested_price_low"),
        "price_high": listing.get("price_high") or listing.get("suggested_price_high"),
        "pricing_unit": listing.get("pricing_unit"),
        "proof_hash": proof_hash,
        "created_at": utc_now(),
    }
    payload["anchor_hash"] = sha256_text(canonical_json(payload))
    return payload


def memo_text_for_payload(payload: dict[str, Any]) -> str:
    compact = canonical_json(payload)
    return "MEMBRA:" + base64.b64encode(compact.encode("utf-8")).decode("ascii")


def build_solana_cli_command(memo_text: str, config: SolanaDevnetConfig) -> list[str]:
    ensure_devnet_rpc(config.rpc_url)
    if not config.keypair_path:
        raise ValueError("MEMBRA_SOLANA_DEVNET_KEYPAIR is required for devnet send mode.")
    if not Path(config.keypair_path).exists():
        raise FileNotFoundError("Configured Solana devnet keypair path does not exist.")
    return [
        "spl-token",
        "transfer",
        "--url",
        config.rpc_url,
        "--fund-recipient",
        "--allow-unfunded-recipient",
        "--owner",
        config.keypair_path,
        "So11111111111111111111111111111111111111112",
        "0",
        "11111111111111111111111111111111",
        "--memo",
        memo_text,
    ]


def anchor_listing_on_solana_devnet(conn, context: BackendContext, listing: dict[str, Any], proof_hash: str | None = None) -> dict[str, Any]:
    config = load_solana_devnet_config()
    ensure_devnet_rpc(config.rpc_url)
    payload = listing_anchor_payload(listing, proof_hash=proof_hash)
    memo_text = memo_text_for_payload(payload)
    result: dict[str, Any] = {
        "network": "solana-devnet",
        "mode": "dry_run",
        "sent": False,
        "signature": None,
        "payload": payload,
        "memo_preview": memo_text[:96] + "...",
        "error": None,
    }

    if config.enabled and not config.dry_run:
        try:
            command = build_solana_cli_command(memo_text, config)
            completed = subprocess.run(command, check=True, capture_output=True, text=True, timeout=45)
            result["mode"] = "devnet_send"
            result["sent"] = True
            result["signature"] = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else None
        except Exception as exc:
            result["mode"] = "devnet_send_failed"
            result["error"] = str(exc)

    append_chain_event(
        conn,
        context,
        "listing",
        str(payload["listing_id"]),
        "solana_devnet.anchor_intent" if not result["sent"] else "solana_devnet.anchor_sent",
        result,
    )
    return result


def solana_devnet_status() -> dict[str, Any]:
    config = load_solana_devnet_config()
    return {
        "network": "solana-devnet",
        "enabled": config.enabled,
        "dry_run": config.dry_run,
        "rpc_url": config.rpc_url,
        "keypair_configured": bool(config.keypair_path),
        "devnet_only": True,
    }
