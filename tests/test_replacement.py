"""SYNTHETIC TEST DATA — NOT FORTYGUARD OR MUNICIPAL DATA."""

from __future__ import annotations

from decimal import Decimal

import pytest

from coolaccess.contracts import (
    AllocationRequest,
    AllocationResult,
    EvidenceStatus,
    MarginalAdditionNotApplicableReason,
    MarginalAdditionOutcome,
    ReplacementComparatorOutcome,
    ReplacementReasonCode,
    TieBreakCriterion,
)
from coolaccess.coverage import evaluate_coverage
from coolaccess.errors import (
    InternalConsistencyError,
    InvalidMarginalAdditionError,
    InvalidReplacementError,
)
from coolaccess.optimizer import optimize
from coolaccess.replacement import (
    build_marginal_addition_evidence,
    build_marginal_addition_evidence_set,
    build_replacement_evidence,
    validate_marginal_optimality,
    validate_replacement_optimality,
)
from tests.synthetic_fixtures import make_request


def _purported_allocation(
    request: AllocationRequest,
    selected_facility_ids: tuple[str, ...],
) -> AllocationResult:
    template = optimize(request)
    coverage = evaluate_coverage(request, selected_facility_ids)
    return template.model_copy(
        update={
            "selected_facility_ids": selected_facility_ids,
            "objective_value": coverage.covered_heat_weighted_demand,
            "coverage": coverage,
            "resource_count": len(selected_facility_ids),
            "remaining_budget": request.k - len(selected_facility_ids),
        }
    )


def test_replacement_primary_objective_loss_and_cell_evidence() -> None:
    request = make_request(
        cells=(("c1", 10, "1"), ("c2", 20, "1"), ("c3", 30, "1")),
        facility_ids=("A", "B", "C"),
        edges=(
            ("c1", "A"),
            ("c2", "A"),
            ("c2", "B"),
            ("c3", "B"),
            ("c1", "C"),
        ),
        k=2,
    )
    allocation = optimize(request)

    evidence = build_replacement_evidence(request, allocation, "B", "C")

    assert allocation.selected_facility_ids == ("A", "B")
    assert evidence.comparator_outcome is ReplacementComparatorOutcome.ORIGINAL_PREFERRED
    assert evidence.reason_code is ReplacementReasonCode.PRIMARY_OBJECTIVE_LOSS
    assert evidence.retained_covered_cell_ids == ("c1", "c2")
    assert evidence.retained_heat_weighted_demand == 30
    assert evidence.retained_population == 30
    assert evidence.decisive_criterion is TieBreakCriterion.HEAT_WEIGHTED_DEMAND
    assert evidence.lost_cell_ids == ("c3",)
    assert evidence.lost_heat_weighted_demand == 30
    assert evidence.gained_cell_ids == ()
    assert evidence.selected_coverage.unique_cell_ids == ("c3",)
    assert evidence.selected_coverage.overlapping_cell_ids == ("c2",)
    assert evidence.alternative_coverage.overlapping_cell_ids == ("c1",)
    assert evidence.original_resource_count == evidence.replacement_resource_count
    validate_replacement_optimality(evidence)


def test_positive_primary_objective_replacement_is_consistency_failure() -> None:
    request = make_request(
        cells=(("a", 100, "1"), ("b", 10, "1")),
        facility_ids=("A", "B"),
        edges=(("a", "A"), ("b", "B")),
        k=1,
    )
    purported = _purported_allocation(request, ("B",))

    evidence = build_replacement_evidence(request, purported, "B", "A")

    assert evidence.reason_code is ReplacementReasonCode.REPLACEMENT_PRIMARY_OBJECTIVE_WIN
    with pytest.raises(InternalConsistencyError):
        validate_replacement_optimality(evidence)


