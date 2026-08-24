"""Deterministic provider-neutral baseline algorithms.

Both baselines are deliberately small and auditable.  They consume the same
validated request as the optimizer and delegate all authoritative coverage
arithmetic to :func:`coolaccess.coverage.evaluate_coverage`.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from functools import cmp_to_key

from coolaccess.canonical import full_state_fingerprint, structural_fingerprint
from coolaccess.contracts import (
    AllocationRequest,
    AllocationResult,
    BaselineAlgorithm,
    BaselineResult,
    CompleteBaselineResult,
    EligibilityStatus,
    FacilityThermalScore,
    UnavailableBaselineResult,
)
from coolaccess.coverage import evaluate_coverage
from coolaccess.demand import exact_mean, exact_product, exact_sum
from coolaccess.errors import InvalidStaticSelectionError, StructuralMismatchError

_NO_ACCESSIBLE_CELLS = "NO_ACCESSIBLE_DEMAND_CELLS"
_INSUFFICIENT_SCOREABLE_FACILITIES = "INSUFFICIENT_SCOREABLE_FACILITIES"


def _eligible_facility_ids(request: AllocationRequest) -> tuple[str, ...]:
    return tuple(
        facility.facility_id
        for facility in request.facilities
        if facility.eligibility_status is EligibilityStatus.ELIGIBLE
    )


def _validate_static_selection(
    target_request: AllocationRequest,
    prior_allocation: AllocationResult,
) -> tuple[str, ...]:
    selected = tuple(str(facility_id) for facility_id in prior_allocation.selected_facility_ids)
    target_structural_fingerprint = structural_fingerprint(target_request)
    if prior_allocation.structural_fingerprint != target_structural_fingerprint:
        raise StructuralMismatchError(
            "static allocation and target state do not share invariant decision inputs",
            details={
                "prior_structural_fingerprint": prior_allocation.structural_fingerprint,
                "target_structural_fingerprint": target_structural_fingerprint,
            },
        )

    if prior_allocation.k != target_request.k:
        # K is already in the structural fingerprint, but this explicit check
        # gives an honest error even for a manually constructed result.
        raise InvalidStaticSelectionError(
            "static allocation uses a different configured resource budget",
            details={"prior_k": prior_allocation.k, "target_k": target_request.k},
        )
    if len(selected) != len(set(selected)):
        raise InvalidStaticSelectionError("static allocation contains duplicate facility IDs")
    if tuple(sorted(selected)) != selected:
        raise InvalidStaticSelectionError(
            "static allocation facility IDs are not in canonical order"
        )
    if len(selected) > target_request.k:
        raise InvalidStaticSelectionError(
            "static allocation exceeds the configured resource budget",
            details={"selected_count": len(selected), "k": target_request.k},
        )
    if prior_allocation.resource_count != len(selected):
        raise InvalidStaticSelectionError(
            "static allocation resource count does not match its selection"
        )
    if prior_allocation.remaining_budget != prior_allocation.k - len(selected):
        raise InvalidStaticSelectionError("static allocation remaining budget is inconsistent")
    if prior_allocation.objective_value != prior_allocation.coverage.covered_heat_weighted_demand:
        raise InvalidStaticSelectionError("static allocation objective does not match its coverage")
    if tuple(item.facility_id for item in prior_allocation.coverage.per_facility) != selected:
        raise InvalidStaticSelectionError("static allocation coverage does not match its selection")

    facilities = {facility.facility_id: facility for facility in target_request.facilities}
    unknown = tuple(sorted(set(selected) - set(facilities)))
    ineligible = tuple(
        facility_id
        for facility_id in selected
        if facility_id in facilities
        and facilities[facility_id].eligibility_status is not EligibilityStatus.ELIGIBLE
    )
    if unknown or ineligible:
        raise InvalidStaticSelectionError(
            "static allocation contains unavailable or ineligible facilities",
            details={
                "unknown_facility_ids": unknown,
                "ineligible_facility_ids": ineligible,
            },
        )
    return selected


def evaluate_static_baseline(
    target_request: AllocationRequest,
    prior_allocation: AllocationResult,
) -> CompleteBaselineResult:
    """Evaluate a prior allocation unchanged against a compatible target state."""

    selected = _validate_static_selection(target_request, prior_allocation)
    coverage = evaluate_coverage(target_request, selected)
    return CompleteBaselineResult(
        algorithm=BaselineAlgorithm.STATIC_ALLOCATION,
        scenario_id=target_request.scenario_id,
        state_id=target_request.state_id,
        valid_at=target_request.valid_at,
        k=target_request.k,
        selected_facility_ids=selected,
        objective_value=coverage.covered_heat_weighted_demand,
        coverage=coverage,
        resource_count=len(selected),
        remaining_budget=target_request.k - len(selected),
        structural_fingerprint=structural_fingerprint(target_request),
        full_state_fingerprint=full_state_fingerprint(target_request),
        source_state_id=prior_allocation.state_id,
        source_valid_at=prior_allocation.valid_at,
        source_selected_facility_ids=selected,
        source_full_state_fingerprint=prior_allocation.full_state_fingerprint,
        source_evidence_provenance_refs=prior_allocation.evidence_provenance_refs,
    )


def _thermal_scores(request: AllocationRequest) -> tuple[FacilityThermalScore, ...]:
    """Return Phase-1 provisional equal-PopulationCell catchment means."""

    eligible = set(_eligible_facility_ids(request))
    accessible_cells: dict[str, set[str]] = defaultdict(set)
    for relationship in request.accessibility_relationships:
        if relationship.is_accessible and relationship.facility_id in eligible:
            accessible_cells[relationship.facility_id].add(relationship.cell_id)

    cells = {cell.cell_id: cell for cell in request.demand_cells}
    scores: list[FacilityThermalScore] = []
    for facility_id in sorted(eligible):
        cell_ids = tuple(sorted(accessible_cells.get(facility_id, set())))
        if not cell_ids:
            scores.append(
                FacilityThermalScore(
                    facility_id=facility_id,
                    accessible_cell_count=0,
                    thermal_priority_sum=None,
                    mean_thermal_priority=None,
                    is_available=False,
                    unavailable_reason=_NO_ACCESSIBLE_CELLS,
                )
            )
            continue
        priority_sum = exact_sum(cells[cell_id].thermal_priority for cell_id in cell_ids)
        scores.append(
            FacilityThermalScore(
                facility_id=facility_id,
                accessible_cell_count=len(cell_ids),
                thermal_priority_sum=priority_sum,
                mean_thermal_priority=exact_mean(
                    cells[cell_id].thermal_priority for cell_id in cell_ids
                ),
                is_available=True,
            )
        )
    return tuple(scores)


def evaluate_naive_baseline(request: AllocationRequest) -> BaselineResult:
    """Evaluate the deliberately naive Phase-1 thermal-only allocation.

    Population and catchment overlap do not participate in selection.  The
    equal-cell observation unit is intentionally provisional pending Task 01B.
    """

    eligible = _eligible_facility_ids(request)
    target_count = min(request.k, len(eligible))
    scores = _thermal_scores(request)
    scoreable = tuple(score for score in scores if score.is_available)
    request_structural_fingerprint = structural_fingerprint(request)
    request_full_state_fingerprint = full_state_fingerprint(request)

    if len(scoreable) < target_count:
        return UnavailableBaselineResult(
            algorithm=BaselineAlgorithm.NAIVE_THERMAL,
            scenario_id=request.scenario_id,
            state_id=request.state_id,
            valid_at=request.valid_at,
            k=request.k,
            structural_fingerprint=request_structural_fingerprint,
            full_state_fingerprint=request_full_state_fingerprint,
            unavailable_reason=_INSUFFICIENT_SCOREABLE_FACILITIES,
            unavailable_facility_ids=tuple(
                score.facility_id for score in scores if not score.is_available
            ),
            facility_scores=scores,
        )

    def compare_scores(left: FacilityThermalScore, right: FacilityThermalScore) -> int:
        left_sum = left.thermal_priority_sum
        right_sum = right.thermal_priority_sum
        if left_sum is None or right_sum is None:
            raise ValueError("scoreable facility unexpectedly has no thermal score")
        left_scaled = exact_product(left_sum, Decimal(right.accessible_cell_count))
        right_scaled = exact_product(right_sum, Decimal(left.accessible_cell_count))
        if left_scaled != right_scaled:
            return -1 if left_scaled > right_scaled else 1
        if left.facility_id == right.facility_id:
            return 0
        return -1 if left.facility_id < right.facility_id else 1

    ranked = sorted(scoreable, key=cmp_to_key(compare_scores))
    selected = tuple(sorted(score.facility_id for score in ranked[:target_count]))
    coverage = evaluate_coverage(request, selected)
    return CompleteBaselineResult(
        algorithm=BaselineAlgorithm.NAIVE_THERMAL,
        scenario_id=request.scenario_id,
        state_id=request.state_id,
        valid_at=request.valid_at,
        k=request.k,
        selected_facility_ids=selected,
        objective_value=coverage.covered_heat_weighted_demand,
        coverage=coverage,
        resource_count=len(selected),
        remaining_budget=request.k - len(selected),
        structural_fingerprint=request_structural_fingerprint,
        full_state_fingerprint=request_full_state_fingerprint,
        facility_scores=scores,
    )
