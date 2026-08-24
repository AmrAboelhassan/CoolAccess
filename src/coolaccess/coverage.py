"""Exact deterministic union-coverage calculations."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from decimal import Decimal

from coolaccess.contracts import (
    AllocationRequest,
    CoverageSummary,
    EligibilityStatus,
    FacilityCoverage,
    PopulationCell,
)
from coolaccess.demand import exact_sum
from coolaccess.errors import InternalConsistencyError, InvalidSelectionError


def _canonical_selection(
    request: AllocationRequest,
    selected_facility_ids: Iterable[str],
) -> tuple[str, ...]:
    selected = tuple(selected_facility_ids)
    if len(selected) != len(set(selected)):
        raise InvalidSelectionError(
            "selected facility IDs must be unique",
            details={"selected_facility_ids": tuple(sorted(selected))},
        )
    if len(selected) > request.k:
        raise InvalidSelectionError(
            "selected facility count exceeds the configured resource budget",
            details={"k": request.k, "selected_count": len(selected)},
        )

    facilities = {facility.facility_id: facility for facility in request.facilities}
    unknown = tuple(sorted(set(selected) - facilities.keys()))
    if unknown:
        raise InvalidSelectionError(
            "selection contains unknown facilities",
            details={"unknown_facility_ids": unknown},
        )
    ineligible = tuple(
        sorted(
            facility_id
            for facility_id in selected
            if facilities[facility_id].eligibility_status is not EligibilityStatus.ELIGIBLE
        )
    )
    if ineligible:
        raise InvalidSelectionError(
            "selection contains ineligible facilities",
            details={"ineligible_facility_ids": ineligible},
        )
    return tuple(sorted(selected))


def _cell_demand(cell: PopulationCell) -> Decimal:
    demand = cell.heat_weighted_demand
    if demand is None:
        raise InternalConsistencyError(
            "validated demand cell has no heat-weighted demand",
            details={"cell_id": cell.cell_id},
        )
    return demand


def _totals_for_cells(
    cells: dict[str, PopulationCell],
    cell_ids: Iterable[str],
) -> tuple[Decimal, Decimal]:
    materialized = tuple(cell_ids)
    return (
        exact_sum(_cell_demand(cells[cell_id]) for cell_id in materialized),
        exact_sum(cells[cell_id].population for cell_id in materialized),
    )


def evaluate_coverage(
    request: AllocationRequest,
    selected_facility_ids: Iterable[str],
) -> CoverageSummary:
    """Evaluate exact union coverage for a validated facility selection.

    Missing or explicitly false relationships both mean inaccessible. A demand
    cell contributes to union totals at most once, irrespective of how many
    selected facilities cover it.
    """

    selected = _canonical_selection(request, selected_facility_ids)
    cells = {cell.cell_id: cell for cell in request.demand_cells}
    direct_cells: dict[str, set[str]] = {facility_id: set() for facility_id in selected}
    for relationship in request.accessibility_relationships:
        if relationship.is_accessible and relationship.facility_id in direct_cells:
            direct_cells[relationship.facility_id].add(relationship.cell_id)

    coverage_counts: Counter[str] = Counter()
    for facility_cells in direct_cells.values():
        coverage_counts.update(facility_cells)

    covered_cell_ids = tuple(sorted(coverage_counts))
    uncovered_cell_ids = tuple(sorted(set(cells) - set(covered_cell_ids)))
    multi_covered_cell_ids = tuple(
        sorted(cell_id for cell_id, count in coverage_counts.items() if count > 1)
    )

    total_demand, total_population = _totals_for_cells(cells, cells)
    covered_demand, covered_population = _totals_for_cells(cells, covered_cell_ids)
    uncovered_demand, uncovered_population = _totals_for_cells(cells, uncovered_cell_ids)
    overlap_demand, overlap_population = _totals_for_cells(cells, multi_covered_cell_ids)

    redundant_demand_values: list[Decimal] = []
    redundant_population_values: list[Decimal] = []
    for cell_id, count in sorted(coverage_counts.items()):
        for _ in range(count - 1):
            redundant_demand_values.append(_cell_demand(cells[cell_id]))
            redundant_population_values.append(cells[cell_id].population)

    per_facility: list[FacilityCoverage] = []
    for facility_id in selected:
        direct_ids = tuple(sorted(direct_cells[facility_id]))
        unique_ids = tuple(cell_id for cell_id in direct_ids if coverage_counts[cell_id] == 1)
        overlapping_ids = tuple(cell_id for cell_id in direct_ids if coverage_counts[cell_id] > 1)
        direct_demand, direct_population = _totals_for_cells(cells, direct_ids)
        unique_demand, unique_population = _totals_for_cells(cells, unique_ids)
        overlapping_demand, overlapping_population = _totals_for_cells(cells, overlapping_ids)
        per_facility.append(
            FacilityCoverage(
                facility_id=facility_id,
                direct_cell_ids=direct_ids,
                direct_heat_weighted_demand=direct_demand,
                direct_population=direct_population,
                unique_cell_ids=unique_ids,
                unique_heat_weighted_demand=unique_demand,
                unique_population=unique_population,
                overlapping_cell_ids=overlapping_ids,
                overlapping_heat_weighted_demand=overlapping_demand,
                overlapping_population=overlapping_population,
            )
        )

    if exact_sum((covered_demand, uncovered_demand)) != total_demand:
        raise InternalConsistencyError("covered and uncovered demand do not reconcile")
    if exact_sum((covered_population, uncovered_population)) != total_population:
        raise InternalConsistencyError("covered and uncovered population do not reconcile")

    return CoverageSummary(
        total_heat_weighted_demand=total_demand,
        covered_heat_weighted_demand=covered_demand,
        uncovered_heat_weighted_demand=uncovered_demand,
        total_population=total_population,
        covered_population=covered_population,
        uncovered_population=uncovered_population,
        covered_cell_ids=covered_cell_ids,
        uncovered_cell_ids=uncovered_cell_ids,
        multi_covered_cell_ids=multi_covered_cell_ids,
        overlap_union_heat_weighted_demand=overlap_demand,
        overlap_union_population=overlap_population,
        redundant_heat_weighted_demand=exact_sum(redundant_demand_values),
        redundant_population=exact_sum(redundant_population_values),
        per_facility=tuple(per_facility),
    )
