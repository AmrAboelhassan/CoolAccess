"""Deterministic replacement and unused-budget evidence builders."""

from __future__ import annotations

from decimal import Decimal

from coolaccess.canonical import (
    canonical_json,
    evidence_provenance_refs,
    full_state_fingerprint,
    structural_fingerprint,
)
from coolaccess.contracts import (
    AllocationRequest,
    AllocationResult,
    EligibilityStatus,
    EvidenceStatus,
    FacilityCoverage,
    MarginalAdditionEvidence,
    MarginalAdditionEvidenceSet,
    MarginalAdditionNotApplicableReason,
    MarginalAdditionOutcome,
    ReplacementComparatorOutcome,
    ReplacementEvidence,
    ReplacementReasonCode,
    TieBreakCriterion,
)
from coolaccess.coverage import evaluate_coverage
from coolaccess.demand import exact_sum
from coolaccess.errors import (
    FullStateMismatchError,
    InternalConsistencyError,
    InvalidMarginalAdditionError,
    InvalidReplacementError,
    StructuralMismatchError,
)


def _validate_result_for_request(
    request: AllocationRequest,
    allocation: AllocationResult,
) -> None:
    expected_structural = structural_fingerprint(request)
    expected_full_state = full_state_fingerprint(request)
    if allocation.structural_fingerprint != expected_structural:
        raise StructuralMismatchError(
            "allocation and request do not share invariant decision inputs",
            details={
                "allocation_structural_fingerprint": allocation.structural_fingerprint,
                "request_structural_fingerprint": expected_structural,
            },
        )
    if allocation.full_state_fingerprint != expected_full_state:
        raise FullStateMismatchError(
            "allocation and request do not describe the same thermal state",
            details={
                "allocation_full_state_fingerprint": allocation.full_state_fingerprint,
                "request_full_state_fingerprint": expected_full_state,
            },
        )
    if allocation.k != request.k:
        raise InternalConsistencyError(
            "allocation resource budget does not match its fingerprinted request",
            details={"allocation_k": allocation.k, "request_k": request.k},
        )

    selected = allocation.selected_facility_ids
    if selected != tuple(sorted(selected)) or len(selected) != len(set(selected)):
        raise InternalConsistencyError(
            "allocation selection is not canonical",
            details={"selected_facility_ids": selected},
        )
    calculated = evaluate_coverage(request, selected)
    if (
        allocation.coverage != calculated
        or allocation.objective_value != calculated.covered_heat_weighted_demand
        or allocation.resource_count != len(selected)
        or allocation.remaining_budget != request.k - len(selected)
    ):
        raise InternalConsistencyError(
            "allocation authoritative totals do not match deterministic reevaluation",
            details={"selected_facility_ids": selected},
        )


def _coverage_for_facility(
    per_facility: tuple[FacilityCoverage, ...], facility_id: str
) -> FacilityCoverage:
    for coverage in per_facility:
        if coverage.facility_id == facility_id:
            return coverage
    raise InternalConsistencyError(
        "evaluated selection is missing per-facility coverage",
        details={"facility_id": facility_id},
    )


def _cell_totals(
    request: AllocationRequest,
    cell_ids: tuple[str, ...],
) -> tuple[Decimal, Decimal]:
    cells = {cell.cell_id: cell for cell in request.demand_cells}
    demands: list[Decimal] = []
    populations: list[Decimal] = []
    for cell_id in cell_ids:
        cell = cells[cell_id]
        if cell.heat_weighted_demand is None:
            raise InternalConsistencyError(
                "validated demand cell has no derived demand",
                details={"cell_id": cell_id},
            )
        demands.append(cell.heat_weighted_demand)
        populations.append(cell.population)
    return exact_sum(demands), exact_sum(populations)


