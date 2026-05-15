from membra_kpi.infinite_kpi import (
    build_infinite_kpi_production_plan,
    build_kpi_batch,
    derive_kpi_value,
    list_kpi_templates,
)



def test_kpi_templates_exist():
    templates = list_kpi_templates()
    assert len(templates) >= 10
    assert templates[0]["priority"] >= templates[-1]["priority"]



def test_kpi_batch_is_bounded():
    listing = {"listing_id": "lst_1", "title": "Window ad placement", "description": "High visibility first-floor window.", "city": "Chicago"}
    batch = build_kpi_batch(listing=listing, limit=3)
    assert batch["count"] == 3
    assert batch["execution_mode"] == "bounded_batch_not_uncontrolled_loop"
    assert all(0 <= kpi["metric_value"] <= 100 for kpi in batch["kpis"])



def test_infinite_kpi_plan_contains_worker_policy():
    plan = build_infinite_kpi_production_plan(listing={"listing_id": "lst_2", "title": "Shelf placement", "description": "Retail shelf display."})
    assert plan["worker_policy"]["no_unbounded_web_loop"] is True
    assert plan["first_batch"]["count"] > 0
    assert "hypermodular_packet_summary" in plan
