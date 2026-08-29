"""Run offline deterministic allocation robustness evidence for CoolAccess.

Covers:
1. Population-Only vs. FortyGuard Thermal-Weighted Ablation (16:00 and 20:00 UTC)
2. Geographic Catchment Radius Sensitivity (500m to 1000m, K=3)
3. Budget Constraint K Sensitivity (K=1 to 6, 750m)
4. Normalization Set Stability (Canonical P1/P99, Empirical P5/P95, Min/Max snapshot range)

Usage:
    python scripts/run_allocation_robustness_evidence.py
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from coolaccess.coverage import evaluate_coverage  # noqa: E402
from coolaccess.demand import canonical_decimal  # noqa: E402
from coolaccess.optimizer import optimize  # noqa: E402
from coolaccess.scenario import ScenarioBundle  # noqa: E402


def run_evidence() -> dict[str, Any]:
    bundle = ScenarioBundle()
    blocks_by_geoid = {b["geoid"]: b for b in bundle.census_data["blocks"]}

    print("=" * 80)
    print("COOLACCESS - OFFLINE ALLOCATION ROBUSTNESS EVIDENCE")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # 1. Population-Only vs. FortyGuard Thermal-Weighted Ablation
    # -------------------------------------------------------------------------
    print("\n--- 1. POPULATION-ONLY VS FORTYGUARD THERMAL ABLATION ---")
    ablation_results: dict[str, Any] = {}

    for ts in ["16:00", "20:00"]:
        req_can = bundle.build_allocation_request(timestamp=ts, radius_meters=750, k=3)
        res_can = optimize(req_can)

        pop_cells = [
            c.model_copy(
                update={
                    "thermal_priority": Decimal("1.0"),
                    "heat_weighted_demand": c.population,
                }
            )
            for c in req_can.demand_cells
        ]
        req_pop = req_can.model_copy(update={"demand_cells": tuple(pop_cells)})
        res_pop = optimize(req_pop)

        can_obj = float(res_can.coverage.covered_heat_weighted_demand)
        can_pop = int(res_can.coverage.covered_population)
        pop_obj = float(res_pop.coverage.covered_heat_weighted_demand)
        pop_pop = int(res_pop.coverage.covered_population)

        ablation_results[ts] = {
            "canonical_set": res_can.selected_facility_ids,
            "canonical_obj": can_obj,
            "canonical_pop": can_pop,
            "pop_only_set": res_pop.selected_facility_ids,
            "pop_only_obj": pop_obj,
            "pop_only_pop": pop_pop,
        }

        print(f"\nTimestamp: {ts} UTC")
        print(
            f"  Canonical (Thermal x Pop): Set={res_can.selected_facility_ids}, "
            f"Obj={can_obj:.2f}, Pop={can_pop}"
        )
        print(
            f"  Population-Only Ablation:  Set={res_pop.selected_facility_ids}, "
            f"Obj={pop_obj:.2f}, Pop={pop_pop}"
        )

    # -------------------------------------------------------------------------
    # 2. Geographic Catchment Radius Sensitivity
    # -------------------------------------------------------------------------
    print("\n--- 2. GEOGRAPHIC CATCHMENT RADIUS SENSITIVITY (K=3) ---")
    radii = [500, 600, 650, 700, 750, 800, 850, 900, 1000]
    radius_results: list[dict[str, Any]] = []

    header = (
        f"{'Radius':<8} {'16:00 Set':<25} {'20:00 Set':<25} {'Dyn Obj':<12} "
        f"{'Stat Obj':<12} {'Gain %':<10} {'Dyn Pop':<10} {'Stat Pop':<10} {'148->135?'}"
    )
    print(header)
    print("-" * 125)

    for r in radii:
        req_16 = bundle.build_allocation_request(timestamp="16:00", radius_meters=r, k=3)
        res_16 = optimize(req_16)
        req_20 = bundle.build_allocation_request(timestamp="20:00", radius_meters=r, k=3)
        res_20 = optimize(req_20)

        stat_cov = evaluate_coverage(req_20, res_16.selected_facility_ids)
        dyn_obj = res_20.coverage.covered_heat_weighted_demand
        stat_obj = stat_cov.covered_heat_weighted_demand
        gain_pct = (dyn_obj - stat_obj) / stat_obj * 100 if stat_obj > 0 else Decimal("0")

        dyn_pop = res_20.coverage.covered_population
        stat_pop = stat_cov.covered_population

        is_148_135 = (
            "DC_148" in res_16.selected_facility_ids
            and "DC_135" in res_20.selected_facility_ids
            and "DC_148" not in res_20.selected_facility_ids
        )

        s16 = ", ".join(res_16.selected_facility_ids)
        s20 = ", ".join(res_20.selected_facility_ids)
        row = (
            f"{r:<8} {s16:<25} {s20:<25} {float(dyn_obj):<12.2f} "
            f"{float(stat_obj):<12.2f} {float(gain_pct):<+9.2f}% "
            f"{int(dyn_pop):<10d} {int(stat_pop):<10d} {is_148_135!s:<10}"
        )
        print(row)

        radius_results.append(
            {
                "radius": r,
                "set_16": res_16.selected_facility_ids,
                "set_20": res_20.selected_facility_ids,
                "dyn_obj": float(dyn_obj),
                "stat_obj": float(stat_obj),
                "gain_pct": float(gain_pct),
                "is_148_135": is_148_135,
            }
        )

    # -------------------------------------------------------------------------
    # 3. Budget Constraint K Sensitivity
    # -------------------------------------------------------------------------
    print("\n--- 3. BUDGET CONSTRAINT K SENSITIVITY (750m) ---")
    k_results: list[dict[str, Any]] = []
    for k in range(1, 7):
        req_16 = bundle.build_allocation_request(timestamp="16:00", radius_meters=750, k=k)
        res_16 = optimize(req_16)
        req_20 = bundle.build_allocation_request(timestamp="20:00", radius_meters=750, k=k)
        res_20 = optimize(req_20)
        obj16 = float(res_16.coverage.covered_heat_weighted_demand)
        obj20 = float(res_20.coverage.covered_heat_weighted_demand)
        print(
            f"K={k}: 16:00 Set={res_16.selected_facility_ids} (Obj: {obj16:.2f}) | "
            f"20:00 Set={res_20.selected_facility_ids} (Obj: {obj20:.2f})"
        )
        k_results.append(
            {
                "k": k,
                "set_16": res_16.selected_facility_ids,
                "set_20": res_20.selected_facility_ids,
                "temporal_change": res_16.selected_facility_ids != res_20.selected_facility_ids,
            }
        )

    # -------------------------------------------------------------------------
    # 4. Normalization Set Stability
    # -------------------------------------------------------------------------
    print("\n--- 4. NORMALIZATION SET STABILITY ---")
    all_raw_temps = []
    for t_map in bundle.thermal_data["temperatures_by_timestamp"].values():
        all_raw_temps.extend(t_map.values())
    all_raw_temps_sorted = sorted(all_raw_temps)
    n_tiles = len(all_raw_temps_sorted)
    min_t = min(all_raw_temps_sorted)
    max_t = max(all_raw_temps_sorted)
    p5_t = all_raw_temps_sorted[int(0.05 * n_tiles)]
    p95_t = all_raw_temps_sorted[int(0.95 * n_tiles)]

    schemes = [
        ("Canonical P1/P99 Anchors", bundle.p1_lower, bundle.p99_upper),
        ("Empirical P5/P95 Anchors", p5_t, p95_t),
        ("Min/Max Snapshot Range", min_t, max_t),
    ]

    norm_results: list[dict[str, Any]] = []
    for name, low, high in schemes:
        diff = high - low

        def make_norm_fn(low_val: float, span_val: float) -> Any:
            def _fn(temp_val: float) -> Decimal:
                norm = (temp_val - low_val) / span_val
                clamped = max(0.0, min(1.0, norm))
                return canonical_decimal(Decimal(str(round(clamped, 6))))
            return _fn

        norm_fn = make_norm_fn(low, diff)

        # 16:00
        req_16_base = bundle.build_allocation_request(timestamp="16:00", radius_meters=750, k=3)
        cells_16 = []
        for c in req_16_base.demand_cells:
            b = blocks_by_geoid[c.cell_id]
            tile_id = str(b["matched_fortyguard_tile_id"])
            raw_t = bundle.thermal_data["temperatures_by_timestamp"]["1600"][tile_id]
            p = norm_fn(raw_t)
            cells_16.append(
                c.model_copy(
                    update={
                        "thermal_priority": p,
                        "heat_weighted_demand": canonical_decimal(c.population * p),
                    }
                )
            )
        res_16 = optimize(req_16_base.model_copy(update={"demand_cells": tuple(cells_16)}))

        # 20:00
        req_20_base = bundle.build_allocation_request(timestamp="20:00", radius_meters=750, k=3)
        cells_20 = []
        for c in req_20_base.demand_cells:
            b = blocks_by_geoid[c.cell_id]
            tile_id = str(b["matched_fortyguard_tile_id"])
            raw_t = bundle.thermal_data["temperatures_by_timestamp"]["2000"][tile_id]
            p = norm_fn(raw_t)
            cells_20.append(
                c.model_copy(
                    update={
                        "thermal_priority": p,
                        "heat_weighted_demand": canonical_decimal(c.population * p),
                    }
                )
            )
        req_20_custom = req_20_base.model_copy(update={"demand_cells": tuple(cells_20)})
        res_20 = optimize(req_20_custom)

        stat_cov = evaluate_coverage(req_20_custom, res_16.selected_facility_ids)
        d_cov = res_20.coverage.covered_heat_weighted_demand
        s_cov = stat_cov.covered_heat_weighted_demand
        gain_pct = (d_cov - s_cov) / s_cov * 100

        print(
            f"Scheme: {name:<26} -> 16:00={res_16.selected_facility_ids}, "
            f"20:00={res_20.selected_facility_ids}, Dynamic Gain={float(gain_pct):+.2f}%"
        )
        norm_results.append(
            {
                "name": name,
                "set_16": res_16.selected_facility_ids,
                "set_20": res_20.selected_facility_ids,
                "gain_pct": float(gain_pct),
            }
        )

    return {
        "ablation": ablation_results,
        "radius_results": radius_results,
        "k_results": k_results,
        "norm_results": norm_results,
    }


if __name__ == "__main__":
    run_evidence()
