"""SYNTHETIC TEST DATA — NOT FORTYGUARD OR MUNICIPAL DATA."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from coolaccess.baselines import evaluate_naive_baseline, evaluate_static_baseline
from coolaccess.contracts import PROXY_LABEL, AllocationRequest, AllocationResult, MetricStatus
from coolaccess.coverage import evaluate_coverage
from coolaccess.errors import (
    FullStateMismatchError,
    InternalConsistencyError,
    StructuralMismatchError,
)
from coolaccess.metrics import (
    calculate_coverage_percentage,
    calculate_selection_change,
    compare_with_baseline,
)
from coolaccess.optimizer import optimize
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


def test_coverage_percentage_is_deterministically_rounded() -> None:
    request = make_request(
        cells=(("covered", 1, "1"), ("uncovered", 2, "1")),
        facility_ids=("A",),
        edges=(("covered", "A"),),
        k=1,
    )
    metric = calculate_coverage_percentage(evaluate_coverage(request, ("A",)))

    assert metric.status is MetricStatus.AVAILABLE
    assert metric.value == Decimal("33.333333333333")
    assert metric.numerator == 1
    assert metric.denominator == 3
    assert metric.unit == "percent"
    assert metric.proxy_label == PROXY_LABEL


def test_zero_total_demand_percentage_is_not_applicable() -> None:
    request = make_request(
        cells=(("c", 0, "1"),),
        facility_ids=("A",),
        edges=(("c", "A"),),
        k=1,
    )

    metric = calculate_coverage_percentage(evaluate_coverage(request, ("A",)))

    assert metric.status is MetricStatus.NOT_APPLICABLE
    assert metric.value is None
    assert metric.reason_code == "ZERO_TOTAL_DEMAND"
    assert metric.numerator == metric.denominator == 0


def test_baseline_comparison_reports_absolute_percentage_and_selection_change() -> None:
    request = make_request(
        cells=(("a", 100, "1"), ("b", 50, "1")),
        facility_ids=("A", "B"),
        edges=(("a", "A"), ("b", "B")),
        k=1,
    )
    optimized = optimize(request)
    baseline = evaluate_static_baseline(
        request,
        _purported_allocation(request, ("B",)),
    )

    comparison = compare_with_baseline(optimized, baseline)

    assert comparison.optimized_objective == 100
    assert comparison.baseline_objective == 50
    assert comparison.absolute_improvement == 50
    assert comparison.percentage_improvement.value == 100
    assert comparison.selection_change is not None
    assert comparison.selection_change.added_facility_ids == ("A",)
    assert comparison.selection_change.removed_facility_ids == ("B",)
    assert comparison.selection_change.changed_slot_count == 1


def test_zero_baseline_objective_percentage_is_not_applicable() -> None:
    request = make_request(
        cells=(("c", 100, "1"),),
        facility_ids=("A", "B"),
        edges=(("c", "A"),),
        k=1,
    )
    optimized = optimize(request)
    baseline = evaluate_static_baseline(
        request,
        _purported_allocation(request, ("B",)),
    )

    comparison = compare_with_baseline(optimized, baseline)

    assert comparison.absolute_improvement == 100
    assert comparison.percentage_improvement.status is MetricStatus.NOT_APPLICABLE
    assert comparison.percentage_improvement.value is None
    assert comparison.percentage_improvement.reason_code == "ZERO_BASELINE_OBJECTIVE"
    assert comparison.percentage_improvement.denominator == 0


def test_unavailable_baseline_produces_no_fabricated_comparison() -> None:
    request = make_request(
        cells=(("c", 100, "1"),),
        facility_ids=("A", "B"),
        edges=(("c", "A"),),
        k=2,
    )
    optimized = optimize(request)
    baseline = evaluate_naive_baseline(request)

    comparison = compare_with_baseline(optimized, baseline)

    assert comparison.baseline_objective is None
    assert comparison.absolute_improvement is None
    assert comparison.selection_change is None
    assert comparison.percentage_improvement.status is MetricStatus.NOT_APPLICABLE
    assert comparison.percentage_improvement.reason_code == "BASELINE_UNAVAILABLE"


def test_comparison_rejects_structural_and_full_state_mismatches() -> None:
    now = make_request(
        cells=(("c", 100, "1"),),
        facility_ids=("A",),
        edges=(("c", "A"),),
        k=1,
    )
    future = make_request(
        cells=(("c", 100, "0.5"),),
        facility_ids=("A",),
        edges=(("c", "A"),),
        k=1,
        state_id="future",
        valid_at=datetime(2026, 1, 1, 13, tzinfo=UTC),
        thermal_provenance_id="prov-thermal-future",
    )
    future_baseline = evaluate_static_baseline(future, optimize(now))
    with pytest.raises(FullStateMismatchError):
        compare_with_baseline(optimize(now), future_baseline)

    changed_population = make_request(
        cells=(("c", 101, "1"),),
        facility_ids=("A",),
        edges=(("c", "A"),),
        k=1,
    )
    changed_baseline = evaluate_static_baseline(
        changed_population,
        optimize(changed_population),
    )
    with pytest.raises(StructuralMismatchError):
        compare_with_baseline(optimize(now), changed_baseline)


def test_comparison_detects_baseline_above_purported_optimized_result() -> None:
    request = make_request(
        cells=(("c", 100, "1"),),
        facility_ids=("A",),
        edges=(("c", "A"),),
        k=1,
    )
    optimized = optimize(request)
    baseline = evaluate_static_baseline(request, optimized)
    purported = optimized.model_copy(update={"objective_value": Decimal(0)})

    with pytest.raises(InternalConsistencyError):
        compare_with_baseline(purported, baseline)


def test_selection_change_counts_slots_not_symmetric_difference_members() -> None:
    change = calculate_selection_change(("A", "C", "D"), ("A", "B"))

    assert change.added_facility_ids == ("C", "D")
    assert change.removed_facility_ids == ("B",)
    assert change.added_count == 2
    assert change.removed_count == 1
    assert change.changed_slot_count == 2


def test_large_decimal_absolute_improvement_is_not_context_rounded() -> None:
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
    baseline = evaluate_static_baseline(
        request,
        _purported_allocation(request, ("B",)),
    )

    comparison = compare_with_baseline(optimized, baseline)

    assert comparison.absolute_improvement == Decimal("123456789012345678901234567890")
