"""SYNTHETIC TEST DATA — NOT FORTYGUARD OR MUNICIPAL DATA."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from coolaccess.baselines import evaluate_naive_baseline, evaluate_static_baseline
from coolaccess.canonical import structural_fingerprint
from coolaccess.contracts import BaselineStatus
from coolaccess.errors import InvalidStaticSelectionError, StructuralMismatchError
from coolaccess.optimizer import optimize
from tests.synthetic_fixtures import make_request


def test_static_baseline_recalculates_unchanged_set_for_future_thermal_state() -> None:
    now = make_request(
        cells=(("c1", 100, "1"), ("c2", 100, "0.1")),
        facility_ids=("A", "B"),
        edges=(("c1", "A"), ("c2", "B")),
        k=1,
    )
    prior = optimize(now)
    future = make_request(
        cells=(("c1", 100, "0.1"), ("c2", 100, "1")),
        facility_ids=("A", "B"),
        edges=(("c1", "A"), ("c2", "B")),
        k=1,
        state_id="synthetic-state-future",
        valid_at=datetime(2026, 1, 1, 13, tzinfo=UTC),
        thermal_provenance_id="prov-thermal-future-observation",
    )

    baseline = evaluate_static_baseline(future, prior)

    assert structural_fingerprint(now) == structural_fingerprint(future)
    assert baseline.selected_facility_ids == ("A",)
    assert baseline.objective_value == Decimal("10")
    assert baseline.source_state_id == now.state_id
    assert baseline.source_valid_at == prior.valid_at
    assert baseline.source_full_state_fingerprint == prior.full_state_fingerprint
    assert baseline.source_evidence_provenance_refs == prior.evidence_provenance_refs
    assert baseline.full_state_fingerprint != prior.full_state_fingerprint


@pytest.mark.parametrize(
    "future",
    (
        make_request(
            cells=(("c1", 101, "1"),),
            facility_ids=("A", "B"),
            edges=(("c1", "A"),),
            k=1,
        ),
        make_request(
            cells=(("c1", 100, "1"),),
            facility_ids=("A", "B"),
            edges=(("c1", "B"),),
            k=1,
        ),
        make_request(
            cells=(("c1", 100, "1"),),
            facility_ids=("A", "B"),
            edges=(("c1", "A"),),
            k=2,
        ),
        make_request(
            cells=(("c1", 100, "1"),),
            facility_ids=("A", "B"),
            edges=(("c1", "A"),),
            k=1,
            normalization_version="synthetic-normalization-v2",
        ),
        make_request(
            cells=(("c1", 100, "1"),),
            facility_ids=("A", "B"),
            edges=(("c1", "A"),),
            k=1,
            ineligible_facility_ids=("B",),
        ),
    ),
)
def test_static_baseline_rejects_invariant_changes(future: object) -> None:
    now = make_request(
        cells=(("c1", 100, "1"),),
        facility_ids=("A", "B"),
        edges=(("c1", "A"),),
        k=1,
    )
    with pytest.raises(StructuralMismatchError):
        evaluate_static_baseline(future, optimize(now))  # type: ignore[arg-type]


def test_static_baseline_rejects_ineligible_source_selection() -> None:
    request = make_request(
        cells=(("c", 100, "1"),),
        facility_ids=("A", "B"),
        edges=(("c", "A"),),
        k=1,
        ineligible_facility_ids=("B",),
    )
    valid = optimize(request)
    purported = valid.model_copy(
        update={
            "selected_facility_ids": ("B",),
            "resource_count": 1,
            "remaining_budget": 0,
        }
    )
    with pytest.raises(InvalidStaticSelectionError):
        evaluate_static_baseline(request, purported)


def test_static_baseline_rejects_internally_inconsistent_source_summary() -> None:
    request = make_request(
        cells=(("c", 100, "1"),),
        facility_ids=("A",),
        edges=(("c", "A"),),
        k=1,
    )
    purported = optimize(request).model_copy(update={"objective_value": Decimal("999")})

    with pytest.raises(InvalidStaticSelectionError, match="objective"):
        evaluate_static_baseline(request, purported)


def test_naive_baseline_uses_unweighted_cell_mean_and_ignores_overlap_population() -> None:
    request = make_request(
        cells=(("hot-tiny", 0, "1"), ("warm-large", 10000, "0.6")),
        facility_ids=("A", "B", "C"),
        edges=(
            ("hot-tiny", "A"),
            ("warm-large", "B"),
            ("warm-large", "C"),
        ),
        k=2,
    )

    baseline = evaluate_naive_baseline(request)

    assert baseline.status is BaselineStatus.COMPLETE
    assert baseline.selected_facility_ids == ("A", "B")
    scores = {score.facility_id: score for score in baseline.facility_scores}
    assert scores["A"].mean_thermal_priority == Decimal("1")
    assert scores["A"].accessible_cell_count == 1
    assert scores["A"].observation_unit == "population_cell_phase1_provisional"
    assert scores["B"].mean_thermal_priority == scores["C"].mean_thermal_priority
    assert baseline.coverage.covered_population == Decimal("10000")


def test_naive_baseline_is_unavailable_when_too_few_facilities_are_scoreable() -> None:
    request = make_request(
        cells=(("c", 100, "0.7"),),
        facility_ids=("A", "B"),
        edges=(("c", "A"),),
        k=2,
    )

    baseline = evaluate_naive_baseline(request)

    assert baseline.status is BaselineStatus.UNAVAILABLE
    assert baseline.unavailable_reason == "INSUFFICIENT_SCOREABLE_FACILITIES"
    assert baseline.unavailable_facility_ids == ("B",)
    score = baseline.facility_scores[1]
    assert score.facility_id == "B"
    assert score.mean_thermal_priority is None
    assert not score.is_available


def test_naive_baseline_allows_k_greater_than_eligible_count_without_rewriting_k() -> None:
    request = make_request(
        cells=(("c1", 10, "0.8"), ("c2", 10, "0.4")),
        facility_ids=("A", "B", "X"),
        ineligible_facility_ids=("X",),
        edges=(("c1", "A"), ("c2", "B")),
        k=5,
    )

    baseline = evaluate_naive_baseline(request)

    assert baseline.status is BaselineStatus.COMPLETE
    assert baseline.k == 5
    assert baseline.selected_facility_ids == ("A", "B")
    assert baseline.resource_count == 2
    assert baseline.remaining_budget == 3


def test_naive_baseline_ranks_repeating_means_by_exact_sum_count_ratio() -> None:
    request = make_request(
        cells=(
            ("a-cell", 1, "0.33333333333333333333333333332"),
            ("z-hot", 1, "1"),
            ("z-zero-1", 1, "0"),
            ("z-zero-2", 1, "0"),
        ),
        facility_ids=("A", "Z"),
        edges=(
            ("a-cell", "A"),
            ("z-hot", "Z"),
            ("z-zero-1", "Z"),
            ("z-zero-2", "Z"),
        ),
        k=1,
    )

    baseline = evaluate_naive_baseline(request)

    assert baseline.status is BaselineStatus.COMPLETE
    assert baseline.selected_facility_ids == ("Z",)
    scores = {score.facility_id: score for score in baseline.facility_scores}
    assert scores["Z"].thermal_priority_sum == Decimal("1")
    assert scores["Z"].accessible_cell_count == 3


def test_static_baseline_preserves_less_than_k_selection_and_remaining_budget() -> None:
    now = make_request(
        cells=(("c", 100, "1"),),
        facility_ids=("A", "B"),
        edges=(("c", "A"), ("c", "B")),
        k=3,
    )
    prior = optimize(now)
    future = now.model_copy(
        update={
            "state_id": "synthetic-future",
            "valid_at": now.valid_at + timedelta(hours=1),
        }
    )

    baseline = evaluate_static_baseline(future, prior)

    assert prior.resource_count == 1
    assert baseline.selected_facility_ids == prior.selected_facility_ids
    assert baseline.remaining_budget == 2
