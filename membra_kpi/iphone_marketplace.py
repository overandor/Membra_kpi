"""iPhone photo -> MEMBRA marketplace listing pipeline.

This module contains real production-facing application code, not a mock.
It accepts an iPhone/HEIC-converted/JPEG/PNG/WebP upload, stores the photo,
checks image quality, screens for duplicates, runs SKU identification, runs the
existing MEMBRA assetification engine, writes inventory, SKU, KPI, ProofBook,
listing draft, optional owner-confirmed public listing, payout eligibility,
wallet ledger, QR artifact records, and MEMBRA proprietary commercial packets.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from fastapi import File, Form, HTTPException, UploadFile

from .assetification import assetify_from_context
from .image_quality import analyze_image_file, hamming_distance_hex
from .image_sku_engine import identify_sku_candidates
from .marketplace import confirm_visibility, create_listing_draft, request_visibility
from .proofbook import sha256_payload
from .proprietary_listing_os import generate_listing_packet, summarize_packet_for_operator


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


def ensure_image_ingestion_table(deps: IphoneListingDeps) -> None:
    deps.execute(
        """
        CREATE TABLE IF NOT EXISTS image_ingestions(
          ingestion_id TEXT PRIMARY KEY,
          photo_id TEXT NOT NULL,
          owner_id TEXT NOT NULL,
          filename TEXT NOT NULL,
          file_path TEXT NOT NULL,
          exact_sha256 TEXT NOT NULL,
          average_hash TEXT NOT NULL,
          width INTEGER,
          height INTEGER,
          quality_score INTEGER,
          quality_grade TEXT,
          duplicate_of_photo_id TEXT,
          duplicate_distance INTEGER,
          sku_identification_json TEXT NOT NULL,
          quality_report_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        )
        """,
        (),
    )
    deps.execute("CREATE INDEX IF NOT EXISTS idx_image_ingestions_owner_sha ON image_ingestions(owner_id, exact_sha256)", ())
    deps.execute("CREATE INDEX IF NOT EXISTS idx_image_ingestions_owner_hash ON image_ingestions(owner_id, average_hash)", ())
    deps.execute(
        """
        CREATE TABLE IF NOT EXISTS proprietary_listing_packets(
          packet_id TEXT PRIMARY KEY,
          listing_id TEXT NOT NULL,
          inventory_item_id TEXT NOT NULL,
          photo_id TEXT NOT NULL,
          owner_id TEXT NOT NULL,
          sku TEXT NOT NULL,
          proprietary_asset_class TEXT NOT NULL,
          proof_score INTEGER NOT NULL,
          liquidity_score INTEGER NOT NULL,
          compliance_score INTEGER NOT NULL,
          operator_score INTEGER NOT NULL,
          valuation_score INTEGER NOT NULL,
          risk_tier TEXT NOT NULL,
          review_actions_json TEXT NOT NULL,
          missing_proof_json TEXT NOT NULL,
          packet_hash TEXT NOT NULL,
          packet_json TEXT NOT NULL,
          operator_summary_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        )
        """,
        (),
    )
    deps.execute("CREATE INDEX IF NOT EXISTS idx_packets_owner_score ON proprietary_listing_packets(owner_id, valuation_score)", ())
    deps.execute("CREATE INDEX IF NOT EXISTS idx_packets_listing ON proprietary_listing_packets(listing_id)", ())


def find_duplicate(deps: IphoneListingDeps, *, owner_id: str, exact_sha256: str, average_hash: str) -> dict[str, Any] | None:
    exact = deps.one(
        "SELECT * FROM image_ingestions WHERE owner_id=? AND exact_sha256=? ORDER BY created_at DESC LIMIT 1",
        (owner_id, exact_sha256),
    )
    if exact:
        exact["duplicate_distance"] = 0
        exact["duplicate_kind"] = "exact_sha256"
        return exact

    recent: list[dict[str, Any]] = []
    # The host app currently exposes one(), not rows(), through this module dependency.
    # Exact matching is enforced now; near-duplicate expansion is schema-ready and can be enabled once rows() is injected.
    for row in recent:
        dist = hamming_distance_hex(average_hash, row.get("average_hash", ""))
        if dist <= 6:
            row["duplicate_distance"] = dist
            row["duplicate_kind"] = "average_hash"
            return row
    return None


def pick_best_inventory_item(items: list[dict[str, Any]], requested_asset_type: str = "", sku_top: dict[str, Any] | None = None) -> dict[str, Any]:
    if not items:
        raise HTTPException(422, "No inventory candidates were created from this picture.")

    requested = requested_asset_type.strip().lower()
    sku_asset = (sku_top or {}).get("asset_type", "").lower()
    sku_family = (sku_top or {}).get("sku_family", "").lower()

    def score(item: dict[str, Any]) -> float:
        confidence = float(item.get("confidence") or 0)
        kpi = float(item.get("kpi_score") or 0) / 100
        haystack = " ".join(
            str(item.get(k, ""))
            for k in ["asset_type", "detected_name", "listing_type", "monetization_type", "description", "sku"]
        ).lower()
        bias = 0.0
        if requested and requested in haystack:
            bias += 0.35
        if sku_asset and sku_asset in haystack:
            bias += 0.30
        if sku_family and sku_family in haystack:
            bias += 0.15
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


def _persist_listing_packet(
    deps: IphoneListingDeps,
    *,
    packet: Any,
    operator_summary: dict[str, Any],
    photo_id: str,
    owner_id: str,
) -> None:
    data = packet.to_dict()
    deps.execute(
        "INSERT OR REPLACE INTO proprietary_listing_packets VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            data["packet_id"], data["listing_id"], data["inventory_item_id"], photo_id, owner_id,
            data["sku"], data["proprietary_asset_class"], data["proof_score"], data["liquidity_score"],
            data["compliance_score"], data["operator_score"], data["valuation_score"], data["risk_tier"],
            json.dumps(data["review_actions"], sort_keys=True), json.dumps(data["missing_proof"], sort_keys=True),
            data["packet_hash"], json.dumps(data, sort_keys=True), json.dumps(operator_summary, sort_keys=True), deps.now(),
        ),
    )


def _publish_listing(deps: IphoneListingDeps, *, draft: dict[str, Any], owner_id: str) -> dict[str, Any]:
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
    ensure_image_ingestion_table(d)

    @app.post("/api/iphone/listing/from-photo")
    async def iphone_photo_to_listing(
        image: UploadFile = File(...),
        owner_id: str = Form("owner_default"),
        room_type: str = Form(""),
        monetization_goal: str = Form(""),
        user_notes: str = Form(""),
        location_hint: str = Form(""),
        requested_asset_type: str = Form(""),
        owner_fields_json: str = Form("{}"),
        vision_labels_json: str = Form("[]"),
        publish: bool = Form(False),
        owner_confirmed: bool = Form(False),
        allow_duplicate: bool = Form(False),
        min_quality_score: int = Form(45),
    ) -> dict[str, Any]:
        filename, path = await d.save_upload(image, "iphone")
        width, height = d.image_meta(path)
        photo_id = d.new_id("photo")

        quality = analyze_image_file(Path(path)).to_dict()
        if int(quality["listing_quality_score"]) < int(min_quality_score):
            raise HTTPException(
                422,
                {
                    "error": "image_quality_too_low",
                    "quality_report": quality,
                    "message": "Retake or upload a clearer image before generating a marketplace listing.",
                },
            )

        duplicate = find_duplicate(
            d,
            owner_id=owner_id,
            exact_sha256=quality["exact_sha256"],
            average_hash=quality["average_hash"],
        )
        if duplicate and not allow_duplicate:
            raise HTTPException(
                409,
                {
                    "error": "duplicate_image",
                    "duplicate_photo_id": duplicate.get("photo_id"),
                    "duplicate_kind": duplicate.get("duplicate_kind", "exact_or_near_duplicate"),
                    "duplicate_distance": duplicate.get("duplicate_distance"),
                    "message": "This image appears to have already been ingested for this owner. Set allow_duplicate=true to override.",
                },
            )

        try:
            vision_labels = json.loads(vision_labels_json or "[]")
            if not isinstance(vision_labels, list):
                vision_labels = []
        except json.JSONDecodeError:
            vision_labels = []

        try:
            owner_fields = json.loads(owner_fields_json or "{}")
            if not isinstance(owner_fields, dict):
                owner_fields = {}
        except json.JSONDecodeError:
            owner_fields = {}

        sku_identification = identify_sku_candidates(
            filename=filename,
            width=width,
            height=height,
            room_type=room_type,
            monetization_goal=monetization_goal,
            user_notes=user_notes,
            location_hint=location_hint,
            requested_asset_type=requested_asset_type,
            vision_labels=[str(x) for x in vision_labels],
            limit=5,
        )
        sku_top = sku_identification["top_candidate"]

        notes = " ".join(
            part for part in [user_notes, "iphone upload", requested_asset_type, sku_top.get("asset_type", ""), sku_top.get("title", "")]
            if part
        ).strip()
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
        d.execute(
            "INSERT INTO image_ingestions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                d.new_id("ingest"), photo_id, owner_id, filename, str(path), quality["exact_sha256"],
                quality["average_hash"], width, height, quality["listing_quality_score"],
                quality["quality_grade"], duplicate.get("photo_id") if duplicate else None,
                duplicate.get("duplicate_distance") if duplicate else None,
                json.dumps(sku_identification, sort_keys=True), json.dumps(quality, sort_keys=True), d.now(),
            ),
        )

        drafts = _insert_inventory_bundle(d, photo_id=photo_id, owner_id=owner_id, result=result)
        best_item = pick_best_inventory_item(result["detected_inventory"], requested_asset_type, sku_top=sku_top)
        best_draft = next((x for x in drafts if x["inventory_item_id"] == best_item["inventory_item_id"]), drafts[0])

        listing_packet = generate_listing_packet(
            inventory_item=best_item,
            listing_draft=best_draft,
            sku_identification=sku_top,
            image_quality=quality,
            owner_fields=owner_fields,
            location_hint=location_hint,
        )
        operator_summary = summarize_packet_for_operator(listing_packet)
        _persist_listing_packet(d, packet=listing_packet, operator_summary=operator_summary, photo_id=photo_id, owner_id=owner_id)

        for event in [
            "iphone_photo_uploaded",
            "image_quality_scored",
            "sku_identified",
            "iphone_picture_inventory_mapped",
            "iphone_listing_draft_created",
            "proprietary_listing_packet_generated",
        ]:
            d.insert_proof(
                "photo",
                photo_id,
                event,
                {
                    "owner_id": owner_id,
                    "filename": filename,
                    "best_listing_id": best_draft["listing_id"],
                    "quality_score": quality["listing_quality_score"],
                    "top_sku": sku_top["sku"],
                    "packet_id": listing_packet.packet_id,
                    "valuation_score": listing_packet.valuation_score,
                    "risk_tier": listing_packet.risk_tier,
                },
            )

        response: dict[str, Any] = {
            "success": True,
            "mode": "public_listing" if publish and owner_confirmed else "private_draft",
            "photo_id": photo_id,
            "filename": filename,
            "image_metadata": {"width": width, "height": height, "content_type": image.content_type},
            "image_quality": quality,
            "sku_identification": sku_identification,
            "proprietary_listing_packet": listing_packet.to_dict(),
            "operator_summary": operator_summary,
            "scenario": result["scenario"],
            "room_summary": result["room_summary"],
            "best_inventory_item": best_item,
            "private_listing_draft": best_draft,
            "all_listing_drafts": drafts,
            "proof_events": [
                "iphone_photo_uploaded",
                "image_quality_scored",
                "sku_identified",
                "iphone_picture_inventory_mapped",
                "iphone_listing_draft_created",
                "proprietary_listing_packet_generated",
            ],
            "safety": {
                "owner_approval_required": True,
                "earnings_not_guaranteed": True,
                "external_payment_rails_required": True,
                "duplicate_screening": True,
                "image_quality_gate": True,
                "operator_review_routing": True,
                "proprietary_packet_hash": listing_packet.packet_hash,
            },
        }

        if publish and not owner_confirmed:
            response["publish_blocked_reason"] = "Set owner_confirmed=true to publish. Otherwise listing remains private."
            return response

        if publish and owner_confirmed:
            if "block_publication" in listing_packet.review_actions:
                response["publish_blocked_reason"] = "MEMBRA proprietary packet blocks publication until required proof/compliance fields are resolved."
                return response
            published = _publish_listing(d, draft=best_draft, owner_id=owner_id)
            qr = _create_listing_qr(d, public_listing=published["public_listing"])
            response.update(published)
            response["qr_artifact"] = qr
            response["marketplace_url"] = f"{d.app_base_url}/marketplace/{published['public_listing']['public_listing_id']}"
            response["proof_events"].extend(["visibility_requested", "visibility_confirmed", "qr_artifact_created"])

        return response
