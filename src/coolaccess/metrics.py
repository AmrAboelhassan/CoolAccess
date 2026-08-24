"""Scenario-specific planning/accessibility proxy metrics."""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal, localcontext

from coolaccess.contracts import (
    AllocationResult,
    BaselineComparison,
    BaselineResult,
    BaselineStatus,
    CompleteBaselineResult,
    CoverageSummary,
    MetricStatus,
    MetricValue,
    SelectionChange,
)
from coolaccess.demand import canonical_decimal, exact_sum
from coolaccess.errors import (
    FullStateMismatchError,
    InternalConsistencyError,
    StructuralMismatchError,
)

_PERCENT_QUANTUM = Decimal("0.000000000001")


def _validate_result_summaries(
    optimized: AllocationResult,
    baseline: BaselineResult,
) -> None:
    selected = optimized.selected_facility_ids
    if (
        selected != tuple(sorted(selected))
        or len(selected) != len(set(selected))
        or optimized.resource_count != len(selected)
        or optimized.resource_count > optimized.k
        or optimized.remaining_budget != optimized.k - optimized.resource_count
        or optimized.objective_value != optimized.coverage.covered_heat_weighted_demand
        or tuple(item.facility_id for item in optimized.coverage.per_facility) != selected
    ):
        raise InternalConsistencyError("optimized allocation summary is inconsistent")

    if baseline.status is BaselineStatus.COMPLETE:
        if not isinstance(baseline, CompleteBaselineResult):
            raise InternalConsistencyError("unknown complete baseline result type")
        baseline_selected = baseline.selected_facility_ids
        if (
            baseline_selected != tuple(sorted(baseline_selected))
            or len(baseline_selected) != len(set(baseline_selected))
            or baseline.resource_count != len(baseline_selected)
            or baseline.resource_count > baseline.k
            or baseline.remaining_budget != baseline.k - baseline.resource_count
            or baseline.objective_value != baseline.coverage.covered_heat_weighted_demand
            or tuple(item.facility_id for item in baseline.coverage.per_facility)
            != baseline_selected
        ):
            raise InternalConsistencyError("baseline allocation summary is inconsistent")
        if (
            optimized.coverage.total_heat_weighted_demand
            != baseline.coverage.total_heat_weighted_demand
            or optimized.coverage.total_population != baseline.coverage.total_population
            or set(optimized.coverage.covered_cell_ids) | set(optimized.coverage.uncovered_cell_ids)
            != set(baseline.coverage.covered_cell_ids) | set(baseline.coverage.uncovered_cell_ids)
        ):
            raise FullStateMismatchError(
                "optimized and baseline coverage summaries describe different demand cells"
            )


def _percentage(numerator: Decimal, denominator: Decimal) -> Decimal:
    precision = max(
        40,
        len(numerator.as_tuple().digits)
        + len(denominator.as_tuple().digits)
        + abs(numerator.adjusted() - denominator.adjusted())
        + 20,
    )
    with localcontext() as context:
        context.prec = precision
        value = (numerator * Decimal(100)) / denominator
        return value.quantize(_PERCENT_QUANTUM, rounding=ROUND_HALF_EVEN)


def available_metric(
    value: Decimal,
    *,
    unit: str,
    numerator: Decimal | None = None,
    denominator: Decimal | None = None,
) -> MetricValue:
    """Construct an available authoritative proxy metric."""

    return MetricValue(
        value=canonical_decimal(value),
        status=MetricStatus.AVAILABLE,
        unit=unit,
        numerator=numerator,
        denominator=denominator,
    )


def not_applicable_metric(
    *,
    unit: str,
    reason_code: str,
    numerator: Decimal | None = None,
    denominator: Decimal | None = None,
) -> MetricValue:
    """Construct an explicit unavailable ratio without fabricating a number."""

    return MetricValue(
        value=None,
        status=MetricStatus.NOT_APPLICABLE,
        unit=unit,
        numerator=numerator,
        denominator=denominator,
        reason_code=reason_code,
    )