def test_population_tie_break_handles_both_directions() -> None:
    request = make_request(
        cells=(("a", 100, "0.5"), ("b", 50, "1")),
        facility_ids=("A", "B"),
        edges=(("a", "A"), ("b", "B")),
        k=1,
    )
    valid = build_replacement_evidence(
        request,
        _purported_allocation(request, ("A",)),
        "A",
        "B",
    )
    invalid = build_replacement_evidence(
        request,
        _purported_allocation(request, ("B",)),
        "B",
        "A",
    )

    assert valid.original_objective == valid.replacement_objective == 50
    assert valid.reason_code is ReplacementReasonCode.POPULATION_TIE_BREAK_LOSS
    assert valid.decisive_criterion is TieBreakCriterion.RAW_POPULATION
    validate_replacement_optimality(valid)
    assert invalid.reason_code is ReplacementReasonCode.REPLACEMENT_POPULATION_TIE_BREAK_WIN
    with pytest.raises(InternalConsistencyError):
        validate_replacement_optimality(invalid)


def test_stable_id_tie_break_handles_both_directions() -> None:
    request = make_request(
        cells=(("c", 100, "0.5"),),
        facility_ids=("A", "B"),
        edges=(("c", "A"), ("c", "B")),
        k=1,
    )
    valid = build_replacement_evidence(
        request,
        _purported_allocation(request, ("A",)),
        "A",
        "B",
    )
    invalid = build_replacement_evidence(
        request,
        _purported_allocation(request, ("B",)),
        "B",
        "A",
    )

    assert valid.reason_code is ReplacementReasonCode.STABLE_ID_TIE_BREAK_LOSS
    assert valid.decisive_criterion is TieBreakCriterion.FACILITY_IDS
    validate_replacement_optimality(valid)
    assert invalid.reason_code is ReplacementReasonCode.REPLACEMENT_STABLE_ID_TIE_BREAK_WIN
    with pytest.raises(InternalConsistencyError):
        validate_replacement_optimality(invalid)


def test_invalid_replacement_roles_fail_honestly() -> None:
    request = make_request(
        cells=(("c", 1, "1"),),
        facility_ids=("A", "B", "X"),
        ineligible_facility_ids=("X",),
        edges=(("c", "A"),),
        k=1,
    )
    allocation = optimize(request)

    for selected_id, alternative_id in (("B", "A"), ("A", "A"), ("A", "X"), ("A", "Z")):
        with pytest.raises(InvalidReplacementError):
            build_replacement_evidence(
                request,
                allocation,
                selected_id,
                alternative_id,
            )


def test_zero_marginal_addition_explains_unused_budget() -> None:
    request = make_request(
        cells=(("c1", 100, "1"), ("c2", 50, "0.5")),
        facility_ids=("A", "B"),
        edges=(("c1", "A"), ("c1", "B"), ("c2", "B")),
        k=3,
    )
    allocation = optimize(request)

    evidence_set = build_marginal_addition_evidence_set(request, allocation)
    evidence = evidence_set.evidence[0]

    assert allocation.selected_facility_ids == ("B",)
    assert evidence_set.status is EvidenceStatus.APPLICABLE
    assert evidence.unselected_facility_id == "A"
    assert evidence.outcome is MarginalAdditionOutcome.ZERO_MARGINAL_VALUE
    assert evidence.marginal_heat_weighted_demand_gain == 0
    assert evidence.marginal_population_gain == 0
    assert evidence.newly_covered_cell_ids == ()
    assert evidence.redundant_cell_ids == ("c1",)
    assert evidence.resource_count_before == 1
    assert evidence.resource_count_after == 2
    assert evidence.remaining_budget_before == 2
    assert evidence.remaining_budget_after == 1
    validate_marginal_optimality(evidence)


def test_positive_marginal_objective_is_consistency_failure() -> None:
    request = make_request(
        cells=(("b", 10, "1"), ("u", 20, "1")),
        facility_ids=("B", "U"),
        edges=(("b", "B"), ("u", "U")),
        k=2,
    )
    purported = _purported_allocation(request, ("B",))

    evidence = build_marginal_addition_evidence(request, purported, "U")

    assert evidence.outcome is MarginalAdditionOutcome.POSITIVE_MARGINAL_OBJECTIVE
    with pytest.raises(InternalConsistencyError):
        validate_marginal_optimality(evidence)


