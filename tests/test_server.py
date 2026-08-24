"""Tests for CoolAccess FastAPI backend endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from coolaccess.server import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["city"] == "Washington, DC"


def test_scenario_endpoint() -> None:
    response = client.get("/api/scenario")
    assert response.status_code == 200
    data = response.json()
    assert data["city"] == "Washington, DC"
    assert data["resource_budget_k"] == 3
    assert data["catchment_radius_meters"] == 750
    assert len(data["candidate_facilities"]) == 6
    assert len(data["available_timestamps_utc"]) == 5
    assert "DC_089" in [f["facility_id"] for f in data["candidate_facilities"]]


def test_allocate_midday_1600() -> None:
    response = client.get("/api/allocate?timestamp=16:00")
    assert response.status_code == 200
    data = response.json()
    assert data["timestamp"] == "16:00"
    assert data["k"] == 3
    # Midday selection at 16:00 UTC
    assert data["selected_facility_ids"] == ["DC_089", "DC_148", "DC_166"]
    assert data["coverage_metrics"]["covered_heat_weighted_demand"] > 0
    assert data["coverage_metrics"]["covered_population"] > 0


def test_allocate_late_afternoon_2000_and_baseline_gains() -> None:
    response = client.get("/api/allocate?timestamp=20:00&baseline_timestamp=16:00")
    assert response.status_code == 200
    data = response.json()
    assert data["timestamp"] == "20:00"
    assert data["baseline_timestamp"] == "16:00"
    assert data["k"] == 3

    # Dynamic optimal selection at 20:00 UTC
    assert data["selected_facility_ids"] == ["DC_089", "DC_135", "DC_166"]

    # Static baseline reuses 16:00 selection
    static_b = data["static_baseline"]
    assert static_b["selected_facility_ids"] == ["DC_089", "DC_148", "DC_166"]

    # Validate that dynamic beats static baseline
    opt_demand = data["coverage_metrics"]["covered_heat_weighted_demand"]
    static_demand = static_b["objective_value"]
    assert opt_demand > static_demand
    assert static_b["absolute_gain"] > 0
    assert static_b["percentage_gain"] > 0

    # Naive baseline checks
    naive_b = data["naive_baseline"]
    assert naive_b["objective_value"] > 0
    assert len(naive_b["selected_facility_ids"]) == 3


def test_replacement_endpoint_primary_transition() -> None:
    response = client.get("/api/replacement?timestamp=20:00")
    assert response.status_code == 200
    data = response.json()
    assert data["timestamp"] == "20:00"
    assert data["optimal_selected_facilities"] == ["DC_089", "DC_135", "DC_166"]

    primary = data["primary_replacement"]
    assert primary["selected_facility"]["facility_id"] == "DC_135"
    assert primary["alternative_facility"]["facility_id"] == "DC_148"
    assert primary["comparator_outcome"] == "original_preferred"
    assert primary["reason_code"] == "primary_objective_loss"
    assert primary["primary_objective_loss"] > 0
    assert primary["objective_delta"] < 0
    # Population delta is positive because DC_148 has larger raw population
    assert primary["population_delta"] > 0
    assert "explanation" in primary


def test_geojson_endpoints() -> None:
    resp_aoi = client.get("/api/geojson?layer=aoi")
    assert resp_aoi.status_code == 200
    assert resp_aoi.json()["type"] == "FeatureCollection"

    resp_fac = client.get("/api/geojson?layer=facilities")
    assert resp_fac.status_code == 200
    assert len(resp_fac.json()["features"]) == 6

    resp_thermal = client.get("/api/geojson?layer=thermal&timestamp=16:00")
    assert resp_thermal.status_code == 200
    assert len(resp_thermal.json()["features"]) == 1452

    resp_invalid = client.get("/api/geojson?layer=unknown_layer")
    assert resp_invalid.status_code == 400


def test_allocate_invalid_timestamp() -> None:
    response = client.get("/api/allocate?timestamp=99:99")
    assert response.status_code == 400


def test_api_404_not_intercepted_by_spa() -> None:
    # Non-existent API route must return 404, not SPA index.html
    response = client.get("/api/non_existent_endpoint")
    assert response.status_code == 404


def test_heat_intelligence_brief_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COOLACCESS_AI_ENABLED", "false")
    payload = {
        "question": "What changed in thermal exposure between 16:00 and 20:00 UTC?",
        "timestamp": "20:00",
        "baseline_timestamp": "16:00",
        "radius_meters": 750,
        "k": 3,
    }
    response = client.post("/api/heat-intelligence/brief", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "brief_items" in data
    assert len(data["brief_items"]) > 0
    assert "plan_fingerprint" in data
    assert len(data["mandatory_caveats"]) >= 3
