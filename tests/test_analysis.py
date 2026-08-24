"""SYNTHETIC TEST DATA — NOT FORTYGUARD OR MUNICIPAL DATA."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from coolaccess.analysis import analyze_future_state
from coolaccess.canonical import canonical_json
from coolaccess.contracts import (
    BaselineAlgorithm,
    BaselineStatus,
    CompleteBaselineResult,
    EvidenceStatus,
    MarginalAdditionOutcome,
    MetricStatus,
)
from coolaccess.errors import StructuralMismatchError
from coolaccess.optimizer import optimize
from tests.synthetic_fixtures import make_request


def test_analysis_recalculates_future_and_returns_both_comparisons_and_evidence() -> None:
    now = make_request(
        cells=(("c1", 100, "1"), ("c2", 100, "0.1")),
        facility_ids=("A", "B"),
        edges=(("c1", "A"), ("c2", "B")),
        k=1,
    )
    future = make_request(
        cells=(("c1", 100, "0.1"), ("c2", 100, "1")),
        facility_ids=("A", "B"),
        edges=(("c1", "A"), ("c2", "B")),
        k=1,
        state_id="synthetic-future",
        valid_at=datetime(2026, 1, 1, 13, tzinfo=UTC),
        thermal_provenance_id="prov-thermal-future",
    )

    result = analyze_future_state(future, optimize(now))

    assert result.optimized.selected_facility_ids == ("B",)
    assert result.optimized_coverage_percentage.status is MetricStatus.AVAILABLE
    assert result.optimized_coverage_percentage.value == Decimal("90.909090909091")
    assert isinstance(result.static_baseline, CompleteBaselineResult)
    assert isinstance(result.naive_baseline, CompleteBaselineResult)
    assert result.static_baseline.selected_facility_ids == ("A",)
    assert result.naive_baseline.selected_facility_ids == ("B",)
    assert tuple(comparison.algorithm for comparison in result.comparisons) == (
        BaselineAlgorithm.STATIC_ALLOCATION,
        BaselineAlgorithm.NAIVE_THERMAL,
    )
    assert result.comparisons[0].absolute_improvement == 90
    assert result.comparisons[1].absolute_improvement == 0
    assert len(result.replacement_evidence) == 1
    assert result.replacement_evidence[0].selected_facility_id == "B"
    assert result.replacement_evidence[0].alternative_facility_id == "A"
    assert result.marginal_addition_evidence.status is EvidenceStatus.NOT_APPLICABLE


def test_analysis_exposes_canonical_unused_budget_marginal_evidence() -> None:
    request = make_request(
        cells=(("c1", 100, "1"), ("c2", 50, "0.5")),
        facility_ids=("C", "B", "A"),
        edges=(
            ("c1", "A"),
            ("c1", "B"),
            ("c2", "B"),
            ("c2", "C"),
        ),
        k=3,
    )

    result = analyze_future_state(request, optimize(request))

    assert result.optimized.selected_facility_ids == ("B",)
    assert result.optimized.remaining_budget == 2
    assert result.marginal_addition_evidence.status is EvidenceStatus.APPLICABLE
    assert tuple(
        evidence.unselected_facility_id for evidence in result.marginal_addition_evidence.evidence
    ) == ("A", "C")
    assert all(
        evidence.outcome is MarginalAdditionOutcome.ZERO_MARGINAL_VALUE
        for evidence in result.marginal_addition_evidence.evidence
    )
    assert tuple(
        (evidence.selected_facility_id, evidence.alternative_facility_id)
        for evidence in result.replacement_evidence
    ) == (("B", "A"), ("B", "C"))


def test_analysis_retains_unavailable_naive_baseline_without_fabricated_metric() -> None:
    request = make_request(
        cells=(("c", 100, "1"),),
        facility_ids=("A", "B"),
        edges=(("c", "A"),),
        k=2,
    )

    result = analyze_future_state(request, optimize(request))

    assert result.naive_baseline.status is BaselineStatus.UNAVAILABLE
    naive_comparison = result.comparisons[1]
    assert naive_comparison.baseline_status is BaselineStatus.UNAVAILABLE
    assert naive_comparison.baseline_objective is None
    assert naive_comparison.percentage_improvement.status is MetricStatus.NOT_APPLICABLE


def test_analysis_is_byte_stable_for_logically_identical_input_orders() -> None:
    first = make_request(
        cells=(("c2", 50, "0.5"), ("c1", 100, "1")),
        facility_ids=("C", "A", "B"),
        edges=(("c2", "C"), ("c1", "B"), ("c1", "A"), ("c2", "B")),
        k=3,
    )
    second = make_request(
        cells=(("c1", 100, "1"), ("c2", 50, "0.5")),
        facility_ids=("A", "B", "C"),
        edges=(("c2", "B"), ("c1", "A"), ("c1", "B"), ("c2", "C")),
        k=3,
    )

    first_result = analyze_future_state(first, optimize(first))
    second_result = analyze_future_state(second, optimize(second))

    assert canonical_json(first_result) == canonical_json(second_result)
    round_trip = type(first_result).model_validate_json(first_result.model_dump_json())
    assert canonical_json(round_trip) == canonical_json(first_result)


def test_analysis_rejects_structurally_incompatible_prior_allocation() -> None:
    prior_request = make_request(
        cells=(("c", 100, "1"),),
        facility_ids=("A",),
        edges=(("c", "A"),),
        k=1,
    )
    target_request = make_request(
        cells=(("c", 101, "1"),),
        facility_ids=("A",),
        edges=(("c", "A"),),
        k=1,
    )

    with pytest.raises(StructuralMismatchError):
        analyze_future_state(target_request, optimize(prior_request))