def test_population_only_marginal_value_is_consistency_failure() -> None:
    request = make_request(
        cells=(("b", 10, "1"), ("u", 20, "0")),
        facility_ids=("B", "U"),
        edges=(("b", "B"), ("u", "U")),
        k=2,
    )
    purported = _purported_allocation(request, ("B",))

    evidence = build_marginal_addition_evidence(request, purported, "U")

    assert evidence.marginal_heat_weighted_demand_gain == 0
    assert evidence.marginal_population_gain == 20
    assert evidence.outcome is MarginalAdditionOutcome.POPULATION_ONLY_MARGINAL_VALUE
    with pytest.raises(InternalConsistencyError):
        validate_marginal_optimality(evidence)


def test_marginal_evidence_not_applicable_states() -> None:
    full_request = make_request(
        cells=(("c", 10, "1"),),
        facility_ids=("A", "B"),
        edges=(("c", "A"),),
        k=1,
    )
    full = build_marginal_addition_evidence_set(full_request, optimize(full_request))
    assert full.status is EvidenceStatus.NOT_APPLICABLE
    assert full.not_applicable_reason is MarginalAdditionNotApplicableReason.RESOURCE_BUDGET_FULL
    assert full.evidence == ()

    no_alternative_request = make_request(
        cells=(("c", 10, "1"),),
        facility_ids=("A",),
        edges=(("c", "A"),),
        k=3,
    )
    no_alternative = build_marginal_addition_evidence_set(
        no_alternative_request,
        optimize(no_alternative_request),
    )
    assert no_alternative.status is EvidenceStatus.NOT_APPLICABLE
    assert (
        no_alternative.not_applicable_reason
        is MarginalAdditionNotApplicableReason.NO_ELIGIBLE_UNSELECTED_FACILITIES
    )


def test_marginal_evidence_is_canonical_and_rejects_invalid_facilities() -> None:
    request = make_request(
        cells=(("c", 10, "1"),),
        facility_ids=("C", "B", "A", "X"),
        ineligible_facility_ids=("X",),
        edges=(("c", "B"), ("c", "A"), ("c", "C")),
        k=4,
    )
    allocation = optimize(request)
    evidence = build_marginal_addition_evidence_set(request, allocation)

    assert tuple(item.unselected_facility_id for item in evidence.evidence) == ("B", "C")
    assert all(
        item.outcome is MarginalAdditionOutcome.ZERO_MARGINAL_VALUE for item in evidence.evidence
    )
    with pytest.raises(InvalidMarginalAdditionError):
        build_marginal_addition_evidence(request, allocation, "A")
    with pytest.raises(InvalidMarginalAdditionError):
        build_marginal_addition_evidence(request, allocation, "X")
    with pytest.raises(InvalidMarginalAdditionError):
        build_marginal_addition_evidence(request, allocation, "unknown")


def test_large_decimal_replacement_and_marginal_deltas_are_exact() -> None:
    request = make_request(
        cells=(
            ("large", "123456789012345678901234567890.1", "1"),
            ("small", "0.1", "1"),
        ),
        facility_ids=("A", "B"),
        edges=(("large", "A"), ("small", "B")),
        k=1,
    )
    optimized = optimize(request)
    replacement = build_replacement_evidence(request, optimized, "A", "B")
    assert replacement.primary_objective_loss == Decimal("123456789012345678901234567890")

    unused_budget_request = request.model_copy(update={"k": 2})
    purported = _purported_allocation(unused_budget_request, ("B",))
    marginal = build_marginal_addition_evidence(
        unused_budget_request,
        purported,
        "A",
    )
    assert marginal.marginal_heat_weighted_demand_gain == Decimal(
        "123456789012345678901234567890.1"
    )
