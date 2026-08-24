"""Deterministic exhaustive maximum-coverage allocation."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from coolaccess.canonical import (
    evidence_provenance_refs,
    full_state_fingerprint,
    structural_fingerprint,
)
from coolaccess.contracts import (
    ALGORITHM_VERSION,
    AllocationRequest,
    AllocationResult,
    CoverageSummary,
    EligibilityStatus,
    TieBreakCriterion,
    TieBreakInfo,
)
from coolaccess.coverage import evaluate_coverage
from coolaccess.demand import exact_sum
from coolaccess.errors import InternalConsistencyError


@dataclass(frozen=True, slots=True)
class _Candidate:
    facility_ids: tuple[str, ...]
    coverage: CoverageSummary


def _candidate_is_better(candidate: _Candidate, incumbent: _Candidate) -> bool:
    candidate_objective = candidate.coverage.covered_heat_weighted_demand
    incumbent_objective = incumbent.coverage.covered_heat_weighted_demand
    if candidate_objective != incumbent_objective:
        return candidate_objective > incumbent_objective

    candidate_population = candidate.coverage.covered_population
    incumbent_population = incumbent.coverage.covered_population
    if candidate_population != incumbent_population:
        return candidate_population > incumbent_population
    if len(candidate.facility_ids) != len(incumbent.facility_ids):
        return len(candidate.facility_ids) < len(incumbent.facility_ids)
    return candidate.facility_ids < incumbent.facility_ids


def _tie_break_info(
    candidates: tuple[_Candidate, ...],
    winner: _Candidate,
) -> TieBreakInfo:
    primary_ties = tuple(
        candidate
        for candidate in candidates
        if candidate.coverage.covered_heat_weighted_demand
        == winner.coverage.covered_heat_weighted_demand
    )
    population_ties = tuple(
        candidate
        for candidate in primary_ties
        if candidate.coverage.covered_population == winner.coverage.covered_population
    )
    cardinality_ties = tuple(
        candidate
        for candidate in population_ties
        if len(candidate.facility_ids) == len(winner.facility_ids)
    )

    if len(primary_ties) == 1:
        decisive = TieBreakCriterion.HEAT_WEIGHTED_DEMAND
    elif len(population_ties) == 1:
        decisive = TieBreakCriterion.RAW_POPULATION
    elif len(cardinality_ties) == 1:
        decisive = TieBreakCriterion.FEWER_FACILITIES
    else:
        decisive = TieBreakCriterion.FACILITY_IDS

    return TieBreakInfo(
        evaluated_combination_count=len(candidates),
        decisive_criterion=decisive,
        selected_facility_ids=winner.facility_ids,
        selected_count=len(winner.facility_ids),
        primary_tied_count=len(primary_ties),
        population_tied_count=len(population_ties),
        cardinality_tied_count=len(cardinality_ties),
        algorithm_version=ALGORITHM_VERSION,
    )


def _validate_unused_budget_optimality(
    request: AllocationRequest,
    winner: _Candidate,
    eligible_facility_ids: tuple[str, ...],
) -> None:
    if len(winner.facility_ids) >= request.k:
        return
    selected = set(winner.facility_ids)
    for facility_id in eligible_facility_ids:
        if facility_id in selected:
            continue
        augmented_ids = tuple(sorted((*winner.facility_ids, facility_id)))
        augmented = evaluate_coverage(request, augmented_ids)
        marginal_objective = exact_sum(
            (
                augmented.covered_heat_weighted_demand,
                winner.coverage.covered_heat_weighted_demand.copy_negate(),
            )
        )
        marginal_population = exact_sum(
            (
                augmented.covered_population,
                winner.coverage.covered_population.copy_negate(),
            )
        )
        if marginal_objective < 0 or marginal_population < 0:
            raise InternalConsistencyError(
                "adding a facility produced a negative union-coverage marginal value",
                details={
                    "facility_id": facility_id,
                    "marginal_objective": str(marginal_objective),
                    "marginal_population": str(marginal_population),
                },
            )
        if marginal_objective > 0 or marginal_population > 0:
            raise InternalConsistencyError(
                "allocation with unused budget is not optimal",
                details={
                    "facility_id": facility_id,
                    "marginal_objective": str(marginal_objective),
                    "marginal_population": str(marginal_population),
                },
            )


def optimize(request: AllocationRequest) -> AllocationResult:
    """Enumerate all feasible subsets and return the canonical optimum."""

    eligible_facility_ids = tuple(
        facility.facility_id
        for facility in request.facilities
        if facility.eligibility_status is EligibilityStatus.ELIGIBLE
    )
    selection_bound = min(request.k, len(eligible_facility_ids))
    candidates = tuple(
        _Candidate(facility_ids, evaluate_coverage(request, facility_ids))
        for selected_count in range(selection_bound + 1)
        for facility_ids in combinations(eligible_facility_ids, selected_count)
    )
    if not candidates:
        raise InternalConsistencyError("enumeration produced no feasible allocations")

    winner = candidates[0]
    for candidate in candidates[1:]:
        if _candidate_is_better(candidate, winner):
            winner = candidate

    _validate_unused_budget_optimality(request, winner, eligible_facility_ids)
    resource_count = len(winner.facility_ids)
    return AllocationResult(
        scenario_id=request.scenario_id,
        state_id=request.state_id,
        valid_at=request.valid_at,
        k=request.k,
        selected_facility_ids=winner.facility_ids,
        objective_value=winner.coverage.covered_heat_weighted_demand,
        coverage=winner.coverage,
        resource_count=resource_count,
        remaining_budget=request.k - resource_count,
        tie_break=_tie_break_info(candidates, winner),
        algorithm_version=ALGORITHM_VERSION,
        structural_fingerprint=structural_fingerprint(request),
        full_state_fingerprint=full_state_fingerprint(request),
        evidence_provenance_refs=evidence_provenance_refs(request),
    )
