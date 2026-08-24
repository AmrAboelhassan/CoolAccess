"""Tests for CoolAccess ScenarioBundle loader."""

from __future__ import annotations

import pytest

from coolaccess.contracts import AllocationRequest
from coolaccess.scenario import load_locked_scenario


def test_scenario_bundle_loading() -> None:
    bundle = load_locked_scenario()
    assert bundle.metadata["city_name"] == "Washington, DC"
    assert bundle.metadata["resource_budget_k"] == 3
    assert bundle.metadata["primary_catchment_radius_meters"] == 750
    assert len(bundle.facilities_definitions) == 6
    assert len(bundle.census_data["blocks"]) == 887


def test_scenario_build_request() -> None:
    bundle = load_locked_scenario()
    req_16 = bundle.build_allocation_request("16:00")
    assert isinstance(req_16, AllocationRequest)
    assert req_16.k == 3
    assert len(req_16.facilities) == 6
    assert len(req_16.demand_cells) == 887
    assert len(req_16.accessibility_relationships) > 0

    req_20 = bundle.build_allocation_request("20:00")
    assert isinstance(req_20, AllocationRequest)
    assert req_20.state_id == "state_dc_2000"


def test_scenario_invalid_timestamp() -> None:
    bundle = load_locked_scenario()
    with pytest.raises(ValueError, match="Unknown timestamp"):
        bundle.build_allocation_request("03:00")


def test_scenario_geojson_layers() -> None:
    bundle = load_locked_scenario()
    aoi = bundle.get_geojson("aoi")
    assert aoi["type"] == "FeatureCollection"
    assert len(aoi["features"]) >= 1

    facs = bundle.get_geojson("facilities")
    assert facs["type"] == "FeatureCollection"
    assert len(facs["features"]) == 6

    thermal = bundle.get_geojson("thermal", "16:00")
    assert thermal["type"] == "FeatureCollection"
    assert len(thermal["features"]) == 1452
    assert "temperature_c" in thermal["features"][0]["properties"]
    assert "thermal_priority" in thermal["features"][0]["properties"]

    all_layers = bundle.get_geojson("all", "20:00")
    assert "aoi" in all_layers
    assert "facilities" in all_layers
    assert "thermal" in all_layers
    assert "demand" in all_layers
