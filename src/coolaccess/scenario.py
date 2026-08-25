"""Scenario data bundle loader and request builder for CoolAccess.

Loads the locked Washington, DC Gate C empirical scenario bundle and constructs
immutable, validated domain objects for deterministic allocation.
"""

from __future__ import annotations

import json
import math
import os
import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from coolaccess.contracts import (
    AccessibilityRelationship,
    AllocationRequest,
    ConfigurationReference,
    DataState,
    EligibilityStatus,
    FacilityDefinition,
    PopulationCell,
    ProvenanceRecord,
    ProvenanceScope,
    SourceKind,
)
from coolaccess.demand import canonical_decimal

# Default path to packaged scenario data (supports COOLACCESS_DATA_DIR env override)
DEFAULT_DATA_DIR = (
    Path(os.environ["COOLACCESS_DATA_DIR"])
    if "COOLACCESS_DATA_DIR" in os.environ
    else Path(__file__).resolve().parent.parent.parent / "data" / "locked_dc_scenario"
)

MIN_RADIUS_METERS = 100
MAX_RADIUS_METERS = 5000

_LOCKED_FACILITY_ALIASES: dict[str, tuple[str, ...]] = {
    "DC_089": ("shaw", "shaw library", "watha", "watha t daniel"),
    "DC_135": ("mlk", "martin luther king", "mlk library"),
    "DC_148": ("northeast", "northeast library"),
    "DC_159": ("southeast", "southeast library"),
    "DC_166": ("randall", "randall recreation center"),
    "DC_168": ("southwest", "southwest library"),
}


