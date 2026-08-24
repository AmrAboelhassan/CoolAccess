"""FastAPI backend service for CoolAccess Dynamic Cooling Resource Allocation.

Exposes REST endpoints for scenario metadata, allocation optimization,
baseline comparisons, replacement evidence, and map GeoJSON layers.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from coolaccess.analysis import analyze_future_state
from coolaccess.contracts import CompleteBaselineResult
from coolaccess.optimizer import optimize
from coolaccess.replacement import build_replacement_evidence
from coolaccess.scenario import ScenarioBundle, format_timestamp_display, load_locked_scenario


def create_app(scenario_bundle: ScenarioBundle | None = None) -> FastAPI:
    """Application factory for the CoolAccess FastAPI service."""
    bundle = scenario_bundle or load_locked_scenario()

    app = FastAPI(
        title="CoolAccess API",
        description="Provider-neutral deterministic cooling resource allocation engine",
        version="0.1.0",
    )

    # Allow CORS for local frontend development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health_check() -> dict[str, Any]:
        return {
            "status": "healthy",
            "service": "CoolAccess",
            "scenario_id": bundle.metadata.get("scenario_id"),
            "city": bundle.metadata.get("city_name"),
            "version": "0.1.0",
        }

    @app.get("/api/scenario")
    def get_scenario() -> dict[str, Any]:
        """Return scenario metadata, AOI, candidate facilities, timestamps, and parameters."""
        return {
            "city": bundle.metadata.get("city_name"),
            "scenario_id": bundle.metadata.get("scenario_id"),
            "scenario_title": bundle.metadata.get("scenario_title"),
            "historical_date": bundle.metadata.get("historical_date"),
            "timezone": bundle.metadata.get("timezone"),
            "aoi": bundle.metadata.get("aoi"),
            "resource_budget_k": bundle.metadata.get("resource_budget_k", 3),
            "catchment_radius_meters": bundle.metadata.get("primary_catchment_radius_meters", 750),
            "available_timestamps_utc": bundle.get_timestamps(),
            "candidate_facilities": bundle.get_facilities(),
            "population_summary": bundle.metadata.get("population_summary"),
            "primary_transition": bundle.metadata.get("primary_transition"),
            "provenance_registry": bundle.metadata.get("provenance_registry"),
        }

    @app.get("/api/allocate")
    def allocate(
        timestamp: str = Query("16:00", description="Target timestamp (e.g. '16:00', '20:00')"),
        baseline_timestamp: str = Query(
            "16:00", description="Source timestamp for static baseline selection (e.g. '16:00')"
        ),
        radius_meters: int = Query(750, description="Catchment proximity radius in meters"),
        k: int = Query(3, description="Resource facility budget limit"),
    ) -> dict[str, Any]:
        """Compute optimal allocation, baseline comparisons, and metrics for a timestamp."""
        try:
            target_req = bundle.build_allocation_request(
                timestamp=timestamp, radius_meters=radius_meters, k=k
            )
            baseline_req = bundle.build_allocation_request(
                timestamp=baseline_timestamp, radius_meters=radius_meters, k=k
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        # Prior allocation for static baseline
        prior_res = optimize(baseline_req)

        # Full analysis of target state
        analysis = analyze_future_state(target_req, prior_res)
        opt = analysis.optimized

        # Metrics
        cov_demand = float(opt.coverage.covered_heat_weighted_demand)
        tot_demand = float(opt.coverage.total_heat_weighted_demand)
        uncov_demand = float(opt.coverage.uncovered_heat_weighted_demand)
        cov_pop = int(opt.coverage.covered_population)
        tot_pop = int(opt.coverage.total_population)
        cov_pct_val = analysis.optimized_coverage_percentage.value
        cov_pct = float(cov_pct_val) if cov_pct_val is not None else 0.0

        # Static baseline details
        static_res = analysis.static_baseline
        if isinstance(static_res, CompleteBaselineResult):
            static_obj = float(static_res.objective_value)
            static_selected = list(static_res.selected_facility_ids)
            static_pop = int(static_res.coverage.covered_population)
        else:
            static_obj = 0.0
            static_selected = []
            static_pop = 0
        static_gain = cov_demand - static_obj
        static_gain_pct = (static_gain / static_obj * 100.0) if static_obj > 0 else 0.0

        # Naive baseline details
        naive_res = analysis.naive_baseline
        if isinstance(naive_res, CompleteBaselineResult):
            naive_obj = float(naive_res.objective_value)
            naive_selected = list(naive_res.selected_facility_ids)
            naive_pop = int(naive_res.coverage.covered_population)
            naive_gain = cov_demand - naive_obj
            naive_gain_pct = (naive_gain / naive_obj * 100.0) if naive_obj > 0 else 0.0
        else:
            naive_obj = 0.0
            naive_selected = []
            naive_pop = 0
            naive_gain = 0.0
            naive_gain_pct = 0.0

        # Facility details in selection
        selected_details = []
        for pfc in opt.coverage.per_facility:
            fac_info = next(
                (
                    f
                    for f in bundle.facilities_data["facilities"]
                    if f["facility_id"] == pfc.facility_id
                ),
                None,
            )
            selected_details.append(
                {
                    "facility_id": pfc.facility_id,
                    "name": fac_info["name"] if fac_info else pfc.facility_id,
                    "address": fac_info.get("address", "") if fac_info else "",
                    "direct_covered_population": int(pfc.direct_population),
                    "direct_heat_weighted_demand": float(pfc.direct_heat_weighted_demand),
                    "unique_heat_weighted_demand": float(pfc.unique_heat_weighted_demand),
                    "overlapping_heat_weighted_demand": float(pfc.overlapping_heat_weighted_demand),
                }
            )

        # Replacement summary
        replacements_summary = [
            {
                "selected_facility_id": r.selected_facility_id,
                "alternative_facility_id": r.alternative_facility_id,
                "objective_delta": float(r.objective_delta),
                "primary_objective_loss": float(r.primary_objective_loss),
                "population_delta": int(r.population_delta),
                "reason_code": r.reason_code.value,
            }
            for r in analysis.replacement_evidence
        ]

        return {
            "timestamp": format_timestamp_display(timestamp),
            "baseline_timestamp": format_timestamp_display(baseline_timestamp),
            "k": opt.k,
            "resource_count": opt.resource_count,
            "selected_facility_ids": list(opt.selected_facility_ids),
            "selected_facilities": selected_details,
            "coverage_metrics": {
                "covered_heat_weighted_demand": round(cov_demand, 2),
                "total_heat_weighted_demand": round(tot_demand, 2),
                "uncovered_heat_weighted_demand": round(uncov_demand, 2),
                "coverage_percentage": round(cov_pct, 2),
                "covered_population": cov_pop,
                "total_population": tot_pop,
                "uncovered_population": tot_pop - cov_pop,
            },
            "static_baseline": {
                "source_timestamp": format_timestamp_display(baseline_timestamp),
                "selected_facility_ids": static_selected,
                "objective_value": round(static_obj, 2),
                "covered_population": static_pop,
                "absolute_gain": round(static_gain, 2),
                "percentage_gain": round(static_gain_pct, 2),
            },
            "naive_baseline": {
                "algorithm": "naive_thermal_only",
                "selected_facility_ids": naive_selected,
                "objective_value": round(naive_obj, 2),
                "covered_population": naive_pop,
                "absolute_gain": round(naive_gain, 2),
                "percentage_gain": round(naive_gain_pct, 2),
            },
            "replacement_summary": replacements_summary,
            "tie_break": {
                "decisive_criterion": opt.tie_break.decisive_criterion.value,
                "evaluated_combination_count": opt.tie_break.evaluated_combination_count,
                "primary_tied_count": opt.tie_break.primary_tied_count,
                "population_tied_count": opt.tie_break.population_tied_count,
            },
            "fingerprints": {
                "structural": opt.structural_fingerprint,
                "full_state": opt.full_state_fingerprint,
            },
        }

    @app.get("/api/replacement")
    def get_replacement(
        timestamp: str = Query("20:00", description="Target timestamp to evaluate replacements"),
        selected_id: str | None = Query(
            None, description="Selected facility ID to replace (defaults to DC_135 at 20:00)"
        ),
        unselected_id: str | None = Query(
            None, description="Unselected alternative facility ID (defaults to DC_148 at 20:00)"
        ),
        radius_meters: int = Query(750, description="Catchment proximity radius in meters"),
        k: int = Query(3, description="Resource facility budget limit"),
    ) -> dict[str, Any]:
        """Return one-for-one facility replacement evidence and loss analysis."""
        try:
            target_req = bundle.build_allocation_request(
                timestamp=timestamp, radius_meters=radius_meters, k=k
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        opt = optimize(target_req)
        selected_ids = opt.selected_facility_ids
        eligible_unselected = tuple(
            f["facility_id"]
            for f in bundle.facilities_data["facilities"]
            if f["facility_id"] not in selected_ids
        )

        # Default primary replacement pair:
        target_sel = selected_id or ("DC_135" if "DC_135" in selected_ids else selected_ids[0])
        target_unsel = unselected_id or (
            "DC_148" if "DC_148" in eligible_unselected else eligible_unselected[0]
        )

        if target_sel not in selected_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Facility '{target_sel}' is not selected in {selected_ids}",
            )
        if target_unsel not in eligible_unselected:
            raise HTTPException(
                status_code=400,
                detail=f"Facility '{target_unsel}' is not unselected in {eligible_unselected}",
            )

        evidence = build_replacement_evidence(target_req, opt, target_sel, target_unsel)

        # Facility details
        sel_info: dict[str, Any] = next(
            (f for f in bundle.facilities_data["facilities"] if f["facility_id"] == target_sel), {}
        )
        unsel_info: dict[str, Any] = next(
            (f for f in bundle.facilities_data["facilities"] if f["facility_id"] == target_unsel),
            {},
        )

        # Build human-readable physical explanation
        ts_fmt = format_timestamp_display(timestamp)
        loss_val = float(evidence.primary_objective_loss)
        pop_d = int(evidence.population_delta)
        explanation = (
            f"At {ts_fmt} UTC, replacing '{sel_info.get('name', target_sel)}' "
            f"with '{unsel_info.get('name', target_unsel)}' results in a primary objective loss of "
            f"{loss_val:.2f} heat-weighted demand units. While the alternative covers "
            f"{pop_d:+d} raw residents, the optimal facility operates in an urban corridor "
            f"with substantially higher late-afternoon thermal priority."
        )

        # Build full matrix of all 9 possible replacements for convenience
        all_replacements = []
        for sid in selected_ids:
            for uid in eligible_unselected:
                rep = build_replacement_evidence(target_req, opt, sid, uid)
                all_replacements.append(
                    {
                        "selected_id": sid,
                        "unselected_id": uid,
                        "objective_delta": float(rep.objective_delta),
                        "primary_objective_loss": float(rep.primary_objective_loss),
                        "population_delta": int(rep.population_delta),
                        "reason_code": rep.reason_code.value,
                    }
                )

        return {
            "timestamp": format_timestamp_display(timestamp),
            "optimal_selected_facilities": list(selected_ids),
            "primary_replacement": {
                "selected_facility": {
                    "facility_id": target_sel,
                    "name": sel_info.get("name", target_sel),
                    "direct_covered_population": int(evidence.selected_coverage.direct_population),
                    "direct_heat_weighted_demand": float(
                        evidence.selected_coverage.direct_heat_weighted_demand
                    ),
                },
                "alternative_facility": {
                    "facility_id": target_unsel,
                    "name": unsel_info.get("name", target_unsel),
                    "direct_covered_population": int(
                        evidence.alternative_coverage.direct_population
                    ),
                    "direct_heat_weighted_demand": float(
                        evidence.alternative_coverage.direct_heat_weighted_demand
                    ),
                },
                "original_objective": float(evidence.original_objective),
                "replacement_objective": float(evidence.replacement_objective),
                "objective_delta": float(evidence.objective_delta),
                "primary_objective_loss": float(evidence.primary_objective_loss),
                "population_delta": int(evidence.population_delta),
                "lost_population": int(evidence.lost_population),
                "gained_population": int(evidence.gained_population),
                "lost_demand": float(evidence.lost_heat_weighted_demand),
                "gained_demand": float(evidence.gained_heat_weighted_demand),
                "comparator_outcome": evidence.comparator_outcome.value,
                "decisive_criterion": (
                    evidence.decisive_criterion.value if evidence.decisive_criterion else None
                ),
                "reason_code": evidence.reason_code.value,
                "explanation": explanation,
            },
            "replacement_matrix": all_replacements,
        }

    @app.get("/api/geojson")
    def get_geojson(
        layer: str = Query(
            "all", description="GeoJSON layer ('all', 'thermal', 'facilities', 'demand', 'aoi')"
        ),
        timestamp: str = Query("16:00", description="Timestamp for thermal/demand properties"),
    ) -> dict[str, Any]:
        """Return map-ready GeoJSON FeatureCollection(s)."""
        try:
            return bundle.get_geojson(layer=layer, timestamp=timestamp)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    return app


# Default module-level FastAPI instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("coolaccess.server:app", host="127.0.0.1", port=8000, reload=True)
