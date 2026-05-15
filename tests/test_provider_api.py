from membra_kpi.provider_api import (
    get_all_provider_status,
    get_google_status,
    get_iot_status,
    get_provider_requirements,
    get_web3_status,
    safe_google_request_blueprint,
)



def test_provider_registry_structure():
    registry = get_all_provider_status()

    assert "providers" in registry
    assert "counts" in registry
    assert registry["counts"]["total"] >= 1



def test_provider_requirements_structure():
    requirements = get_provider_requirements()

    assert "web3" in requirements
    assert "iot" in requirements
    assert "google_official_public" in requirements



def test_google_blueprint_is_safe_only():
    result = safe_google_request_blueprint(
        "google-places",
        {"query": "coffee shops", "location": "Chicago"},
    )

    assert result["mode"] == "blueprint_only"
    assert "No external request executed" in result["note"]



def test_status_filters():
    assert "providers" in get_google_status()
    assert "providers" in get_iot_status()
    assert "providers" in get_web3_status()
