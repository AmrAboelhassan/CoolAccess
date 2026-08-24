"""SYNTHETIC TEST DATA — NOT FORTYGUARD OR MUNICIPAL DATA."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from coolaccess.canonical import canonical_json
from coolaccess.contracts import AllocationRequest, TieBreakCriterion
from coolaccess.optimizer import optimize
from tests.synthetic_fixtures import make_request


def test_exact_known_optimum() -> None:
    request = make_request(
        cells=(("c1", "100", "1"), ("c2", "80", "1"), ("c3", "10", "1")),
        facility_ids=("a", "b", "c"),
        edges=(("c1", "a"), ("c2", "b"), ("c1", "c"), ("c3", "c")),
        k=2,
    )
    result = optimize(request)
    assert result.selected_facility_ids == ("b", "c")
    assert result.objective_value == Decimal("190")


def test_k_one_and_default_k_three() -> None:
    k_one = make_request(
        cells=(("a", "10", "1"), ("b", "20", "1")),
        facility_ids=("a", "b"),
        edges=(("a", "a"), ("b", "b")),
        k=1,
    )
    assert optimize(k_one).selected_facility_ids == ("b",)

    default_k = make_request(
        cells=(("a", "10", "1"), ("b", "20", "1"), ("c", "30", "1")),
        facility_ids=("a", "b", "c"),
        edges=(("a", "a"), ("b", "b"), ("c", "c")),
    )
    result = optimize(default_k)
    assert result.k == 3
    assert result.selected_facility_ids == ("a", "b", "c")


def test_all_subsets_are_enumerated() -> None:
    request = make_request(
        cells=(("c", "1", "1"),),
        facility_ids=("a", "b", "c", "d"),
        edges=(("c", "a"),),
        k=3,
    )
    assert optimize(request).tie_break.evaluated_combination_count == 15


def test_k_above_eligible_count_is_preserved() -> None:
    request = make_request(
        cells=(("a", "10", "1"), ("b", "20", "1")),
        facility_ids=("a", "b"),
        edges=(("a", "a"), ("b", "b")),
        k=9,
    )
    result = optimize(request)
    assert result.k == 9
    assert result.selected_facility_ids == ("a", "b")
    assert result.remaining_budget == 7
    assert result.tie_break.evaluated_combination_count == 4


def test_zero_marginal_lexicographically_earlier_facility_is_not_selected() -> None:
    request = make_request(
        cells=(("shared", "1000", "0.1"), ("only-b", "10", "1")),
        facility_ids=("A", "B"),
        edges=(("shared", "A"), ("shared", "B"), ("only-b", "B")),
        k=3,
    )
    result = optimize(request)
    assert result.selected_facility_ids == ("B",)
    assert result.remaining_budget == 2
    assert result.tie_break.decisive_criterion is TieBreakCriterion.FEWER_FACILITIES


def test_population_is_secondary_comparator() -> None:
    request = make_request(
        cells=(("weighted", "10", "1"), ("zero-priority", "100", "0")),
        facility_ids=("a", "b"),
        edges=(("weighted", "a"), ("weighted", "b"), ("zero-priority", "b")),
        k=1,
    )
    result = optimize(request)
    assert result.selected_facility_ids == ("b",)
    assert result.objective_value == Decimal("10")
    assert result.coverage.covered_population == Decimal("110")
    assert result.tie_break.decisive_criterion is TieBreakCriterion.RAW_POPULATION


def test_equal_cardinality_tie_uses_stable_ids() -> None:
    request = make_request(
        cells=(("a", "10", "1"), ("b", "10", "1")),
        facility_ids=("b", "a"),
        edges=(("a", "a"), ("b", "b")),
        k=1,
    )
    result = optimize(request)
    assert result.selected_facility_ids == ("a",)
    assert result.tie_break.decisive_criterion is TieBreakCriterion.FACILITY_IDS


def test_empty_set_wins_only_when_objective_and_population_are_zero() -> None:
    zero = make_request(cells=(("c", "0", "1"),), facility_ids=("a", "b"), edges=(("c", "a"),), k=2)
    assert optimize(zero).selected_facility_ids == ()

    positive_population = make_request(
        cells=(("c", "10", "0"),),
        facility_ids=("a", "b"),
        edges=(("c", "b"),),
        k=2,
    )
    assert optimize(positive_population).selected_facility_ids == ("b",)


def test_ineligible_facility_is_never_selected() -> None:
    request = make_request(
        cells=(("c", "100", "1"),),
        facility_ids=("eligible", "ineligible"),
        edges=(("c", "ineligible"),),
        ineligible_facility_ids=("ineligible",),
    )
    assert optimize(request).selected_facility_ids == ()


def test_union_coverage_beats_independent_facility_ranking() -> None:
    request = make_request(
        cells=(("shared", "100", "1"), ("other", "90", "1")),
        facility_ids=("a", "b", "c"),
        edges=(("shared", "a"), ("shared", "b"), ("other", "c")),
        k=2,
    )
    result = optimize(request)
    assert result.selected_facility_ids in {("a", "c"), ("b", "c")}
    assert result.objective_value == Decimal("190")


def test_thermal_priority_changes_the_selected_facility() -> None:
    request = make_request(
        cells=(("cooler", "100", "0.2"), ("hotter", "100", "0.8")),
        facility_ids=("cooler-facility", "hotter-facility"),
        edges=(("cooler", "cooler-facility"), ("hotter", "hotter-facility")),
        k=1,
    )
    assert optimize(request).selected_facility_ids == ("hotter-facility",)


def test_accessibility_relationship_changes_the_selected_facility() -> None:
    request = make_request(
        cells=(("large", "100", "1"), ("small", "10", "1")),
        facility_ids=("a", "b"),
        edges=(("small", "a"), ("large", "b")),
        k=1,
    )
    assert optimize(request).selected_facility_ids == ("b",)


@pytest.mark.parametrize("invalid_k", (0, -1))
def test_non_positive_k_is_rejected(invalid_k: int) -> None:
    with pytest.raises(ValidationError, match="greater than zero"):
        make_request(
            cells=(("c", "1", "1"),),
            facility_ids=("f",),
            edges=(("c", "f"),),
            k=invalid_k,
        )


def test_logically_identical_shuffled_inputs_and_repeated_runs_are_identical() -> None:
    forward = make_request(
        cells=(("c1", "100", "0.4"), ("c2", "50", "0.8")),
        facility_ids=("a", "b", "c"),
        edges=(("c1", "a"), ("c2", "b"), ("c1", "c")),
        k=2,
    )
    shuffled = make_request(
        cells=(("c2", "50", "0.8"), ("c1", "100", "0.4")),
        facility_ids=("c", "b", "a"),
        edges=(("c1", "c"), ("c2", "b"), ("c1", "a")),
        k=2,
    )
    first = optimize(forward)
    assert optimize(forward) == first
    assert optimize(shuffled) == first
    assert canonical_json(optimize(shuffled)) == canonical_json(first)


def test_serialization_round_trip_preserves_optimizer_result() -> None:
    request = make_request(
        cells=(("c1", "100", "0.25"), ("c2", "20", "1")),
        facility_ids=("a", "b"),
        edges=(("c1", "a"), ("c2", "b")),
        k=1,
    )
    restored = AllocationRequest.model_validate_json(request.model_dump_json())
    assert restored == request
    assert optimize(restored) == optimize(request)