def _normalize_facility_text(value: str) -> str:
    """Normalize facility wording for deterministic whole-token alias matching."""
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters between two coordinates."""
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * R * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def sanitize_timestamp_key(ts: str) -> str:
    """Normalize '16:00', '16:00 UTC', '1600', or '16' to '1600'."""
    cleaned = ts.strip().replace(":", "").replace("UTC", "").replace("Z", "").strip()
    if len(cleaned) == 2:
        cleaned += "00"
    return cleaned


def format_timestamp_display(ts_key: str) -> str:
    """Format '1600' to '16:00'."""
    clean = sanitize_timestamp_key(ts_key)
    return f"{clean[:2]}:{clean[2:]}"


class ScenarioBundle:
    """Container holding locked scenario inputs and building AllocationRequests."""

    def __init__(self, data_dir: Path | str = DEFAULT_DATA_DIR) -> None:
        self.data_dir = Path(data_dir)
        self._validate_required_files()
        self._load_data()
        self._build_provenance_registry()
        self._build_facilities_definitions()

    def _validate_required_files(self) -> None:
        required = [
            "metadata.json",
            "facilities.json",
            "census_blocks.json",
            "thermal_snapshots.json",
            "catchments.json",
            "geojson/aoi.geojson",
            "geojson/facilities.geojson",
            "geojson/grid.geojson",
            "geojson/census_blocks.geojson",
        ]
        missing = [f for f in required if not (self.data_dir / f).exists()]
        if missing:
            raise FileNotFoundError(
                f"Scenario data bundle at '{self.data_dir}' is missing required files: {missing}"
            )

    def _load_data(self) -> None:
        with open(self.data_dir / "metadata.json", encoding="utf-8") as f:
            self.metadata: dict[str, Any] = json.load(f)

        with open(self.data_dir / "facilities.json", encoding="utf-8") as f:
            self.facilities_data: dict[str, Any] = json.load(f)

        with open(self.data_dir / "census_blocks.json", encoding="utf-8") as f:
            self.census_data: dict[str, Any] = json.load(f)

        with open(self.data_dir / "thermal_snapshots.json", encoding="utf-8") as f:
            self.thermal_data: dict[str, Any] = json.load(f)

        with open(self.data_dir / "catchments.json", encoding="utf-8") as f:
            self.catchments_data: dict[str, Any] = json.load(f)

        # Anchors for Normalization Method A
        anchors = self.thermal_data.get("normalization_anchors", {})
        self.p1_lower: float = float(anchors.get("p1_lower_anchor_c", 32.022))
        self.p99_upper: float = float(anchors.get("p99_upper_anchor_c", 37.699))

    def _build_provenance_registry(self) -> None:
        now_utc = datetime(2026, 8, 24, 12, 0, 0, tzinfo=UTC)
        self.prov_pop = ProvenanceRecord(
            provenance_id="prov_census_2020_p1",
            scope=ProvenanceScope.INVARIANT,
            source_kind=SourceKind.POPULATION,
            source_name="U.S. Census Bureau 2020 Decennial Census Table P1",
            dataset_title="2020 Census Blocks for District of Columbia",
            license_reference="Public Domain (U.S. Government Work)",
            source_vintage="2020",
            data_state=DataState.STATIC,
            retrieved_at=now_utc,
        )
        self.prov_fg = ProvenanceRecord(
            provenance_id="prov_fortyguard_tcm_gate_b2",
            scope=ProvenanceScope.THERMAL_STATE,
            source_kind=SourceKind.THERMAL_PRIORITY,
            source_name="FortyGuard Temperature API (tcm, 100m)",
            dataset_title="FortyGuard Urban Thermal Snapshots 2024-07-15",
            license_reference="FortyGuard Commercial Hackathon API License",
            source_vintage="2024-07-15",
            data_state=DataState.PREPARED,
            retrieved_at=now_utc,
        )
        self.prov_fac = ProvenanceRecord(
            provenance_id="prov_dc_facilities_octo",
            scope=ProvenanceScope.INVARIANT,
            source_kind=SourceKind.FACILITY,
            source_name="Open Data DC / OCTO Public Facilities Directory",
            dataset_title="DC GIS Cooling Centers",
            license_reference="Creative Commons CC0 1.0 Universal",
            source_vintage="2024",
            data_state=DataState.STATIC,
            retrieved_at=now_utc,
        )
        self.prov_cfg = ProvenanceRecord(
            provenance_id="prov_coolaccess_config_v1",
            scope=ProvenanceScope.INVARIANT,
            source_kind=SourceKind.CONFIGURATION,
            source_name="CoolAccess Deterministic Engine",
            license_reference="Proprietary",
            source_vintage="2026",
            data_state=DataState.STATIC,
            retrieved_at=now_utc,
        )
        self.registry = (self.prov_pop, self.prov_fg, self.prov_fac, self.prov_cfg)

    def _build_facilities_definitions(self) -> None:
        self.facilities_definitions = tuple(
            FacilityDefinition(
                facility_id=f["facility_id"],
                label=f["name"],
                eligibility_status=EligibilityStatus.ELIGIBLE,
                eligibility_reason="Official public municipal facility",
                location_ref=f"lat={f['latitude']},lon={f['longitude']}",
                source_provenance_refs=("prov_dc_facilities_octo",),
                eligibility_provenance_refs=("prov_dc_facilities_octo",),
            )
            for f in self.facilities_data["facilities"]
        )

    def normalize_temperature(self, temp_c: float) -> Decimal:
        """Apply Method A (Robust Fixed Anchors) linear clamping to [0, 1]."""
        norm = (temp_c - self.p1_lower) / (self.p99_upper - self.p1_lower)
        clamped = max(0.0, min(1.0, norm))
        return canonical_decimal(Decimal(str(round(clamped, 6))))

    def build_allocation_request(
        self,
        timestamp: str = "16:00",
        radius_meters: int = 750,
        k: int = 3,
    ) -> AllocationRequest:
        """Build an immutable AllocationRequest for the specified timestamp and radius."""
        facility_count = len(self.facilities_definitions)
        if not MIN_RADIUS_METERS <= radius_meters <= MAX_RADIUS_METERS:
            raise ValueError(
                f"radius_meters must be between {MIN_RADIUS_METERS} and {MAX_RADIUS_METERS}."
            )
        if not 1 <= k <= facility_count:
            raise ValueError(f"k must be between 1 and {facility_count} for this scenario.")

        ts_key = sanitize_timestamp_key(timestamp)
        temps_map = self.thermal_data["temperatures_by_timestamp"].get(ts_key)
        if temps_map is None:
            available = list(self.thermal_data["temperatures_by_timestamp"].keys())
            raise ValueError(f"Unknown timestamp '{timestamp}'. Available timestamps: {available}")

        hour_int = int(ts_key[:2])
        valid_at_dt = datetime(2024, 7, 15, hour_int, 0, 0, tzinfo=UTC)

        # Build demand cells
        cells: list[PopulationCell] = []
        for b in self.census_data["blocks"]:
            t_id = b["matched_fortyguard_tile_id"]
            temp_val = temps_map[str(t_id)]
            priority = self.normalize_temperature(temp_val)
            cells.append(
                PopulationCell(
                    cell_id=b["geoid"],
                    population=canonical_decimal(Decimal(str(b["population"]))),
                    thermal_priority=priority,
                    population_provenance_refs=("prov_census_2020_p1",),
                    thermal_state_provenance_refs=("prov_fortyguard_tcm_gate_b2",),
                )
            )

        # Build accessibility relationships
        edges: list[AccessibilityRelationship] = []
        for b in self.census_data["blocks"]:
            bx, by = b["centroid"][0], b["centroid"][1]
            for f in self.facilities_data["facilities"]:
                fx, fy = f["longitude"], f["latitude"]
                dist = haversine_meters(by, bx, fy, fx)
                if dist <= radius_meters:
                    edges.append(
                        AccessibilityRelationship(
                            cell_id=b["geoid"],
                            facility_id=f["facility_id"],
                            is_accessible=True,
                            accessibility_configuration_id=f"cfg_radius_{radius_meters}m",
                            provenance_refs=("prov_coolaccess_config_v1",),
                        )
                    )

        return AllocationRequest(
            scenario_id=f"DC_CoolAccess_RobustAnchors_r{radius_meters}m",
            state_id=f"state_dc_{ts_key}",
            valid_at=valid_at_dt,
            facilities=self.facilities_definitions,
            demand_cells=tuple(cells),
            accessibility_relationships=tuple(edges),
            k=k,
            thermal_priority_reference=ConfigurationReference(
                configuration_id="cfg_robust_fixed_anchors_v1",
                version="1.0",
                provenance_refs=("prov_coolaccess_config_v1",),
            ),
            accessibility_configuration=ConfigurationReference(
                configuration_id=f"cfg_radius_{radius_meters}m",
                version="1.0",
                provenance_refs=("prov_coolaccess_config_v1",),
            ),
            invariant_provenance_refs=(
                "prov_census_2020_p1",
                "prov_dc_facilities_octo",
                "prov_coolaccess_config_v1",
            ),
            thermal_state_provenance_refs=("prov_fortyguard_tcm_gate_b2",),
            provenance_registry=self.registry,
        )

    def get_facility_ids(self) -> tuple[str, ...]:
        """Return tuple of authoritative candidate facility identifiers."""
        return tuple(f["facility_id"] for f in self.facilities_data.get("facilities", []))

    def get_facility_name_map(self) -> dict[str, str]:
        """Return mapping of facility_id -> full facility name."""
        return {
            f["facility_id"]: f["name"]
            for f in self.facilities_data.get("facilities", [])
        }

    def get_facility_address_map(self) -> dict[str, str]:
        """Return mapping of facility_id -> street address."""
        return {
            f["facility_id"]: f.get("address") or ""
            for f in self.facilities_data.get("facilities", [])
        }

    def resolve_facility(self, query: str | None) -> str | None:
        """Resolve the first explicitly mentioned facility for compatibility."""
        resolved = self.resolve_facilities(query)
        return resolved[0] if resolved else None

    def resolve_facilities(self, query: str | None) -> tuple[str, ...]:
        """Resolve every explicit facility mention in user order.

        IDs, authoritative full names, and a small scenario-owned alias table are
        matched as complete normalized phrases. Generic words such as ``library``
        never identify a facility.
        """
        if not query:
            return ()

        normalized_query = _normalize_facility_text(query)
        if not normalized_query:
            return ()
        padded_query = f" {normalized_query} "

        matches: dict[str, int] = {}
        name_map = self.get_facility_name_map()
        for fid in self.get_facility_ids():
            suffix = fid.split("_")[-1]
            aliases = {
                _normalize_facility_text(fid),
                fid.casefold().replace("_", ""),
                suffix.casefold(),
                _normalize_facility_text(name_map[fid]),
                *(
                    _normalize_facility_text(alias)
                    for alias in _LOCKED_FACILITY_ALIASES.get(fid, ())
                ),
            }
            positions = [
                padded_query.find(f" {alias} ")
                for alias in aliases
                if alias and padded_query.find(f" {alias} ") >= 0
            ]
            if positions:
                matches[fid] = min(positions)

        return tuple(fid for fid, _ in sorted(matches.items(), key=lambda item: (item[1], item[0])))

    def get_thermal_statistics(self, from_ts: str, to_ts: str) -> dict[str, Any]:
        """Compute empirical FortyGuard 100m raster temperature statistics for two timestamps."""
        from_key = sanitize_timestamp_key(from_ts)
        to_key = sanitize_timestamp_key(to_ts)

        temps_from_map = self.thermal_data["temperatures_by_timestamp"].get(from_key)
        temps_to_map = self.thermal_data["temperatures_by_timestamp"].get(to_key)

        if temps_from_map is None:
            raise ValueError(f"Unknown from_timestamp '{from_ts}'")
        if temps_to_map is None:
            raise ValueError(f"Unknown to_timestamp '{to_ts}'")

        from_vals = sorted(float(v) for v in temps_from_map.values())
        to_vals = sorted(float(v) for v in temps_to_map.values())
        n = len(from_vals)

        def _calc_stats(vals: list[float]) -> dict[str, float]:
            mean_v = sum(vals) / len(vals)
            min_v = vals[0]
            max_v = vals[-1]
            med_idx = len(vals) // 2
            med_v = (
                vals[med_idx]
                if len(vals) % 2 == 1
                else (vals[med_idx - 1] + vals[med_idx]) / 2.0
            )
            p90_idx = int(len(vals) * 0.90)
            p90_v = vals[min(p90_idx, len(vals) - 1)]
            return {
                "mean_c": round(mean_v, 2),
                "min_c": round(min_v, 2),
                "max_c": round(max_v, 2),
                "median_c": round(med_v, 2),
                "p90_c": round(p90_v, 2),
            }

        # Elevated thermal-priority threshold (> 0.70 weight)
        from_high = sum(1 for v in from_vals if float(self.normalize_temperature(v)) > 0.70)
        to_high = sum(1 for v in to_vals if float(self.normalize_temperature(v)) > 0.70)

        from_stats = _calc_stats(from_vals)
        to_stats = _calc_stats(to_vals)

        return {
            "from_timestamp": format_timestamp_display(from_ts),
            "to_timestamp": format_timestamp_display(to_ts),
            "total_tiles": n,
            "from_stats": from_stats,
            "to_stats": to_stats,
            "mean_temp_delta_c": round(to_stats["mean_c"] - from_stats["mean_c"], 2),
            "from_high_priority_cells": from_high,
            "to_high_priority_cells": to_high,
            "high_priority_cell_delta": to_high - from_high,
            "thermal_priority_threshold": 0.70,
        }

    def get_metadata(self) -> dict[str, Any]:
        """Return scenario configuration and metadata."""
        return self.metadata

    def get_facilities(self) -> list[dict[str, Any]]:
        """Return list of candidate facilities."""
        return list(self.facilities_data.get("facilities", []))

    def get_timestamps(self) -> list[str]:
        """Return list of available formatted timestamps."""
        return list(self.metadata.get("available_timestamps_utc", []))

    def get_geojson(self, layer: str = "all", timestamp: str = "16:00") -> dict[str, Any]:
        """Return GeoJSON FeatureCollection(s) for the requested layer."""
        ts_key = sanitize_timestamp_key(timestamp)
        temps_map = self.thermal_data["temperatures_by_timestamp"].get(ts_key)
        if temps_map is None:
            raise ValueError("Unsupported prepared benchmark timestamp.")

        if layer == "aoi":
            with open(self.data_dir / "geojson" / "aoi.geojson", encoding="utf-8") as f:
                return cast(dict[str, Any], json.load(f))

        if layer == "facilities":
            with open(self.data_dir / "geojson" / "facilities.geojson", encoding="utf-8") as f:
                return cast(dict[str, Any], json.load(f))

        if layer == "demand":
            with open(self.data_dir / "geojson" / "census_blocks.geojson", encoding="utf-8") as f:
                data = cast(dict[str, Any], json.load(f))
                # Enrich with current temperature and normalized thermal weight
                for feat in data["features"]:
                    t_id = str(feat["properties"]["matched_tile_id"])
                    if t_id in temps_map:
                        t_val = temps_map[t_id]
                        feat["properties"]["temperature_c"] = t_val
                        feat["properties"]["thermal_priority"] = float(
                            self.normalize_temperature(t_val)
                        )
                data["metadata"] = {
                    "timestamp": format_timestamp_display(ts_key),
                    "thermal_data_status": "available",
                }
                return data

        if layer == "thermal":
            with open(self.data_dir / "geojson" / "grid.geojson", encoding="utf-8") as f:
                data = cast(dict[str, Any], json.load(f))
                for feat in data["features"]:
                    t_id = str(feat["properties"]["tile_id"])
                    if t_id in temps_map:
                        t_val = temps_map[t_id]
                        feat["properties"]["temperature_c"] = t_val
                        feat["properties"]["thermal_priority"] = float(
                            self.normalize_temperature(t_val)
                        )
                data["metadata"] = {
                    "timestamp": format_timestamp_display(ts_key),
                    "thermal_data_status": "available",
                }
                return data

        if layer == "all":
            return {
                "aoi": self.get_geojson("aoi", timestamp),
                "facilities": self.get_geojson("facilities", timestamp),
                "thermal": self.get_geojson("thermal", timestamp),
                "demand": self.get_geojson("demand", timestamp),
            }

        raise ValueError(
            f"Unknown layer '{layer}'. Available: 'aoi', 'facilities', 'thermal', 'demand', 'all'"
        )


def load_locked_scenario(data_dir: Path | str = DEFAULT_DATA_DIR) -> ScenarioBundle:
    """Factory helper to load and return the locked ScenarioBundle."""
    return ScenarioBundle(data_dir=data_dir)
