"""Canonical serialization and request fingerprints."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel

from coolaccess.contracts import AllocationRequest, ProvenanceRecord
from coolaccess.demand import canonical_decimal


def canonical_decimal_string(value: Decimal) -> str:
    """Serialize a Decimal without exponent or insignificant trailing zeroes."""

    canonical = canonical_decimal(value)
    rendered = format(canonical, "f")
    return "0" if rendered in {"-0", ""} else rendered


def _canonical_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _canonical_value(value.model_dump(mode="python"))
    if isinstance(value, Decimal):
        return canonical_decimal_string(value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("canonical timestamps must be timezone-aware")
        normalized = value.astimezone(UTC)
        return normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _canonical_value(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (tuple, list)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, set):
        return [_canonical_value(item) for item in sorted(value)]
    return value


def canonical_json(value: Any) -> str:
    """Return byte-stable canonical JSON for supported domain values."""

    return json.dumps(
        _canonical_value(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_json_dumps(value: Any) -> str:
    """Compatibility name making the string return type explicit."""

    return canonical_json(value)


def canonical_json_bytes(value: Any) -> bytes:
    """Return the UTF-8 bytes used for stable hashing and comparisons."""

    return canonical_json(value).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _all_invariant_refs(request: AllocationRequest) -> tuple[str, ...]:
    references: set[str] = set(request.invariant_provenance_refs)
    references.update(request.thermal_priority_reference.provenance_refs)
    references.update(request.accessibility_configuration.provenance_refs)
    for facility in request.facilities:
        references.update(facility.source_provenance_refs)
        references.update(facility.eligibility_provenance_refs)
    for cell in request.demand_cells:
        references.update(cell.population_provenance_refs)
        references.update(cell.geometry_provenance_refs)
    for relationship in request.accessibility_relationships:
        if relationship.is_accessible:
            references.update(relationship.provenance_refs)
    return tuple(sorted(references))


def _all_thermal_refs(request: AllocationRequest) -> tuple[str, ...]:
    references: set[str] = set(request.thermal_state_provenance_refs)
    for cell in request.demand_cells:
        references.update(cell.thermal_state_provenance_refs)
    return tuple(sorted(references))


def _invariant_provenance_projection(record: ProvenanceRecord) -> dict[str, Any]:
    return {
        "provenance_id": record.provenance_id,
        "scope": record.scope,
        "source_kind": record.source_kind,
        "source_name": record.source_name,
        "dataset_title": record.dataset_title,
        "source_reference": record.source_reference,
        "source_record_id": record.source_record_id,
        "license_reference": record.license_reference,
        "source_vintage": record.source_vintage,
        "transformation_version": record.transformation_version,
    }


def structural_payload(request: AllocationRequest) -> dict[str, Any]:
    """Return only NOW/FUTURE invariant decision inputs."""

    registry = {record.provenance_id: record for record in request.provenance_registry}
    invariant_records = tuple(
        _invariant_provenance_projection(registry[reference])
        for reference in _all_invariant_refs(request)
    )
    return {
        "scenario_id": request.scenario_id,
        "k": request.k,
        "facilities": tuple(
            {
                "facility_id": facility.facility_id,
                "eligibility_status": facility.eligibility_status,
                "source_provenance_refs": facility.source_provenance_refs,
                "eligibility_provenance_refs": facility.eligibility_provenance_refs,
            }
            for facility in request.facilities
        ),
        "population_cells": tuple(
            {
                "cell_id": cell.cell_id,
                "population": cell.population,
                "population_provenance_refs": cell.population_provenance_refs,
                "geometry_provenance_refs": cell.geometry_provenance_refs,
            }
            for cell in request.demand_cells
        ),
        "true_accessibility_relationships": tuple(
            {
                "cell_id": relationship.cell_id,
                "facility_id": relationship.facility_id,
                "provenance_refs": relationship.provenance_refs,
            }
            for relationship in request.accessibility_relationships
            if relationship.is_accessible
        ),
        "accessibility_configuration": request.accessibility_configuration,
        "thermal_priority_reference": request.thermal_priority_reference,
        "invariant_provenance": invariant_records,
    }


def structural_fingerprint(request: AllocationRequest) -> str:
    return canonical_sha256(structural_payload(request))


def full_state_payload(request: AllocationRequest) -> dict[str, Any]:
    """Extend the invariant payload with state-specific thermal evidence."""

    registry = {record.provenance_id: record for record in request.provenance_registry}
    thermal_records = tuple(registry[reference] for reference in _all_thermal_refs(request))
    return {
        "structural": structural_payload(request),
        "state_id": request.state_id,
        "valid_at": request.valid_at,
        "thermal_cells": tuple(
            {
                "cell_id": cell.cell_id,
                "thermal_priority": cell.thermal_priority,
                "heat_weighted_demand": cell.heat_weighted_demand,
                "thermal_state_provenance_refs": cell.thermal_state_provenance_refs,
            }
            for cell in request.demand_cells
        ),
        "thermal_state_provenance_refs": request.thermal_state_provenance_refs,
        "thermal_state_provenance": thermal_records,
    }


def full_state_fingerprint(request: AllocationRequest) -> str:
    return canonical_sha256(full_state_payload(request))


def evidence_provenance_refs(request: AllocationRequest) -> tuple[str, ...]:
    """Return every provenance record actually referenced by deterministic inputs."""

    return tuple(sorted({*_all_invariant_refs(request), *_all_thermal_refs(request)}))
