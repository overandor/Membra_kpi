"""iPhone photo -> MEMBRA marketplace listing pipeline.

This module contains real production-facing application code, not a mock.
It accepts an iPhone/HEIC-converted/JPEG/PNG/WebP upload, stores the photo,
runs the existing deterministic MEMBRA assetification engine, writes inventory,
SKU, KPI, ProofBook, listing draft, optional owner-confirmed public listing,
payout eligibility, wallet ledger, and QR artifact records.

Wire into app.py with:

    from membra_kpi.iphone_marketplace import register_iphone_marketplace_routes
    register_iphone_marketplace_routes(
        app=app,
        deps={
            "save_upload": save_upload,
            "image_meta": image_meta,
            "new_id": new_id,
            "now": now,
            "execute": execute,
            "one": one,
            "insert_proof": insert_proof,
            "app_base_url": APP_BASE_URL,
        },
    )
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import File, Form, HTTPException, UploadFile

from .assetification import assetify_from_context
from .marketplace import confirm_visibility, create_listing_draft, request_visibility
from .proofbook import sha256_payload


@dataclass(frozen=True)
class IphoneListingDeps:
    save_upload: Callable[..., Any]
    image_meta: Callable[..., tuple[int, int]]
    new_id: Callable[[str], str]
    now: Callable[[], str]
    execute: Callable[[str, tuple[Any, ...]], None]
    one: Callable[[str, tuple[Any, ...]], dict[str, Any] | None]
    insert_proof: Callable[[str, str, str, dict[str, Any] | None], dict[str, Any]]
    app_base_url: str


def _to_deps(raw: dict[str, Any]) -> IphoneListingDeps:
    return IphoneListingDeps(
        save_upload=raw["save_upload"],
        image_meta=raw["image_meta"],
        new_id=raw["new_id"],
        now=raw["now"],
        execute=raw["execute"],
        one=raw["one"],
        insert_proof=raw["insert_proof"],
        app_base_url=raw["app_base_url"].rstrip("/"),
    )


def pick_best_inventory_item(items: list[dict[str, Any]], requested_asset_type: str = "") -> dict[str, Any]:
    """Choose one monetizable item from a photo analysis result.

    The engine may detect multiple monetization possibilities from one photo.
    This selector chooses the highest-confidence/highest-KPI item, optionally
    biased by requested_asset_type. It is deterministic for auditability.
    """
    if not items:
        raise HTTPException(422, "No inventory candidates were created from this picture.")

    requested = requested_asset_type.strip().lower()

    def score(item: dict[str, Any]) -> float:
        confidence = float(item.get("confidence") or 0)
        kpi = float(item.get("kpi_score") or 0) / 100
        bias = 0.0
        haystack = " ".join(
            str(item.get(k, ""))
            for k in ["asset_type", "detected_name", "listing_type", "monetization_type", "description"]
        ).lower()
        if requested and requested in haystack:
            bias = 0.35
        return confidence + kpi + bias

    return sorted(items, key=score, reverse=True)[0]


def _insert_inventory_bundle(deps: IphoneListingDeps, *, photo_id: str, owner_id: str, result: dict[str, Any]) -> list[dict[str, Any]]:
    drafts: list[dict[str, Any]] = []
    for item in result["detected_inventory"]:
        deps.execute(
            "INSERT INTO inventory_items VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                item["inventory_item_id"], photo_id, owner_id, item["sku"], item["detected_name"],
                item["asset_type"], item["visual_evidence"], item["monetization_type"],
                item["listing_type"], item["description"], item["suggested_price_low"],
                item["suggested_price_high"], item["pricing_unit"], item["confidence"],
                item["kpi_score"], json.dumps(item["proof_required"]), json.dumps(item["risk_flags"]),
                item["recommended_action"], item["status"], deps.now(),
            ),
        )
        category = item["sku"].split("-")[1]
        deps.execute(
            "INSERT INTO sku_map VALUES(?,?,?,?,?,?)",
            (item["sku"], item["inventory_item_id"], category, item["detected_name"], "active", deps.now()),
        )
        draft = create_listing_draft(item).to_dict()
        drafts.append(draft)
        deps.execute(
            "INSERT INTO listing_drafts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                draft["listing_id"], draft["inventory_item_id"], draft["sku"], draft["title"],
                draft["description"], draft["listing_type"], draft["suggested_price_low"],
                draft["suggested_price_high"], draft["pricing_unit"], draft["status"],
                draft["owner_visibility_requested_at"], draft["owner_confirmed_at"], draft["created_at"],
            ),
        )

    for card in result["kpi_cards"]:
        deps.execute(
            "INSERT INTO kpi_cards VALUES(?,?,?,?,?,?,?,?,?)",
            (
                deps.new_id("kpi"), card.get("source_photo_id"), card.get("inventory_item_id"),
                card["title"], card["value"], int(card["score"]), card["category"],
                card["explanation"], deps.now(),
            ),
        )
    return drafts


def _publish_listing(deps: IphoneListingDeps, *, draft: dict[str, Any], owner_id: str) -> dict[str, Any]:
    """Move one private draft through request->confirm->public marketplace."""
    listing_id = draft["listing_id"]
    requested = request_visibility(draft)
    deps.execute(
        "UPDATE listing_drafts SET status=?, owner_visibility_requested_at=? WHERE listing_id=?",
        (requested["status"], requested["owner_visibility_requested_at"], listing_id),
    )
    deps.execute(
        "INSERT INTO marketplace_events VALUES(?,?,?,?,?)",
        (deps.new_id("event"), listing_id, "visibility_requested", json.dumps({"status": requested["status"]}), deps.now()),
    )
    deps.insert_proof("listing", listing_id, "visibility_requested", {"status": requested["status"]})

    updated, public = confirm_visibility(requested)
    p = public.to_dict()
    deps.execute(
        "UPDATE listing_drafts SET status=?, owner_confirmed_at=? WHERE listing_id=?",
        (updated["status"], updated["owner_confirmed_at"], listing_id),
    )
    deps.execute(
        "INSERT INTO public_listings VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            p["public_listing_id"], p["listing_id"], p["sku"], p["title"], p["description"],
            p["price_low"], p["price_high"], p["pricing_unit"], p["visibility_status"], p["created_at"],
        ),
    )

    amount = round((float(draft["suggested_price_low"]) + float(draft["suggested_price_high"])) / 2, 2)
    deps.execute(
        "INSERT INTO payout_eligibility VALUES(?,?,?,?,?,?,?,?)",
        (
            deps.new_id("payout"), owner_id, "listing", listing_id, amount,
            "iphone_owner_confirmed_marketplace_visibility", "eligible_pending_external_settlement", deps.now(),
        ),
    )
    deps.execute(
        "INSERT INTO wallet_events VALUES(?,?,?,?,?,?,?,?,?)",
        (
            deps.new_id("ledger"), owner_id, "listing", listing_id, amount,
            "payout_eligibility_created", "eligible_pending_external_settlement",
            json.dumps({"public_listing_id": p["public_listing_id"], "source": "iphone_photo_pipeline"}), deps.now(),
        ),
    )
    deps.insert_proof("listing", listing_id, "visibility_confirmed", {"public_listing_id": p["public_listing_id"], "eligible_amount_usd": amount})
    return {"listing": updated, "public_listing": p, "eligible_amount_usd": amount}


def _create_listing_qr(deps: IphoneListingDeps, *, public_listing: dict[str, Any]) -> dict[str, Any]:
    artifact_id = deps.new_id("artifact")
    destination_url = f"{deps.app_base_url}/marketplace/{public_listing['public_listing_id']}"
    payload = {
        "artifact_id": artifact_id,
        "subject_type": "public_listing",
        "subject_id": public_listing["public_listing_id"],
        "destination_url": destination_url,
        "created_at": deps.now(),
    }
    artifact_hash = sha256_payload(payload)
    qr_url = f"{deps.app_base_url}/g/{artifact_id}"
    deps.execute(
        "INSERT INTO qr_artifacts VALUES(?,?,?,?,?,?,?,?,?)",
        (
            artifact_id, "public_listing", public_listing["public_listing_id"],
            f"QR for {public_listing['title']}", destination_url, artifact_hash, qr_url, "active", deps.now(),
        ),
    )
    deps.insert_proof("qr_artifact", artifact_id, "qr_artifact_created", {"artifact_hash": artifact_hash, "listing_id": public_listing["listing_id"]})
    return {"artifact_id": artifact_id, "artifact_hash": artifact_hash, "qr_url": qr_url, "destination_url": destination_url}


def register_iphone_marketplace_routes(app: Any, deps: dict[str, Any]) -> None:
    d = _to_deps(deps)

    @app.post("/api/iphone/listing/from-photo")
    async def iphone_photo_to_listing(
        image: UploadFile = File(...),
        owner_id: str = Form("owner_default"),
        room_type: str = Form(""),
        monetization_goal: str = Form(""),
        user_notes: str = Form(""),
        location_hint: str = Form(""),
        requested_asset_type: str = Form(""),
        publish: bool = Form(False),
        owner_confirmed: bool = Form(False),
    ) -> dict[str, Any]:
        """Convert one iPhone picture into MEMBRA listing records.

        publish=false: creates private draft only.
        publish=true + owner_confirmed=true: creates public marketplace listing.
        """
        filename, path = await d.save_upload(image, "iphone")
        width, height = d.image_meta(path)
        photo_id = d.new_id("photo")

        notes = " ".join(part for part in [user_notes, "iphone upload", requested_asset_type] if part).strip()
        result = assetify_from_context(
            photo_id=photo_id,
            owner_id=owner_id,
            room_type=room_type,
            monetization_goal=monetization_goal,
            user_notes=notes,
            location_hint=location_hint,
            filename=filename,
            width=width,
            height=height,
        )

        d.execute(
            "INSERT INTO photos VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                photo_id, owner_id, filename, str(path), image.content_type or "", width, height,
                room_type, monetization_goal, notes, location_hint, result["room_summary"],
                "iphone_analyzed", d.now(),
            ),
        )
        drafts = _insert_inventory_bundle(d, photo_id=photo_id, owner_id=owner_id, result=result)
        best_item = pick_best_inventory_item(result["detected_inventory"], requested_asset_type)
        best_draft = next((x for x in drafts if x["inventory_item_id"] == best_item["inventory_item_id"]), drafts[0])

        for event in ["iphone_photo_uploaded", "iphone_picture_inventory_mapped", "iphone_listing_draft_created"]:
            d.insert_proof("photo", photo_id, event, {"owner_id": owner_id, "filename": filename, "best_listing_id": best_draft["listing_id"]})

        response: dict[str, Any] = {
            "success": True,
            "mode": "public_listing" if publish and owner_confirmed else "private_draft",
            "photo_id": photo_id,
            "filename": filename,
            "image_metadata": {"width": width, "height": height, "content_type": image.content_type},
            "scenario": result["scenario"],
            "room_summary": result["room_summary"],
            "best_inventory_item": best_item,
            "private_listing_draft": best_draft,
            "all_listing_drafts": drafts,
            "proof_events": ["iphone_photo_uploaded", "iphone_picture_inventory_mapped", "iphone_listing_draft_created"],
            "safety": {
                "owner_approval_required": True,
                "earnings_not_guaranteed": True,
                "external_payment_rails_required": True,
            },
        }

        if publish and not owner_confirmed:
            response["publish_blocked_reason"] = "Set owner_confirmed=true to publish. Otherwise listing remains private."
            return response

        if publish and owner_confirmed:
            published = _publish_listing(d, draft=best_draft, owner_id=owner_id)
            qr = _create_listing_qr(d, public_listing=published["public_listing"])
            response.update(published)
            response["qr_artifact"] = qr
            response["marketplace_url"] = f"{d.app_base_url}/marketplace/{published['public_listing']['public_listing_id']}"
            response["proof_events"].extend(["visibility_requested", "visibility_confirmed", "qr_artifact_created"])

        return response
