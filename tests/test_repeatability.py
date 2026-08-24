"""SYNTHETIC TEST DATA — NOT FORTYGUARD OR MUNICIPAL DATA."""

import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from coolaccess.canonical import canonical_json, full_state_fingerprint, structural_fingerprint
from coolaccess.contracts import AllocationRequest
from coolaccess.optimizer import optimize
from tests.synthetic_fixtures import make_request


def test_state_specific_thermal_changes_preserve_structural_compatibility() -> None:
    now = make_request(
        cells=(("c", "100", "0.2"),),
        facility_ids=("f",),
        edges=(("c", "f"),),
        state_id="now",
        thermal_provenance_id="thermal-now",
    )
    future = make_request(
        cells=(("c", "100", "0.8"),),
        facility_ids=("f",),
        edges=(("c", "f"),),
        state_id="future",
        valid_at=datetime(2026, 1, 1, 18, tzinfo=UTC),
        thermal_provenance_id="thermal-future",
    )
    assert structural_fingerprint(now) == structural_fingerprint(future)
    assert full_state_fingerprint(now) != full_state_fingerprint(future)


def test_each_invariant_change_breaks_structural_compatibility() -> None:
    cells = (("c", "100", "0.5"),)
    facility_ids = ("f", "g")
    edges = (("c", "f"),)
    base = make_request(cells=cells, facility_ids=facility_ids, edges=edges)
    variants = (
        make_request(
            cells=(("c", "101", "0.5"),),
            facility_ids=facility_ids,
            edges=edges,
        ),
        make_request(
            cells=cells,
            facility_ids=facility_ids,
            edges=edges,
            ineligible_facility_ids=("f",),
        ),
        make_request(cells=cells, facility_ids=facility_ids, edges=()),
        make_request(cells=cells, facility_ids=facility_ids, edges=edges, k=4),
        make_request(
            cells=cells,
            facility_ids=facility_ids,
            edges=edges,
            normalization_version="synthetic-normalization-v2",
        ),
        make_request(
            cells=cells,
            facility_ids=facility_ids,
            edges=edges,
            accessibility_version="synthetic-accessibility-v2",
        ),
    )
    base_fingerprint = structural_fingerprint(base)
    for variant in variants:
        assert structural_fingerprint(variant) != base_fingerprint


def test_invariant_provenance_version_breaks_structural_compatibility() -> None:
    base = make_request(cells=(("c", "1", "1"),), facility_ids=("f",), edges=())
    payload = base.model_dump(mode="python")
    for record in payload["provenance_registry"]:
        if record["provenance_id"] == "prov-population":
            record["transformation_version"] = "fixture-v2"
    changed = AllocationRequest.model_validate(payload)
    assert structural_fingerprint(changed) != structural_fingerprint(base)


def test_only_thermal_observation_provenance_changes_full_state() -> None:
    first = make_request(
        cells=(("c", "1", "0.5"),),
        facility_ids=("f",),
        edges=(),
        thermal_provenance_id="thermal-observation-a",
    )
    second = make_request(
        cells=(("c", "1", "0.5"),),
        facility_ids=("f",),
        edges=(),
        thermal_provenance_id="thermal-observation-b",
    )
    assert structural_fingerprint(first) == structural_fingerprint(second)
    assert full_state_fingerprint(first) != full_state_fingerprint(second)


def test_thermal_retrieval_metadata_is_full_state_only() -> None:
    base = make_request(cells=(("c", "1", "0.5"),), facility_ids=("f",), edges=())
    payload = base.model_dump(mode="python")
    for record in payload["provenance_registry"]:
        if record["scope"] == "thermal_state":
            record["source_record_id"] = "different-observation-record"
            record["retrieved_at"] = datetime(2026, 1, 1, 13, tzinfo=UTC)
    changed = AllocationRequest.model_validate(payload)
    assert structural_fingerprint(changed) == structural_fingerprint(base)
    assert full_state_fingerprint(changed) != full_state_fingerprint(base)


def test_explicit_false_and_omitted_relationship_are_structurally_equivalent() -> None:
    omitted = make_request(cells=(("c", "1", "1"),), facility_ids=("f",), edges=())
    explicit_false = make_request(
        cells=(("c", "1", "1"),), facility_ids=("f",), edges=(("c", "f", False),)
    )
    assert structural_fingerprint(omitted) == structural_fingerprint(explicit_false)
    assert full_state_fingerprint(omitted) == full_state_fingerprint(explicit_false)


def test_true_edge_provenance_assignment_is_structurally_fingerprinted() -> None:
    base = make_request(
        cells=(("c1", "1", "1"), ("c2", "1", "1")),
        facility_ids=("f",),
        edges=(("c1", "f"), ("c2", "f")),
    )
    payload = base.model_dump(mode="python")
    payload["accessibility_relationships"][0]["provenance_refs"] = ("prov-facility",)
    changed = AllocationRequest.model_validate(payload)

    assert structural_fingerprint(changed) != structural_fingerprint(base)


def test_shuffled_logical_input_has_identical_result_and_canonical_json() -> None:
    forward = make_request(
        cells=(("a", "10", "1"), ("b", "20", "0.5")),
        facility_ids=("a", "b"),
        edges=(("a", "a"), ("b", "b")),
    )
    reverse = make_request(
        cells=(("b", "20", "0.5"), ("a", "10", "1")),
        facility_ids=("b", "a"),
        edges=(("b", "b"), ("a", "a")),
    )
    result_forward = optimize(forward)
    result_reverse = optimize(reverse)
    assert result_forward == result_reverse
    assert canonical_json(result_forward) == canonical_json(result_reverse)


def test_equivalent_timezone_offsets_have_identical_full_state() -> None:
    utc_time = datetime(2026, 1, 1, 12, tzinfo=UTC)
    offset_time = utc_time.astimezone(timezone(timedelta(hours=2)))
    utc_request = make_request(
        cells=(("c", "1", "1"),),
        facility_ids=("f",),
        edges=(),
        valid_at=utc_time,
    )
    offset_request = make_request(
        cells=(("c", "1", "1"),),
        facility_ids=("f",),
        edges=(),
        valid_at=offset_time,
    )
    assert full_state_fingerprint(utc_request) == full_state_fingerprint(offset_request)


def test_canonical_result_is_independent_of_python_hash_seed() -> None:
    project_root = Path(__file__).resolve().parents[1]
    script = """
from coolaccess.canonical import canonical_json
from coolaccess.optimizer import optimize
from tests.synthetic_fixtures import make_request

request = make_request(
    cells=(("z", "10", "0.4"), ("a", "20", "0.5")),
    facility_ids=("z", "a", "m"),
    edges=(("z", "z"), ("a", "a"), ("a", "m")),
    k=2,
)
print(canonical_json(optimize(request)))
"""
    outputs: list[str] = []
    for seed in ("1", "987654"):
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = seed
        environment["PYTHONPATH"] = os.pathsep.join((str(project_root / "src"), str(project_root)))
        completed = subprocess.run(
            [sys.executable, "-B", "-c", script],
            cwd=project_root,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        outputs.append(completed.stdout.strip())
    assert outputs[0] == outputs[1]