def _replacement_comparison(
    original_objective: Decimal,
    replacement_objective: Decimal,
    original_population: Decimal,
    replacement_population: Decimal,
    original_ids: tuple[str, ...],
    replacement_ids: tuple[str, ...],
) -> tuple[
    ReplacementComparatorOutcome,
    TieBreakCriterion | None,
    ReplacementReasonCode,
]:
    if replacement_objective < original_objective:
        return (
            ReplacementComparatorOutcome.ORIGINAL_PREFERRED,
            TieBreakCriterion.HEAT_WEIGHTED_DEMAND,
            ReplacementReasonCode.PRIMARY_OBJECTIVE_LOSS,
        )
    if replacement_objective > original_objective:
        return (
            ReplacementComparatorOutcome.REPLACEMENT_PREFERRED,
            TieBreakCriterion.HEAT_WEIGHTED_DEMAND,
            ReplacementReasonCode.REPLACEMENT_PRIMARY_OBJECTIVE_WIN,
        )
    if replacement_population < original_population:
        return (
            ReplacementComparatorOutcome.ORIGINAL_PREFERRED,
            TieBreakCriterion.RAW_POPULATION,
            ReplacementReasonCode.POPULATION_TIE_BREAK_LOSS,
        )
    if replacement_population > original_population:
        return (
            ReplacementComparatorOutcome.REPLACEMENT_PREFERRED,
            TieBreakCriterion.RAW_POPULATION,
            ReplacementReasonCode.REPLACEMENT_POPULATION_TIE_BREAK_WIN,
        )
    if replacement_ids > original_ids:
        return (
            ReplacementComparatorOutcome.ORIGINAL_PREFERRED,
            TieBreakCriterion.FACILITY_IDS,
            ReplacementReasonCode.STABLE_ID_TIE_BREAK_LOSS,
        )
    if replacement_ids < original_ids:
        return (
            ReplacementComparatorOutcome.REPLACEMENT_PREFERRED,
            TieBreakCriterion.FACILITY_IDS,
            ReplacementReasonCode.REPLACEMENT_STABLE_ID_TIE_BREAK_WIN,
        )
    return (
        ReplacementComparatorOutcome.COMPARATOR_EQUIVALENT,
        None,
        ReplacementReasonCode.COMPARATOR_EQUIVALENT,
    )


def build_replacement_evidence(
    request: AllocationRequest,
    allocation: AllocationResult,
    selected_id: str,
    unselected_id: str,
) -> ReplacementEvidence:
    """Build a one-for-one comparison without hiding any comparator criterion."""

    _validate_result_for_request(request, allocation)
    selected = allocation.selected_facility_ids
    if selected_id == unselected_id:
        raise InvalidReplacementError("replacement facility IDs must be different")
    if selected_id not in selected:
        raise InvalidReplacementError(
            "selected replacement ID is not in the allocation",
            details={"selected_facility_id": selected_id},
        )
    if unselected_id in selected:
        raise InvalidReplacementError(
            "replacement alternative is already selected",
            details={"alternative_facility_id": unselected_id},
        )

    facilities = {facility.facility_id: facility for facility in request.facilities}
    alternative = facilities.get(unselected_id)
    if alternative is None:
        raise InvalidReplacementError(
            "replacement alternative is unknown",
            details={"alternative_facility_id": unselected_id},
        )
    if alternative.eligibility_status is not EligibilityStatus.ELIGIBLE:
        raise InvalidReplacementError(
            "replacement alternative is ineligible",
            details={"alternative_facility_id": unselected_id},
        )

    retained_ids = tuple(facility_id for facility_id in selected if facility_id != selected_id)
    replacement_ids = tuple(sorted((*retained_ids, unselected_id)))
    if len(replacement_ids) != len(selected):
        raise InternalConsistencyError("one-for-one replacement changed cardinality")
    replacement_coverage = evaluate_coverage(request, replacement_ids)
    original_coverage = allocation.coverage

    objective_delta = exact_sum(
        (
            replacement_coverage.covered_heat_weighted_demand,
            original_coverage.covered_heat_weighted_demand.copy_negate(),
        )
    )
    population_delta = exact_sum(
        (
            replacement_coverage.covered_population,
            original_coverage.covered_population.copy_negate(),
        )
    )
    outcome, criterion, reason = _replacement_comparison(
        original_coverage.covered_heat_weighted_demand,
        replacement_coverage.covered_heat_weighted_demand,
        original_coverage.covered_population,
        replacement_coverage.covered_population,
        selected,
        replacement_ids,
    )

    original_cells = set(original_coverage.covered_cell_ids)
    replacement_cells = set(replacement_coverage.covered_cell_ids)
    lost_ids = tuple(sorted(original_cells - replacement_cells))
    gained_ids = tuple(sorted(replacement_cells - original_cells))
    retained_covered_ids = tuple(sorted(original_cells & replacement_cells))
    lost_demand, lost_population = _cell_totals(request, lost_ids)
    gained_demand, gained_population = _cell_totals(request, gained_ids)
    retained_demand, retained_population = _cell_totals(request, retained_covered_ids)

    return ReplacementEvidence(
        selected_facility_id=selected_id,
        alternative_facility_id=unselected_id,
        original_facility_ids=selected,
        retained_facility_ids=retained_ids,
        replacement_facility_ids=replacement_ids,
        original_resource_count=len(selected),
        replacement_resource_count=len(replacement_ids),
        remaining_budget=request.k - len(selected),
        original_objective=original_coverage.covered_heat_weighted_demand,
        replacement_objective=replacement_coverage.covered_heat_weighted_demand,
        objective_delta=objective_delta,
        primary_objective_loss=max(objective_delta.copy_negate(), Decimal(0)),
        primary_objective_gain=max(objective_delta, Decimal(0)),
        original_covered_population=original_coverage.covered_population,
        replacement_covered_population=replacement_coverage.covered_population,
        population_delta=population_delta,
        comparator_outcome=outcome,
        decisive_criterion=criterion,
        reason_code=reason,
        selected_coverage=_coverage_for_facility(original_coverage.per_facility, selected_id),
        alternative_coverage=_coverage_for_facility(
            replacement_coverage.per_facility, unselected_id
        ),
        lost_cell_ids=lost_ids,
        lost_heat_weighted_demand=lost_demand,
        lost_population=lost_population,
        gained_cell_ids=gained_ids,
        gained_heat_weighted_demand=gained_demand,
        gained_population=gained_population,
        retained_covered_cell_ids=retained_covered_ids,
        retained_heat_weighted_demand=retained_demand,
        retained_population=retained_population,
        structural_fingerprint=structural_fingerprint(request),
        full_state_fingerprint=full_state_fingerprint(request),
        evidence_provenance_refs=evidence_provenance_refs(request),
    )