def calculate_coverage_percentage(coverage: CoverageSummary) -> MetricValue:
    """Return percent of total scenario demand covered, or an honest N/A."""

    total = coverage.total_heat_weighted_demand
    covered = coverage.covered_heat_weighted_demand
    if total == 0:
        return not_applicable_metric(
            unit="percent",
            reason_code="ZERO_TOTAL_DEMAND",
            numerator=covered,
            denominator=total,
        )
    return available_metric(
        _percentage(covered, total),
        unit="percent",
        numerator=covered,
        denominator=total,
    )


def calculate_selection_change(
    target_facility_ids: tuple[str, ...],
    reference_facility_ids: tuple[str, ...],
) -> SelectionChange:
    """Return stable added/removed IDs and changed resource slots."""

    target = set(target_facility_ids)
    reference = set(reference_facility_ids)
    added = tuple(sorted(target - reference))
    removed = tuple(sorted(reference - target))
    return SelectionChange(
        added_facility_ids=added,
        removed_facility_ids=removed,
        added_count=len(added),
        removed_count=len(removed),
        changed_slot_count=max(len(added), len(removed)),
    )


def compare_with_baseline(
    optimized: AllocationResult,
    baseline: BaselineResult,
) -> BaselineComparison:
    """Compare allocations only when they describe the identical target state."""

    if optimized.structural_fingerprint != baseline.structural_fingerprint:
        raise StructuralMismatchError(
            "optimized and baseline allocations use different invariant inputs",
            details={
                "optimized_structural_fingerprint": optimized.structural_fingerprint,
                "baseline_structural_fingerprint": baseline.structural_fingerprint,
            },
        )
    if optimized.full_state_fingerprint != baseline.full_state_fingerprint:
        raise FullStateMismatchError(
            "optimized and baseline allocations use different target thermal states",
            details={
                "optimized_full_state_fingerprint": optimized.full_state_fingerprint,
                "baseline_full_state_fingerprint": baseline.full_state_fingerprint,
            },
        )

    _validate_result_summaries(optimized, baseline)

    if baseline.status is BaselineStatus.UNAVAILABLE:
        return BaselineComparison(
            algorithm=baseline.algorithm,
            baseline_status=baseline.status,
            optimized_objective=optimized.objective_value,
            baseline_objective=None,
            absolute_improvement=None,
            percentage_improvement=not_applicable_metric(
                unit="percent",
                reason_code="BASELINE_UNAVAILABLE",
            ),
            selection_change=None,
            full_state_fingerprint=optimized.full_state_fingerprint,
        )

    # The discriminated result type lets type checkers narrow only with an
    # explicit assertion when callers pass the union type directly.
    if not isinstance(baseline, CompleteBaselineResult):
        raise InternalConsistencyError("unknown complete baseline result type")
    absolute = exact_sum((optimized.objective_value, baseline.objective_value.copy_negate()))
    if absolute < 0:
        raise InternalConsistencyError(
            "optimized objective is below a valid same-input baseline",
            details={
                "algorithm": baseline.algorithm.value,
                "optimized_objective": str(optimized.objective_value),
                "baseline_objective": str(baseline.objective_value),
            },
        )

    if baseline.objective_value == 0:
        percentage = not_applicable_metric(
            unit="percent",
            reason_code="ZERO_BASELINE_OBJECTIVE",
            numerator=absolute,
            denominator=baseline.objective_value,
        )
    else:
        percentage = available_metric(
            _percentage(absolute, baseline.objective_value),
            unit="percent",
            numerator=absolute,
            denominator=baseline.objective_value,
        )
    return BaselineComparison(
        algorithm=baseline.algorithm,
        baseline_status=baseline.status,
        optimized_objective=optimized.objective_value,
        baseline_objective=baseline.objective_value,
        absolute_improvement=absolute,
        percentage_improvement=percentage,
        selection_change=calculate_selection_change(
            optimized.selected_facility_ids,
            baseline.selected_facility_ids,
        ),
        full_state_fingerprint=optimized.full_state_fingerprint,
    )
