"""Deterministic Offline CoolAccess Expansion Allocation Runner for Washington DC (July 16, 2024).

Executes the complete deterministic CoolAccess allocation pipeline offline against the 5 real
diurnal FortyGuard 100m snapshots acquired for July 16, 2024.

Reuses the invariant layers from locked_dc_scenario:
- 6 candidate municipal public facilities (OCTO DC GIS)
- 887 Census blocks from 2020 U.S. Census Bureau Table P1 (100,389 residents)
- Geodesic accessibility catchments at 500m, 750m, and 1000m
- Exact Decimal arithmetic, combinatorial maximum-coverage optimizer (K=3, 42 subsets)
- Robust Fixed Anchors (p1=32.022°C, p99=37.699°C)
- Static and Naive Baseline evaluators
- Replacement loss analysis
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

# Ensure workspace src is importable
_WORKSPACE_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
_SRC_DIR: Final[Path] = _WORKSPACE_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from coolaccess.baselines import (  # noqa: E402
    evaluate_naive_baseline,
    evaluate_static_baseline,
)
from coolaccess.contracts import (  # noqa: E402
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
from coolaccess.demand import canonical_decimal  # noqa: E402
from coolaccess.optimizer import optimize  # noqa: E402
from coolaccess.replacement import build_replacement_evidence  # noqa: E402
from coolaccess.scenario import (  # noqa: E402
    ScenarioBundle,
    haversine_meters,
    sanitize_timestamp_key,
)

LOCKED_DATA_DIR: Final[Path] = _WORKSPACE_ROOT / "data" / "locked_dc_scenario"
EXPANSION_DATA_DIR: Final[Path] = _WORKSPACE_ROOT / "data" / "expansion_20240716"
EXPANSION_THERMAL_PATH: Final[Path] = EXPANSION_DATA_DIR / "thermal_snapshots.json"


def compute_spearman_correlation(
    temps_a: dict[str, float], temps_b: dict[str, float]
) -> tuple[float, int]:
    """Compute Spearman rank correlation between two tile temperature dictionaries."""
    common_keys = sorted(set(temps_a.keys()) & set(temps_b.keys()))
    n = len(common_keys)
    if n < 2:
        return 0.0, n

    vals_a = [temps_a[k] for k in common_keys]
    vals_b = [temps_b[k] for k in common_keys]

    def _rank(vals: list[float]) -> list[float]:
        sorted_indices = sorted(range(len(vals)), key=lambda i: vals[i])
        ranks = [0.0] * len(vals)
        for rank, idx in enumerate(sorted_indices, start=1):
            ranks[idx] = float(rank)
        return ranks

    ranks_a = _rank(vals_a)
    ranks_b = _rank(vals_b)

    d_sq_sum = sum((ranks_a[i] - ranks_b[i]) ** 2 for i in range(n))
    rho = 1.0 - (6.0 * d_sq_sum) / (n * (n**2 - 1))
    return round(rho, 4), n


class ExpansionScenarioLoader:
    """Builds AllocationRequests using July 16 thermal snapshots and locked invariant layers."""

    def __init__(self) -> None:
        with (LOCKED_DATA_DIR / "facilities.json").open("r", encoding="utf-8") as fp:
            self.facilities_data = json.load(fp)
        with (LOCKED_DATA_DIR / "census_blocks.json").open("r", encoding="utf-8") as fp:
            self.census_data = json.load(fp)
        with (LOCKED_DATA_DIR / "catchments.json").open("r", encoding="utf-8") as fp:
            self.catchments_data = json.load(fp)
        with EXPANSION_THERMAL_PATH.open("r", encoding="utf-8") as fp:
            self.thermal_data = json.load(fp)

        # Reusing the canonical robust anchors from July 15 for cross-day calibration consistency
        with (LOCKED_DATA_DIR / "thermal_snapshots.json").open("r", encoding="utf-8") as fp:
            j15_thermal = json.load(fp)
        anchors = j15_thermal.get("normalization_anchors", {})
        self.p1_lower = float(anchors.get("p1_lower_anchor_c", 32.022))
        self.p99_upper = float(anchors.get("p99_upper_anchor_c", 37.699))

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

        now_utc = datetime(2026, 8, 28, 12, 0, 0, tzinfo=UTC)
        self.registry = (
            ProvenanceRecord(
                provenance_id="prov_census_2020_p1",
                scope=ProvenanceScope.INVARIANT,
                source_kind=SourceKind.POPULATION,
                source_name="U.S. Census Bureau 2020 Decennial Census Table P1",
                dataset_title="2020 Census Blocks for District of Columbia",
                license_reference="Public Domain (U.S. Government Work)",
                source_vintage="2020",
                data_state=DataState.STATIC,
                retrieved_at=now_utc,
            ),
            ProvenanceRecord(
                provenance_id="prov_fortyguard_tcm_expansion_20240716",
                scope=ProvenanceScope.THERMAL_STATE,
                source_kind=SourceKind.THERMAL_PRIORITY,
                source_name="FortyGuard Temperature API (tcm, 100m)",
                dataset_title="FortyGuard Urban Thermal Snapshots 2024-07-16",
                license_reference="FortyGuard Commercial Hackathon API License",
                source_vintage="2024-07-16",
                data_state=DataState.PREPARED,
                retrieved_at=now_utc,
            ),
            ProvenanceRecord(
                provenance_id="prov_dc_facilities_octo",
                scope=ProvenanceScope.INVARIANT,
                source_kind=SourceKind.FACILITY,
                source_name="Open Data DC / OCTO Public Facilities Directory",
                dataset_title="DC GIS Cooling Centers",
                license_reference="Creative Commons CC0 1.0 Universal",
                source_vintage="2024",
                data_state=DataState.STATIC,
                retrieved_at=now_utc,
            ),
            ProvenanceRecord(
                provenance_id="prov_coolaccess_config_v1",
                scope=ProvenanceScope.INVARIANT,
                source_kind=SourceKind.CONFIGURATION,
                source_name="CoolAccess Deterministic Engine",
                license_reference="Proprietary",
                source_vintage="2026",
                data_state=DataState.STATIC,
                retrieved_at=now_utc,
            ),
        )

    def normalize_temperature(self, temp_c: float) -> Decimal:
        norm = (temp_c - self.p1_lower) / (self.p99_upper - self.p1_lower)
        clamped = max(0.0, min(1.0, norm))
        return canonical_decimal(Decimal(str(round(clamped, 6))))

    def build_request(
        self, timestamp: str = "16:00", radius_meters: int = 750, k: int = 3
    ) -> AllocationRequest:
        ts_key = sanitize_timestamp_key(timestamp)
        temps_map = self.thermal_data["temperatures_by_timestamp"].get(ts_key)
        if temps_map is None:
            available_keys = list(self.thermal_data["temperatures_by_timestamp"].keys())
            raise ValueError(f"Unknown timestamp '{timestamp}'. Available: {available_keys}")

        hour_int = int(ts_key[:2])
        valid_at_dt = datetime(2024, 7, 16, hour_int, 0, 0, tzinfo=UTC)

        cells = []
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
                    thermal_state_provenance_refs=("prov_fortyguard_tcm_expansion_20240716",),
                )
            )

        edges = []
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
            scenario_id=f"DC_CoolAccess_Expansion_r{radius_meters}m",
            state_id=f"state_dc_20240716_{ts_key}",
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
            thermal_state_provenance_refs=("prov_fortyguard_tcm_expansion_20240716",),
            provenance_registry=self.registry,
        )


def run_expansion_allocation() -> dict[str, Any]:
    print("=" * 80)
    print("COOLACCESS — SECOND-DAY OFFLINE BENCHMARK EVALUATION (DC JULY 16, 2024)")
    print("=" * 80)

    loader = ExpansionScenarioLoader()
    timestamps = ["14:00", "16:00", "18:00", "20:00", "22:00"]

    # Thermal summary
    print("\n--- 1. THERMAL SNAPSHOT METRICS (JULY 16, 2024) ---")
    hdr_therm = (
        f"{'Timestamp':<12} {'Tile Count':<12} {'Min (°C)':<10} "
        f"{'Mean (°C)':<10} {'Max (°C)':<10} {'Spread (°C)'}"
    )
    print(hdr_therm)
    print("-" * 68)
    for ts in timestamps:
        ts_key = ts.replace(":", "")
        temps = list(loader.thermal_data["temperatures_by_timestamp"][ts_key].values())
        min_t, max_t = min(temps), max(temps)
        mean_t = sum(temps) / len(temps)
        print(
            f"{ts + ' UTC':<12} {len(temps):<12} {min_t:<10.3f} "
            f"{mean_t:<10.3f} {max_t:<10.3f} {max_t - min_t:<10.3f}"
        )

    # Spatial correlation (16:00 vs 20:00)
    t16 = loader.thermal_data["temperatures_by_timestamp"]["1600"]
    t20 = loader.thermal_data["temperatures_by_timestamp"]["2000"]
    rs_val, n_tiles = compute_spearman_correlation(t16, t20)
    print(
        f"\nSpearman Correlation (16:00 vs 20:00 UTC July 16, N={n_tiles}): "
        f"r_s = {rs_val:.4f}"
    )

    # Primary Evaluation: 750m, K=3
    print("\n--- 2. PRIMARY CANONICAL ALLOCATION RESULTS (K=3, Radius=750m) ---")
    hdr = (
        f"{'Timestamp':<10} {'Optimal Facilities':<32} {'Covered Demand':<16} "
        f"{'Demand %':<10} {'Covered Pop':<12} {'Pop %':<8} {'Ties'}"
    )
    print(hdr)
    print("-" * len(hdr))

    results_750: dict[str, Any] = {}
    alloc_results_750: dict[str, Any] = {}
    for ts in timestamps:
        req = loader.build_request(timestamp=ts, radius_meters=750, k=3)
        res = optimize(req)
        alloc_results_750[ts] = res

        total_demand = sum(c.heat_weighted_demand for c in req.demand_cells)
        total_pop = sum(c.population for c in req.demand_cells)
        dem_pct = (res.objective_value / total_demand * 100) if total_demand else Decimal("0")
        pop_pct = (
            (res.coverage.covered_population / total_pop * 100) if total_pop else Decimal("0")
        )

        results_750[ts] = {
            "selected_facilities": list(res.selected_facility_ids),
            "objective_value": float(res.objective_value),
            "demand_pct": float(round(dem_pct, 2)),
            "covered_population": int(res.coverage.covered_population),
            "pop_pct": float(round(pop_pct, 2)),
            "tie_break_criterion": res.tie_break.decisive_criterion.value,
        }

        fac_str = ", ".join(res.selected_facility_ids)
        crit_str = res.tie_break.decisive_criterion.value
        print(
            f"{ts + ' UTC':<10} {fac_str:<32} {float(res.objective_value):<16.2f} "
            f"{float(dem_pct):<10.2f}% {int(res.coverage.covered_population):<12d} "
            f"{float(pop_pct):<8.2f}% {crit_str}"
        )

    # Static baseline comparison (16:00 midday vs 20:00 late afternoon)
    req_20 = loader.build_request(timestamp="20:00", radius_meters=750, k=3)
    res_16 = alloc_results_750["16:00"]
    res_20 = alloc_results_750["20:00"]
    static_baseline_res = evaluate_static_baseline(req_20, res_16)
    naive_baseline_res = evaluate_naive_baseline(req_20)

    static_obj = float(static_baseline_res.objective_value)
    dyn_obj = float(res_20.objective_value)
    static_gain = dyn_obj - static_obj
    static_gain_pct = (static_gain / static_obj * 100) if static_obj else 0.0

    naive_obj = (
        float(naive_baseline_res.objective_value)
        if hasattr(naive_baseline_res, "objective_value")
        else 0.0
    )
    naive_gain = dyn_obj - naive_obj
    naive_gain_pct = (naive_gain / naive_obj * 100) if naive_obj else 0.0

    print("\n--- 3. BASELINE COMPARISON AT 20:00 UTC (Radius=750m) ---")
    pop_dyn = int(res_20.coverage.covered_population)
    print(
        f"Dynamic Optimal Selection (20:00): {list(res_20.selected_facility_ids)} -> "
        f"Objective = {dyn_obj:.2f} (Pop = {pop_dyn})"
    )
    pop_static = int(static_baseline_res.coverage.covered_population)
    print(
        f"Static Baseline (reusing 16:00 set {list(res_16.selected_facility_ids)}): "
        f"Objective = {static_obj:.2f} (Pop = {pop_static})"
    )
    print(f"  * Gain over Static Baseline: +{static_gain:.2f} (+{static_gain_pct:.2f}%)")
    naive_facs = (
        list(naive_baseline_res.selected_facility_ids)
        if hasattr(naive_baseline_res, "selected_facility_ids")
        else "N/A"
    )
    print(
        f"Naive Thermal Baseline: {naive_facs} -> Objective = {naive_obj:.2f}"
    )
    print(f"  * Gain over Naive Thermal Baseline: +{naive_gain:.2f} (+{naive_gain_pct:.2f}%)")

    # One-for-One Replacement Evidence at 20:00
    selected_set = set(res_20.selected_facility_ids)
    all_fac_ids = [
        f.facility_id
        for f in req_20.facilities
        if f.eligibility_status is EligibilityStatus.ELIGIBLE
    ]
    unselected_ids = [fid for fid in all_fac_ids if fid not in selected_set]

    replacements = [
        build_replacement_evidence(req_20, res_20, sel_id, unsel_id)
        for sel_id in res_20.selected_facility_ids
        for unsel_id in unselected_ids
    ]
    print("\n--- 4. ONE-FOR-ONE REPLACEMENT LOSS EVIDENCE (20:00 UTC @ 750m) ---")
    hdr_repl = (
        f"{'Replaced Facility':<18} {'Alternative Facility':<22} "
        f"{'Objective Delta':<18} {'Pop Delta':<12} {'Outcome'}"
    )
    print(hdr_repl)
    print("-" * 80)
    for r in replacements:
        print(
            f"{r.selected_facility_id:<18} {r.alternative_facility_id:<22} "
            f"{float(r.objective_delta):<18.2f} {int(r.population_delta):<+12d} "
            f"{r.comparator_outcome.value}"
        )

    # Cross-day comparison with July 15
    print("\n--- 5. CROSS-DAY COMPARISON (JULY 15 vs JULY 16, 2024 @ 750m) ---")
    j15_loader = ScenarioBundle()
    j15_16 = optimize(j15_loader.build_allocation_request("16:00", radius_meters=750, k=3))
    j15_20 = optimize(j15_loader.build_allocation_request("20:00", radius_meters=750, k=3))

    j15_selection_16 = list(j15_16.selected_facility_ids)
    j15_selection_20 = list(j15_20.selected_facility_ids)
    j16_selection_16 = list(res_16.selected_facility_ids)
    j16_selection_20 = list(res_20.selected_facility_ids)

    print(
        f"July 15 16:00 UTC: {j15_selection_16} -> 20:00 UTC: {j15_selection_20} "
        "(Replaced DC_148 with DC_135)"
    )
    print(f"July 16 16:00 UTC: {j16_selection_16} -> 20:00 UTC: {j16_selection_20}")

    if j15_selection_16 == j16_selection_16 and j15_selection_20 == j16_selection_20:
        decision_class = "DECISION STABLE UNDER SECOND-DAY THERMAL INPUT"
    elif j15_selection_16 == j16_selection_16 and j15_selection_20 != j16_selection_20:
        decision_class = "PARTIAL CROSS-DAY DECISION CHANGE"
    else:
        decision_class = "DECISION CHANGED UNDER SECOND-DAY THERMAL INPUT"

    print(f"Decision Classification: {decision_class}")

    # Secondary Sensitivity Analysis (500m & 1000m)
    print("\n--- 6. SECONDARY SENSITIVITY ANALYSIS (500m & 1000m) ---")
    sensitivity_results = {}
    for r in [500, 1000]:
        print(f"\nRadius = {r}m:")
        sensitivity_results[r] = {}
        for ts in timestamps:
            req_s = loader.build_request(timestamp=ts, radius_meters=r, k=3)
            res_s = optimize(req_s)
            sensitivity_results[r][ts] = {
                "facilities": list(res_s.selected_facility_ids),
                "objective": float(res_s.objective_value),
                "population": int(res_s.coverage.covered_population),
            }
            pop_s = int(res_s.coverage.covered_population)
            print(
                f"  * {ts} UTC: {list(res_s.selected_facility_ids)} | "
                f"Objective = {float(res_s.objective_value):.2f} | Pop = {pop_s}"
            )

    return {
        "benchmark_date": "2024-07-16",
        "primary_750m_results": results_750,
        "static_baseline_comparison": {
            "dynamic_objective": dyn_obj,
            "static_objective": static_obj,
            "gain": static_gain,
            "gain_pct": static_gain_pct,
        },
        "naive_baseline_comparison": {
            "naive_objective": naive_obj,
            "gain": naive_gain,
            "gain_pct": naive_gain_pct,
        },
        "cross_day_classification": decision_class,
        "spearman_rs_16_vs_20": rs_val,
        "sensitivity_results": sensitivity_results,
    }


if __name__ == "__main__":
    run_expansion_allocation()