def validate_replacement_optimality(evidence: ReplacementEvidence) -> None:
    """Reject evidence showing that the replacement wins the approved comparator."""

    if evidence.comparator_outcome is ReplacementComparatorOutcome.REPLACEMENT_PREFERRED:
        raise InternalConsistencyError(
            "purported optimal allocation loses to a one-for-one replacement",
            details={"replacement_evidence": canonical_json(evidence)},
        )


def build_marginal_addition_evidence(
    request: AllocationRequest,
    allocation: AllocationResult,
    unselected_id: str,
) -> MarginalAdditionEvidence:
    """Explain the value of adding one eligible facility to unused budget."""

    _validate_result_for_request(request, allocation)
    selected = allocation.selected_facility_ids
    if allocation.resource_count >= request.k:
        raise InvalidMarginalAdditionError(
            "marginal addition is not applicable when the resource budget is full"
        )
    if unselected_id in selected:
        raise InvalidMarginalAdditionError(
            "marginal-addition facility is already selected",
            details={"facility_id": unselected_id},
        )
    facilities = {facility.facility_id: facility for facility in request.facilities}
    facility = facilities.get(unselected_id)
    if facility is None:
        raise InvalidMarginalAdditionError(
            "marginal-addition facility is unknown",
            details={"facility_id": unselected_id},
        )
    if facility.eligibility_status is not EligibilityStatus.ELIGIBLE:
        raise InvalidMarginalAdditionError(
            "marginal-addition facility is ineligible",
            details={"facility_id": unselected_id},
        )

    augmented_ids = tuple(sorted((*selected, unselected_id)))
    augmented_coverage = evaluate_coverage(request, augmented_ids)
    original_coverage = allocation.coverage
    marginal_objective = exact_sum(
        (
            augmented_coverage.covered_heat_weighted_demand,
            original_coverage.covered_heat_weighted_demand.copy_negate(),
        )
    )
    marginal_population = exact_sum(
        (
            augmented_coverage.covered_population,
            original_coverage.covered_population.copy_negate(),
        )
    )
    if marginal_objective < 0 or marginal_population < 0:
        raise InternalConsistencyError(
            "adding a facility produced a negative union-coverage marginal value",
            details={
                "facility_id": unselected_id,
                "marginal_objective": str(marginal_objective),
                "marginal_population": str(marginal_population),
            },
        )
    if marginal_objective > 0:
        outcome = MarginalAdditionOutcome.POSITIVE_MARGINAL_OBJECTIVE
    elif marginal_population > 0:
        outcome = MarginalAdditionOutcome.POPULATION_ONLY_MARGINAL_VALUE
    else:
        outcome = MarginalAdditionOutcome.ZERO_MARGINAL_VALUE

    catchment_ids = {
        relationship.cell_id
        for relationship in request.accessibility_relationships
        if relationship.is_accessible and relationship.facility_id == unselected_id
    }
    original_cells = set(original_coverage.covered_cell_ids)
    newly_covered_ids = tuple(sorted(catchment_ids - original_cells))
    redundant_ids = tuple(sorted(catchment_ids & original_cells))
    new_demand, new_population = _cell_totals(request, newly_covered_ids)
    redundant_demand, redundant_population = _cell_totals(request, redundant_ids)

    return MarginalAdditionEvidence(
        unselected_facility_id=unselected_id,
        original_facility_ids=selected,
        augmented_facility_ids=augmented_ids,
        original_objective=original_coverage.covered_heat_weighted_demand,
        augmented_objective=augmented_coverage.covered_heat_weighted_demand,
        marginal_heat_weighted_demand_gain=marginal_objective,
        original_covered_population=original_coverage.covered_population,
        augmented_covered_population=augmented_coverage.covered_population,
        marginal_population_gain=marginal_population,
        newly_covered_cell_ids=newly_covered_ids,
        newly_covered_heat_weighted_demand=new_demand,
        newly_covered_population=new_population,
        redundant_cell_ids=redundant_ids,
        redundant_heat_weighted_demand=redundant_demand,
        redundant_population=redundant_population,
        resource_count_before=len(selected),
        resource_count_after=len(augmented_ids),
        remaining_budget_before=request.k - len(selected),
        remaining_budget_after=request.k - len(augmented_ids),
        outcome=outcome,
        structural_fingerprint=structural_fingerprint(request),
        full_state_fingerprint=full_state_fingerprint(request),
        evidence_provenance_refs=evidence_provenance_refs(request),
    )


