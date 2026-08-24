"""SYNTHETIC TEST DATA — NOT FORTYGUARD OR MUNICIPAL DATA."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal

from coolaccess.contracts import (
    AccessibilityRelationship,
    AllocationRequest,
    ConfigurationReference,
    DataState,
    EligibilityStatus,
    FacilityDefinition,
    PopulationCell,
    ProvenanceRecord,
    ProvenanceScope,
    SourceKind,
)

SYNTHETIC_TEST_DATA_NOTICE = "SYNTHETIC TEST DATA — NOT FORTYGUARD OR MUNICIPAL DATA"


def make_request(
    *,
    cells: Iterable[tuple[str, str | int | Decimal, str | int | Decimal]],
    facility_ids: Iterable[str],
    edges: Iterable[tuple[str, str] | tuple[str, str, bool]],
    k: int = 3,
    state_id: str = "synthetic-state-now",
    valid_at: datetime | None = None,
    ineligible_facility_ids: Iterable[str] = (),
    normalization_version: str = "synthetic-normalization-v1",
    accessibility_version: str = "synthetic-accessibility-v1",
    thermal_provenance_id: str | None = None,
) -> AllocationRequest:
    """Build a clearly labeled provider-neutral synthetic request."""

    facility_tuple = tuple(facility_ids)
    ineligible = set(ineligible_facility_ids)
    thermal_id = thermal_provenance_id or f"prov-thermal-{state_id}"
    timestamp = valid_at or datetime(2026, 1, 1, 12, tzinfo=UTC)

    provenance = (
        ProvenanceRecord(
            provenance_id="prov-config",
            scope=ProvenanceScope.INVARIANT,
            source_kind=SourceKind.SYNTHETIC_TEST,
            source_name="Synthetic configuration fixture",
            dataset_title=SYNTHETIC_TEST_DATA_NOTICE,
            transformation_version="fixture-v1",
            data_state=DataState.SYNTHETIC_TEST,
        ),
        ProvenanceRecord(
            provenance_id="prov-population",
            scope=ProvenanceScope.INVARIANT,
            source_kind=SourceKind.SYNTHETIC_TEST,
            source_name="Synthetic population fixture",
            dataset_title=SYNTHETIC_TEST_DATA_NOTICE,
            source_vintage="synthetic",
            transformation_version="fixture-v1",
            data_state=DataState.SYNTHETIC_TEST,
        ),
        ProvenanceRecord(
            provenance_id="prov-facility",
            scope=ProvenanceScope.INVARIANT,
            source_kind=SourceKind.SYNTHETIC_TEST,
            source_name="Synthetic facility fixture",
            dataset_title=SYNTHETIC_TEST_DATA_NOTICE,
            transformation_version="fixture-v1",
            data_state=DataState.SYNTHETIC_TEST,
        ),
        ProvenanceRecord(
            provenance_id="prov-accessibility",
            scope=ProvenanceScope.INVARIANT,
            source_kind=SourceKind.SYNTHETIC_TEST,
            source_name="Synthetic accessibility fixture",
            dataset_title=SYNTHETIC_TEST_DATA_NOTICE,
            transformation_version="fixture-v1",
            data_state=DataState.SYNTHETIC_TEST,
        ),
        ProvenanceRecord(
            provenance_id=thermal_id,
            scope=ProvenanceScope.THERMAL_STATE,
            source_kind=SourceKind.SYNTHETIC_TEST,
            source_name="Synthetic thermal-priority fixture",
            dataset_title=SYNTHETIC_TEST_DATA_NOTICE,
            source_time=timestamp,
            retrieved_at=timestamp,
            transformation_version="fixture-v1",
            data_state=DataState.SYNTHETIC_TEST,
        ),
    )

    population_cells = tuple(
        PopulationCell(
            cell_id=cell_id,
            population=population,
            thermal_priority=priority,
            population_provenance_refs=("prov-population",),
            thermal_state_provenance_refs=(thermal_id,),
        )
        for cell_id, population, priority in cells
    )
    facilities = tuple(
        FacilityDefinition(
            facility_id=facility_id,
            label=f"Synthetic facility {facility_id}",
            eligibility_status=(
                EligibilityStatus.INELIGIBLE
                if facility_id in ineligible
                else EligibilityStatus.ELIGIBLE
            ),
            eligibility_reason="Synthetic eligibility rule",
            source_record_ref=f"synthetic-record-{facility_id}",
            source_provenance_refs=("prov-facility",),
            eligibility_provenance_refs=("prov-config",),
        )
        for facility_id in facility_tuple
    )
    relationships = tuple(
        AccessibilityRelationship(
            cell_id=edge[0],
            facility_id=edge[1],
            is_accessible=edge[2] if len(edge) == 3 else True,
            accessibility_configuration_id="synthetic-accessibility",
            provenance_refs=("prov-accessibility",),
        )
        for edge in edges
    )

    return AllocationRequest(
        scenario_id="synthetic-scenario",
        state_id=state_id,
        valid_at=timestamp,
        facilities=facilities,
        demand_cells=population_cells,
        accessibility_relationships=relationships,
        k=k,
        thermal_priority_reference=ConfigurationReference(
            configuration_id="synthetic-normalization",
            version=normalization_version,
            provenance_refs=("prov-config",),
        ),
        accessibility_configuration=ConfigurationReference(
            configuration_id="synthetic-accessibility",
            version=accessibility_version,
            provenance_refs=("prov-config",),
        ),
        invariant_provenance_refs=("prov-config",),
        thermal_state_provenance_refs=(thermal_id,),
        provenance_registry=provenance,
    )
