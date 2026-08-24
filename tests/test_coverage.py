"""SYNTHETIC TEST DATA — NOT FORTYGUARD OR MUNICIPAL DATA."""

from decimal import Decimal

import pytest

from coolaccess.coverage import evaluate_coverage
from coolaccess.errors import InvalidSelectionError
from tests.synthetic_fixtures import make_request


def test_one_facility_one_cell_coverage() -> None:
    request = make_request(cells=(("c", "100", "0.5"),), facility_ids=("f",), edges=(("c", "f"),))
    coverage = evaluate_coverage(request, ("f",))
    assert coverage.covered_heat_weighted_demand == Decimal("50")
    assert coverage.uncovered_heat_weighted_demand == 0
    assert coverage.covered_population == Decimal("100")
    assert coverage.covered_cell_ids == ("c",)


def test_union_coverage_does_not_double_count_overlap() -> None:
    request = make_request(
        cells=(("c1", "100", "1"), ("c2", "50", "0.5")),
        facility_ids=("a", "b"),
        edges=(("c1", "a"), ("c1", "b"), ("c2", "b")),
    )
    coverage = evaluate_coverage(request, ("a", "b"))
    assert coverage.covered_heat_weighted_demand == Decimal("125")
    assert coverage.covered_population == Decimal("150")
    assert coverage.multi_covered_cell_ids == ("c1",)
    assert coverage.overlap_union_heat_weighted_demand == Decimal("100")
    assert coverage.redundant_heat_weighted_demand == Decimal("100")


def test_unique_and_overlapping_contributions_are_set_relative() -> None:
    request = make_request(
        cells=(("shared", "10", "1"), ("only-a", "20", "1"), ("only-b", "30", "1")),
        facility_ids=("a", "b"),
        edges=(
            ("shared", "a"),
            ("shared", "b"),
            ("only-a", "a"),
            ("only-b", "b"),
        ),
    )
    coverage = evaluate_coverage(request, ("a", "b"))
    by_id = {item.facility_id: item for item in coverage.per_facility}
    assert by_id["a"].unique_cell_ids == ("only-a",)
    assert by_id["a"].overlapping_cell_ids == ("shared",)
    assert by_id["a"].unique_heat_weighted_demand == Decimal("20")
    assert by_id["b"].unique_cell_ids == ("only-b",)


def test_inaccessible_and_explicit_false_demand_stays_uncovered() -> None:
    request = make_request(
        cells=(("c1", "10", "1"), ("c2", "20", "1")),
        facility_ids=("f",),
        edges=(("c1", "f", False),),
    )
    coverage = evaluate_coverage(request, ("f",))
    assert coverage.covered_cell_ids == ()
    assert coverage.uncovered_cell_ids == ("c1", "c2")
    assert coverage.uncovered_heat_weighted_demand == Decimal("30")


def test_empty_selection_has_zero_coverage() -> None:
    request = make_request(cells=(("c", "10", "1"),), facility_ids=("f",), edges=(("c", "f"),))
    coverage = evaluate_coverage(request, ())
    assert coverage.covered_heat_weighted_demand == 0
    assert coverage.covered_population == 0
    assert coverage.uncovered_cell_ids == ("c",)


def test_redundancy_counts_each_extra_coverage_while_overlap_union_counts_cell_once() -> None:
    request = make_request(
        cells=(("shared", "40", "0.5"),),
        facility_ids=("a", "b", "c"),
        edges=(("shared", "a"), ("shared", "b"), ("shared", "c")),
    )
    coverage = evaluate_coverage(request, ("c", "a", "b"))
    assert coverage.covered_heat_weighted_demand == Decimal("20")
    assert coverage.overlap_union_heat_weighted_demand == Decimal("20")
    assert coverage.redundant_heat_weighted_demand == Decimal("40")
    assert coverage.overlap_union_population == Decimal("40")
    assert coverage.redundant_population == Decimal("80")
    assert tuple(item.facility_id for item in coverage.per_facility) == ("a", "b", "c")


def test_zero_priority_cell_contributes_population_but_no_weighted_demand() -> None:
    request = make_request(
        cells=(("zero-priority", "75", "0"),),
        facility_ids=("f",),
        edges=(("zero-priority", "f"),),
    )
    coverage = evaluate_coverage(request, ("f",))
    assert coverage.covered_heat_weighted_demand == 0
    assert coverage.covered_population == Decimal("75")
    assert coverage.uncovered_population == 0


@pytest.mark.parametrize(
    ("selection", "message"),
    (
        (("f", "f"), "unique"),
        (("missing",), "unknown"),
    ),
)
def test_invalid_selection_ids_fail_honestly(
    selection: tuple[str, ...],
    message: str,
) -> None:
    request = make_request(
        cells=(("c", "1", "1"),),
        facility_ids=("f",),
        edges=(("c", "f"),),
        k=2,
    )
    with pytest.raises(InvalidSelectionError, match=message):
        evaluate_coverage(request, selection)


def test_ineligible_and_over_budget_selections_fail_honestly() -> None:
    request = make_request(
        cells=(("c", "1", "1"),),
        facility_ids=("eligible", "ineligible"),
        ineligible_facility_ids=("ineligible",),
        edges=(("c", "eligible"),),
        k=1,
    )
    with pytest.raises(InvalidSelectionError, match="ineligible"):
        evaluate_coverage(request, ("ineligible",))
    with pytest.raises(InvalidSelectionError, match="resource budget"):
        evaluate_coverage(request, ("eligible", "ineligible"))