def validate_marginal_optimality(evidence: MarginalAdditionEvidence) -> None:
    """Reject any beneficial feasible addition to a purported optimum."""

    if evidence.outcome is not MarginalAdditionOutcome.ZERO_MARGINAL_VALUE:
        raise InternalConsistencyError(
            "purported optimal allocation leaves beneficial resource capacity unused",
            details={"marginal_addition_evidence": canonical_json(evidence)},
        )


def build_marginal_addition_evidence_set(
    request: AllocationRequest,
    allocation: AllocationResult,
) -> MarginalAdditionEvidenceSet:
    """Build canonical evidence for every eligible unselected facility."""

    _validate_result_for_request(request, allocation)
    if allocation.resource_count == request.k:
        return MarginalAdditionEvidenceSet(
            status=EvidenceStatus.NOT_APPLICABLE,
            not_applicable_reason=MarginalAdditionNotApplicableReason.RESOURCE_BUDGET_FULL,
        )

    selected = set(allocation.selected_facility_ids)
    unselected = tuple(
        facility.facility_id
        for facility in request.facilities
        if facility.eligibility_status is EligibilityStatus.ELIGIBLE
        and facility.facility_id not in selected
    )
    if not unselected:
        return MarginalAdditionEvidenceSet(
            status=EvidenceStatus.NOT_APPLICABLE,
            not_applicable_reason=(
                MarginalAdditionNotApplicableReason.NO_ELIGIBLE_UNSELECTED_FACILITIES
            ),
        )
    return MarginalAdditionEvidenceSet(
        status=EvidenceStatus.APPLICABLE,
        evidence=tuple(
            build_marginal_addition_evidence(request, allocation, facility_id)
            for facility_id in unselected
        ),
    )
