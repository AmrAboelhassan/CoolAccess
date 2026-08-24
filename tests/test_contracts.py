"""SYNTHETIC TEST DATA — NOT FORTYGUARD OR MUNICIPAL DATA."""

from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from coolaccess.contracts import (
    AllocationRequest,
    AllocationResult,
    PopulationCell,
    ProvenanceScope,
)
from coolaccess.optimizer import optimize
from tests.synthetic_fixtures import make_request


def test_population_cell_computes_and_round_trips_derived_demand() -> None:
    request = make_request(cells=(("c", "10", "0.25"),), facility_ids=("f",), edges=())
    cell = request.demand_cells[0]
    assert cell.heat_weighted_demand == Decimal("2.5")
    assert PopulationCell.model_validate_json(cell.model_dump_json()) == cell


def test_contradictory_derived_demand_fails() -> None:
    with pytest.raises(ValidationError, match="does not match"):
        PopulationCell(
            cell_id="c",
            population="10",
            thermal_priority="0.25",
            heat_weighted_demand="99",
            population_provenance_refs=("p",),
            thermal_state_provenance_refs=("t",),
        )


@pytest.mark.parametrize("priority", ["-0.01", "1.01", "NaN", "Infinity"])
def test_invalid_thermal_priority_fails(priority: str) -> None:
    with pytest.raises((ValidationError, ValueError)):
        PopulationCell(
            cell_id="c",
            population="10",
            thermal_priority=priority,
            population_provenance_refs=("p",),
            thermal_state_provenance_refs=("t",),
        )


def test_negative_population_fails() -> None:
    with pytest.raises(ValidationError, match="non-negative"):
        PopulationCell(
            cell_id="c",
            population="-1",
            thermal_priority="0.5",
            population_provenance_refs=("p",),
            thermal_state_provenance_refs=("t",),
        )


def test_k_greater_than_eligible_count_is_valid_and_preserved() -> None:
    request = make_request(cells=(("c", "10", "1"),), facility_ids=("f",), edges=(("c", "f"),), k=9)
    assert request.k == 9


@pytest.mark.parametrize("k", [0, -1])
def test_non_positive_k_fails(k: int) -> None:
    with pytest.raises(ValidationError, match="greater than zero"):
        make_request(cells=(("c", "1", "1"),), facility_ids=("f",), edges=(), k=k)


def test_duplicate_and_contradictory_relationships_fail() -> None:
    with pytest.raises(ValidationError, match="contradictory"):
        make_request(
            cells=(("c", "1", "1"),),
            facility_ids=("f",),
            edges=(("c", "f", True), ("c", "f", False)),
        )


def test_duplicate_relationship_with_the_same_flag_fails() -> None:
    with pytest.raises(ValidationError, match="duplicate accessibility"):
        make_request(
            cells=(("c", "1", "1"),),
            facility_ids=("f",),
            edges=(("c", "f", True), ("c", "f", True)),
        )


@pytest.mark.parametrize(
    ("cells", "facility_ids", "message"),
    (
        ((), ("f",), "at least one demand cell"),
        ((("c", "1", "1"),), (), "at least one facility"),
    ),
)
def test_empty_domain_collections_fail(
    cells: tuple[tuple[str, str, str], ...],
    facility_ids: tuple[str, ...],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        make_request(cells=cells, facility_ids=facility_ids, edges=())


def test_no_eligible_facility_fails() -> None:
    with pytest.raises(ValidationError, match="at least one eligible"):
        make_request(
            cells=(("c", "1", "1"),),
            facility_ids=("f",),
            ineligible_facility_ids=("f",),
            edges=(),
        )


@pytest.mark.parametrize(
    ("cells", "facility_ids", "message"),
    (
        (
            (("c", "1", "1"), ("c", "2", "0.5")),
            ("f",),
            "duplicate population-cell IDs",
        ),
        (
            (("c", "1", "1"),),
            ("f", "f"),
            "duplicate facility IDs",
        ),
    ),
)
def test_duplicate_domain_ids_fail(
    cells: tuple[tuple[str, str, str], ...],
    facility_ids: tuple[str, ...],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        make_request(cells=cells, facility_ids=facility_ids, edges=())


@pytest.mark.parametrize("population", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_population_fails(population: str) -> None:
    with pytest.raises((ValidationError, ValueError), match="finite"):
        make_request(
            cells=(("c", population, "0.5"),),
            facility_ids=("f",),
            edges=(),
        )


def test_relationship_unknown_endpoint_fails() -> None:
    with pytest.raises(ValidationError, match="unknown endpoint"):
        make_request(
            cells=(("c", "1", "1"),),
            facility_ids=("f",),
            edges=(("unknown", "f"),),
        )


def test_discrete_inputs_do_not_coerce_booleans_or_truthy_strings() -> None:
    with pytest.raises(ValidationError):
        make_request(
            cells=(("c", "1", "1"),),
            facility_ids=("f",),
            edges=(),
            k=True,
        )
    with pytest.raises(ValidationError):
        make_request(
            cells=(("c", "1", "1"),),
            facility_ids=("f",),
            edges=(("c", "f", "yes"),),  # type: ignore[arg-type]
        )


def test_naive_timestamp_fails() -> None:
    valid = make_request(cells=(("c", "1", "1"),), facility_ids=("f",), edges=())
    payload = valid.model_dump(mode="python")
    payload["valid_at"] = datetime(2026, 1, 1, 12)
    with pytest.raises(ValidationError):
        AllocationRequest.model_validate(payload)


def test_request_collections_are_canonical() -> None:
    request = make_request(
        cells=(("z", "1", "1"), ("a", "1", "1")),
        facility_ids=("z", "a"),
        edges=(("z", "z"), ("a", "a")),
    )
    assert tuple(cell.cell_id for cell in request.demand_cells) == ("a", "z")
    assert tuple(facility.facility_id for facility in request.facilities) == ("a", "z")


@pytest.mark.parametrize(
    ("provenance_id", "wrong_scope", "expected_scope"),
    [
        ("prov-config", ProvenanceScope.THERMAL_STATE, "invariant"),
        ("prov-thermal-synthetic-state-now", ProvenanceScope.INVARIANT, "thermal_state"),
    ],
)
def test_provenance_roles_are_enforced(
    provenance_id: str,
    wrong_scope: ProvenanceScope,
    expected_scope: str,
) -> None:
    request = make_request(cells=(("c", "1", "1"),), facility_ids=("f",), edges=())
    payload = request.model_dump(mode="python")
    for record in payload["provenance_registry"]:
        if record["provenance_id"] == provenance_id:
            record["scope"] = wrong_scope
    with pytest.raises(ValidationError, match=f"expected {expected_scope}"):
        AllocationRequest.model_validate(payload)


def test_contracts_are_frozen_and_forbid_extra_fields() -> None:
    request = make_request(cells=(("c", "1", "1"),), facility_ids=("f",), edges=())
    with pytest.raises(ValidationError, match="frozen"):
        request.k = 4  # type: ignore[misc]

    payload = request.model_dump(mode="python")
    payload["unexpected"] = "not allowed"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AllocationRequest.model_validate(payload)


def test_allocation_result_rejects_an_objective_coverage_mismatch() -> None:
    request = make_request(
        cells=(("c", "10", "1"),),
        facility_ids=("f",),
        edges=(("c", "f"),),
    )
    payload = optimize(request).model_dump(mode="python")
    payload["objective_value"] = Decimal("999")

    with pytest.raises(ValidationError, match="objective_value"):
        AllocationResult.model_validate(payload)
