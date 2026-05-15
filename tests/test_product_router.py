import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient

from membra_kpi.deep_backend import apply_deep_backend_schema
from membra_kpi.product_router import build_product_router



def make_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    apply_deep_backend_schema(conn)
    return conn



def test_product_router_mounts():
    app = FastAPI()
    app.include_router(build_product_router(make_conn))

    client = TestClient(app)

    providers = client.get("/api/product/providers")
    assert providers.status_code == 200

    public_sources = client.get("/api/product/public-sources")
    assert public_sources.status_code == 200

    info_bits = client.get("/api/product/info-bits")
    assert info_bits.status_code == 200

    hf_status = client.get("/api/product/huggingface/status")
    assert hf_status.status_code == 200

    hf_models = client.get("/api/product/huggingface/models")
    assert hf_models.status_code == 200
    assert "models" in hf_models.json()



def test_info_gauntlet_creation():
    app = FastAPI()
    app.include_router(build_product_router(make_conn))

    client = TestClient(app)

    response = client.post(
        "/api/product/info-gauntlets/create",
        json={
            "tenant_id": "tenant_test",
            "actor_id": "tester",
            "listing": {
                "listing_id": "lst_123",
                "title": "Retail window frontage",
                "description": "High-density downtown retail frontage.",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "info_gauntlet" in body



def test_huggingface_listing_bundle_creation():
    app = FastAPI()
    app.include_router(build_product_router(make_conn))

    client = TestClient(app)

    response = client.post(
        "/api/product/huggingface/listing-bundle",
        json={
            "tenant_id": "tenant_hf",
            "actor_id": "hf_tester",
            "listing": {
                "listing_id": "lst_hf_1",
                "title": "Storefront activation zone",
                "description": "Retail storefront with visible glass frontage.",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "huggingface_bundle" in body
    assert len(body["huggingface_bundle"]["plans"]) >= 3
