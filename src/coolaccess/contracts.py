"""Provider-neutral immutable contracts for the CoolAccess deterministic core."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    field_validator,
    model_validator,
)

from coolaccess.demand import as_finite_decimal, calculate_heat_weighted_demand

PROXY_LABEL = "SCENARIO_SPECIFIC_PLANNING_GEOGRAPHIC_ACCESSIBILITY_PROXY"
ALGORITHM_VERSION = "phase1-exhaustive-v1"


class EligibilityStatus(StrEnum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"


class BaselineAlgorithm(StrEnum):
    STATIC_ALLOCATION = "static_allocation"
    NAIVE_THERMAL = "naive_thermal"


class BaselineStatus(StrEnum):
    COMPLETE = "complete"
    UNAVAILABLE = "unavailable"


class MetricStatus(StrEnum):
    AVAILABLE = "available"
    NOT_APPLICABLE = "not_applicable"


class EvidenceStatus(StrEnum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"


class TieBreakCriterion(StrEnum):
    HEAT_WEIGHTED_DEMAND = "heat_weighted_demand"
    RAW_POPULATION = "raw_population"
    FEWER_FACILITIES = "fewer_facilities"
    FACILITY_IDS = "facility_ids"


class ReplacementComparatorOutcome(StrEnum):
    ORIGINAL_PREFERRED = "original_preferred"
    REPLACEMENT_PREFERRED = "replacement_preferred"
    COMPARATOR_EQUIVALENT = "comparator_equivalent"


class ReplacementReasonCode(StrEnum):
    PRIMARY_OBJECTIVE_LOSS = "primary_objective_loss"
    POPULATION_TIE_BREAK_LOSS = "population_tie_break_loss"
    STABLE_ID_TIE_BREAK_LOSS = "stable_id_tie_break_loss"
    COMPARATOR_EQUIVALENT = "comparator_equivalent"
    REPLACEMENT_PRIMARY_OBJECTIVE_WIN = "replacement_primary_objective_win"
    REPLACEMENT_POPULATION_TIE_BREAK_WIN = "replacement_population_tie_break_win"
    REPLACEMENT_STABLE_ID_TIE_BREAK_WIN = "replacement_stable_id_tie_break_win"


class MarginalAdditionOutcome(StrEnum):
    ZERO_MARGINAL_VALUE = "zero_marginal_value"
    POPULATION_ONLY_MARGINAL_VALUE = "population_only_marginal_value"
    POSITIVE_MARGINAL_OBJECTIVE = "positive_marginal_objective"


class MarginalAdditionNotApplicableReason(StrEnum):
    RESOURCE_BUDGET_FULL = "resource_budget_full"
    NO_ELIGIBLE_UNSELECTED_FACILITIES = "no_eligible_unselected_facilities"


class DataState(StrEnum):
    STATIC = "static"
    LIVE = "live"
    CACHED = "cached"
    STALE = "stale"
    PREPARED = "prepared"
    SYNTHETIC_TEST = "synthetic_test"


class SourceKind(StrEnum):
    POPULATION = "population"
    THERMAL_PRIORITY = "thermal_priority"
    FACILITY = "facility"
    ACCESSIBILITY = "accessibility"
    CONFIGURATION = "configuration"
    DERIVED = "derived"
    SYNTHETIC_TEST = "synthetic_test"


class ProvenanceScope(StrEnum):
    INVARIANT = "invariant"
    THERMAL_STATE = "thermal_state"


class RedactionState(StrEnum):
    NONE = "none"
    REDACTED = "redacted"


class FrozenModel(BaseModel):
    """Shared immutable strict-output behavior."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_default=True,
        allow_inf_nan=False,
    )


def _validate_text(value: str, *, field_name: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{field_name} must be non-empty")
    if value != value.strip():
        raise ValueError(f"{field_name} must not contain surrounding whitespace")
    if any(ord(character) < 32 for character in value):
        raise ValueError(f"{field_name} must not contain control characters")
    return value


def _canonical_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    for value in values:
        _validate_text(value, field_name="reference")
    if len(set(values)) != len(values):
        raise ValueError("references must be unique")
    return tuple(sorted(values))


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


class ProvenanceRecord(FrozenModel):
    provenance_id: str
    scope: ProvenanceScope
    source_kind: SourceKind
    source_name: str
    dataset_title: str | None = None
    source_reference: str | None = None
    source_record_id: str | None = None
    license_reference: str | None = None
    source_vintage: str | None = None
    source_time: AwareDatetime | None = None
    retrieved_at: AwareDatetime | None = None
    transformation_version: str | None = None
    data_state: DataState = DataState.STATIC
    redaction_state: RedactionState = RedactionState.NONE
    redaction_note: str | None = None
    warning_codes: tuple[str, ...] = ()

    @field_validator("provenance_id", "source_name")
    @classmethod
    def validate_required_text(cls, value: str, info: Any) -> str:
        return _validate_text(value, field_name=info.field_name)

    @field_validator(
        "dataset_title",
        "source_reference",
        "source_record_id",
        "license_reference",
        "source_vintage",
        "transformation_version",
        "redaction_note",
    )
    @classmethod
    def validate_optional_text(cls, value: str | None, info: Any) -> str | None:
        return None if value is None else _validate_text(value, field_name=info.field_name)

    @field_validator("source_time", "retrieved_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _utc(value)

    @field_validator("warning_codes")
    @classmethod
    def canonicalize_warning_codes(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _canonical_ids(values)

    @model_validator(mode="after")
    def validate_redaction(self) -> Self:
        if self.redaction_state is RedactionState.REDACTED and self.redaction_note is None:
            raise ValueError("redaction_note is required when redaction_state is redacted")
        return self


class ConfigurationReference(FrozenModel):
    configuration_id: str
    version: str
    provenance_refs: tuple[str, ...]

    @field_validator("configuration_id", "version")
    @classmethod
    def validate_text(cls, value: str, info: Any) -> str:
        return _validate_text(value, field_name=info.field_name)

    @field_validator("provenance_refs")
    @classmethod
    def canonicalize_refs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if not values:
            raise ValueError("configuration provenance_refs must not be empty")
        return _canonical_ids(values)


class PopulationCell(FrozenModel):
    cell_id: str
    population: Decimal
    thermal_priority: Decimal
    heat_weighted_demand: Decimal | None = None
    geometry_ref: str | None = None
    population_provenance_refs: tuple[str, ...]
    geometry_provenance_refs: tuple[str, ...] = ()
    thermal_state_provenance_refs: tuple[str, ...]

    @field_validator("cell_id")
    @classmethod
    def validate_cell_id(cls, value: str) -> str:
        return _validate_text(value, field_name="cell_id")

    @field_validator("geometry_ref")
    @classmethod
    def validate_geometry_ref(cls, value: str | None) -> str | None:
        return None if value is None else _validate_text(value, field_name="geometry_ref")

    @field_validator("population", "thermal_priority", "heat_weighted_demand", mode="before")
    @classmethod
    def validate_decimal(cls, value: Any) -> Decimal | None:
        return None if value is None else as_finite_decimal(value)

    @field_validator(
        "population_provenance_refs",
        "geometry_provenance_refs",
        "thermal_state_provenance_refs",
    )
    @classmethod
    def canonicalize_refs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _canonical_ids(values)

    @model_validator(mode="after")
    def calculate_and_validate_demand(self) -> Self:
        if self.population < 0:
            raise ValueError("population must be non-negative")
        if self.thermal_priority < 0 or self.thermal_priority > 1:
            raise ValueError("thermal_priority must be in the inclusive range [0, 1]")
        if not self.population_provenance_refs:
            raise ValueError("population_provenance_refs must not be empty")
        if not self.thermal_state_provenance_refs:
            raise ValueError("thermal_state_provenance_refs must not be empty")
        calculated = calculate_heat_weighted_demand(self.population, self.thermal_priority)
        if self.heat_weighted_demand is not None and self.heat_weighted_demand != calculated:
            raise ValueError(
                "heat_weighted_demand does not match population times thermal_priority"
            )
        object.__setattr__(self, "heat_weighted_demand", calculated)
        return self


class FacilityDefinition(FrozenModel):
    facility_id: str
    label: str
    eligibility_status: EligibilityStatus
    eligibility_reason: str
    location_ref: str | None = None
    source_record_ref: str | None = None
    source_provenance_refs: tuple[str, ...]
    eligibility_provenance_refs: tuple[str, ...]

    @field_validator("facility_id", "label", "eligibility_reason")
    @classmethod
    def validate_required_text(cls, value: str, info: Any) -> str:
        return _validate_text(value, field_name=info.field_name)

    @field_validator("location_ref", "source_record_ref")
    @classmethod
    def validate_optional_text(cls, value: str | None, info: Any) -> str | None:
        return None if value is None else _validate_text(value, field_name=info.field_name)

    @field_validator("source_provenance_refs", "eligibility_provenance_refs")
    @classmethod
    def canonicalize_refs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if not values:
            raise ValueError("facility provenance references must not be empty")
        return _canonical_ids(values)


class AccessibilityRelationship(FrozenModel):
    cell_id: str
    facility_id: str
    is_accessible: StrictBool
    accessibility_configuration_id: str
    provenance_refs: tuple[str, ...]

    @field_validator("cell_id", "facility_id", "accessibility_configuration_id")
    @classmethod
    def validate_text(cls, value: str, info: Any) -> str:
        return _validate_text(value, field_name=info.field_name)

    @field_validator("provenance_refs")
    @classmethod
    def canonicalize_refs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if not values:
            raise ValueError("accessibility provenance_refs must not be empty")
        return _canonical_ids(values)


class AllocationRequest(FrozenModel):
    scenario_id: str
    state_id: str
    valid_at: AwareDatetime
    facilities: tuple[FacilityDefinition, ...]
    demand_cells: tuple[PopulationCell, ...]
    accessibility_relationships: tuple[AccessibilityRelationship, ...] = ()
    k: StrictInt = 3
    thermal_priority_reference: ConfigurationReference
    accessibility_configuration: ConfigurationReference
    invariant_provenance_refs: tuple[str, ...] = ()
    thermal_state_provenance_refs: tuple[str, ...] = ()
    provenance_registry: tuple[ProvenanceRecord, ...]

    @field_validator("scenario_id", "state_id")
    @classmethod
    def validate_text(cls, value: str, info: Any) -> str:
        return _validate_text(value, field_name=info.field_name)

    @field_validator("valid_at")
    @classmethod
    def normalize_valid_at(cls, value: datetime) -> datetime:
        return _utc(value)

    @field_validator("invariant_provenance_refs", "thermal_state_provenance_refs")
    @classmethod
    def canonicalize_refs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _canonical_ids(values)

    @model_validator(mode="after")
    def validate_and_canonicalize(self) -> Self:
        if self.k <= 0:
            raise ValueError("k must be greater than zero")
        if not self.facilities:
            raise ValueError("at least one facility is required")
        if not self.demand_cells:
            raise ValueError("at least one demand cell is required")
        if not any(
            facility.eligibility_status is EligibilityStatus.ELIGIBLE
            for facility in self.facilities
        ):
            raise ValueError("at least one eligible facility is required")

        facility_ids = [facility.facility_id for facility in self.facilities]
        cell_ids = [cell.cell_id for cell in self.demand_cells]
        provenance_ids = [record.provenance_id for record in self.provenance_registry]
        for values, label in (
            (facility_ids, "facility IDs"),
            (cell_ids, "population-cell IDs"),
            (provenance_ids, "provenance IDs"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {label} are not allowed")

        known_facilities = set(facility_ids)
        known_cells = set(cell_ids)
        pair_flags: dict[tuple[str, str], bool] = {}
        for edge in self.accessibility_relationships:
            if edge.facility_id not in known_facilities or edge.cell_id not in known_cells:
                raise ValueError("accessibility relationship references an unknown endpoint")
            if (
                edge.accessibility_configuration_id
                != self.accessibility_configuration.configuration_id
            ):
                raise ValueError("accessibility relationship uses a different configuration")
            pair = (edge.cell_id, edge.facility_id)
            if pair in pair_flags:
                if pair_flags[pair] != edge.is_accessible:
                    raise ValueError("contradictory accessibility relationships are not allowed")
                raise ValueError("duplicate accessibility relationships are not allowed")
            pair_flags[pair] = edge.is_accessible

        registry = {record.provenance_id: record for record in self.provenance_registry}
        invariant_refs: list[str] = [*self.invariant_provenance_refs]
        thermal_refs: list[str] = [*self.thermal_state_provenance_refs]
        invariant_refs.extend(self.thermal_priority_reference.provenance_refs)
        invariant_refs.extend(self.accessibility_configuration.provenance_refs)
        for facility in self.facilities:
            invariant_refs.extend(facility.source_provenance_refs)
            invariant_refs.extend(facility.eligibility_provenance_refs)
        for cell in self.demand_cells:
            invariant_refs.extend(cell.population_provenance_refs)
            invariant_refs.extend(cell.geometry_provenance_refs)
            thermal_refs.extend(cell.thermal_state_provenance_refs)
        for edge in self.accessibility_relationships:
            invariant_refs.extend(edge.provenance_refs)

        for reference, expected_scope in (
            *((reference, ProvenanceScope.INVARIANT) for reference in invariant_refs),
            *((reference, ProvenanceScope.THERMAL_STATE) for reference in thermal_refs),
        ):
            record = registry.get(reference)
            if record is None:
                raise ValueError(f"unresolved provenance reference: {reference}")
            if record.scope is not expected_scope:
                raise ValueError(
                    f"provenance reference {reference} has scope {record.scope.value}; "
                    f"expected {expected_scope.value}"
                )

        object.__setattr__(
            self,
            "facilities",
            tuple(sorted(self.facilities, key=lambda item: item.facility_id)),
        )
        object.__setattr__(
            self,
            "demand_cells",
            tuple(sorted(self.demand_cells, key=lambda item: item.cell_id)),
        )
        object.__setattr__(
            self,
            "accessibility_relationships",
            tuple(
                sorted(
                    self.accessibility_relationships,
                    key=lambda x: (x.cell_id, x.facility_id),
                )
            ),
        )
        object.__setattr__(
            self,
            "provenance_registry",
            tuple(sorted(self.provenance_registry, key=lambda x: x.provenance_id)),
        )
        return self


class FacilityCoverage(FrozenModel):
    facility_id: str
    direct_cell_ids: tuple[str, ...]
    direct_heat_weighted_demand: Decimal
    direct_population: Decimal
    unique_cell_ids: tuple[str, ...]
    unique_heat_weighted_demand: Decimal
    unique_population: Decimal
    overlapping_cell_ids: tuple[str, ...]
    overlapping_heat_weighted_demand: Decimal
    overlapping_population: Decimal


class CoverageSummary(FrozenModel):
    total_heat_weighted_demand: Decimal
    covered_heat_weighted_demand: Decimal
    uncovered_heat_weighted_demand: Decimal
    total_population: Decimal
    covered_population: Decimal
    uncovered_population: Decimal
    covered_cell_ids: tuple[str, ...]
    uncovered_cell_ids: tuple[str, ...]
    multi_covered_cell_ids: tuple[str, ...]
    overlap_union_heat_weighted_demand: Decimal
    overlap_union_population: Decimal
    redundant_heat_weighted_demand: Decimal
    redundant_population: Decimal
    per_facility: tuple[FacilityCoverage, ...]
    proxy_label: str = PROXY_LABEL


class TieBreakInfo(FrozenModel):
    evaluated_combination_count: int
    decisive_criterion: TieBreakCriterion
    selected_facility_ids: tuple[str, ...]
    selected_count: int
    primary_tied_count: int
    population_tied_count: int
    cardinality_tied_count: int
    comparator_order: tuple[TieBreakCriterion, ...] = (
        TieBreakCriterion.HEAT_WEIGHTED_DEMAND,
        TieBreakCriterion.RAW_POPULATION,
        TieBreakCriterion.FEWER_FACILITIES,
        TieBreakCriterion.FACILITY_IDS,
    )
    algorithm_version: str = ALGORITHM_VERSION


class AllocationResult(FrozenModel):
    scenario_id: str
    state_id: str
    valid_at: AwareDatetime
    k: int
    selected_facility_ids: tuple[str, ...]
    objective_value: Decimal
    coverage: CoverageSummary
    resource_count: int
    remaining_budget: int
    tie_break: TieBreakInfo
    algorithm_version: str = ALGORITHM_VERSION
    structural_fingerprint: str
    full_state_fingerprint: str
    evidence_provenance_refs: tuple[str, ...]

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        if self.k <= 0:
            raise ValueError("k must be greater than zero")
        if self.selected_facility_ids != _canonical_ids(self.selected_facility_ids):
            raise ValueError("selected facility IDs must be in canonical order")
        if self.resource_count != len(self.selected_facility_ids):
            raise ValueError("resource_count must equal the selected facility count")
        if self.resource_count > self.k:
            raise ValueError("resource_count must not exceed k")
        if self.remaining_budget != self.k - self.resource_count:
            raise ValueError("remaining_budget must equal k minus resource_count")
        if self.objective_value != self.coverage.covered_heat_weighted_demand:
            raise ValueError("objective_value must equal covered heat-weighted demand")
        if self.tie_break.selected_facility_ids != self.selected_facility_ids:
            raise ValueError("tie-break winner must match selected facility IDs")
        if self.tie_break.selected_count != self.resource_count:
            raise ValueError("tie-break selected_count must match resource_count")
        return self


class FacilityThermalScore(FrozenModel):
    facility_id: str
    accessible_cell_count: int
    thermal_priority_sum: Decimal | None
    mean_thermal_priority: Decimal | None
    is_available: bool
    unavailable_reason: str | None = None
    observation_unit: str = "population_cell_phase1_provisional"


class CompleteBaselineResult(FrozenModel):
    status: Literal[BaselineStatus.COMPLETE] = BaselineStatus.COMPLETE
    algorithm: BaselineAlgorithm
    scenario_id: str
    state_id: str
    valid_at: AwareDatetime
    k: int
    selected_facility_ids: tuple[str, ...]
    objective_value: Decimal
    coverage: CoverageSummary
    resource_count: int
    remaining_budget: int
    structural_fingerprint: str
    full_state_fingerprint: str
    source_state_id: str | None = None
    source_valid_at: AwareDatetime | None = None
    source_selected_facility_ids: tuple[str, ...] = ()
    source_full_state_fingerprint: str | None = None
    source_evidence_provenance_refs: tuple[str, ...] = ()
    facility_scores: tuple[FacilityThermalScore, ...] = ()
    algorithm_version: str = ALGORITHM_VERSION

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        if self.k <= 0:
            raise ValueError("k must be greater than zero")
        if self.selected_facility_ids != _canonical_ids(self.selected_facility_ids):
            raise ValueError("baseline facility IDs must be in canonical order")
        if self.resource_count != len(self.selected_facility_ids):
            raise ValueError("baseline resource_count must match its selection")
        if self.resource_count > self.k:
            raise ValueError("baseline resource_count must not exceed k")
        if self.remaining_budget != self.k - self.resource_count:
            raise ValueError("baseline remaining_budget must equal k minus resource_count")
        if self.objective_value != self.coverage.covered_heat_weighted_demand:
            raise ValueError("baseline objective must equal covered heat-weighted demand")
        if self.algorithm is BaselineAlgorithm.STATIC_ALLOCATION:
            if (
                self.source_state_id is None
                or self.source_valid_at is None
                or self.source_full_state_fingerprint is None
            ):
                raise ValueError("static baseline requires source allocation identity")
            if self.source_selected_facility_ids != self.selected_facility_ids:
                raise ValueError("static baseline must preserve the source selection")
        return self


class UnavailableBaselineResult(FrozenModel):
    status: Literal[BaselineStatus.UNAVAILABLE] = BaselineStatus.UNAVAILABLE
    algorithm: BaselineAlgorithm
    scenario_id: str
    state_id: str
    valid_at: AwareDatetime
    k: int
    structural_fingerprint: str
    full_state_fingerprint: str
    unavailable_reason: str
    unavailable_facility_ids: tuple[str, ...] = ()
    facility_scores: tuple[FacilityThermalScore, ...] = ()
    algorithm_version: str = ALGORITHM_VERSION


BaselineResult = Annotated[
    CompleteBaselineResult | UnavailableBaselineResult,
    Field(discriminator="status"),
]


class MetricValue(FrozenModel):
    value: Decimal | None
    status: MetricStatus
    unit: str
    numerator: Decimal | None = None
    denominator: Decimal | None = None
    reason_code: str | None = None
    proxy_label: str = PROXY_LABEL

    @model_validator(mode="after")
    def validate_status(self) -> Self:
        if self.status is MetricStatus.AVAILABLE and self.value is None:
            raise ValueError("available metrics require a value")
        if self.status is MetricStatus.NOT_APPLICABLE and self.value is not None:
            raise ValueError("not-applicable metrics must not contain a value")
        return self


class SelectionChange(FrozenModel):
    added_facility_ids: tuple[str, ...]
    removed_facility_ids: tuple[str, ...]
    added_count: int
    removed_count: int
    changed_slot_count: int


class BaselineComparison(FrozenModel):
    algorithm: BaselineAlgorithm
    baseline_status: BaselineStatus
    optimized_objective: Decimal
    baseline_objective: Decimal | None
    absolute_improvement: Decimal | None
    percentage_improvement: MetricValue
    selection_change: SelectionChange | None
    full_state_fingerprint: str
    proxy_label: str = PROXY_LABEL


class ReplacementEvidence(FrozenModel):
    selected_facility_id: str
    alternative_facility_id: str
    original_facility_ids: tuple[str, ...]
    retained_facility_ids: tuple[str, ...]
    replacement_facility_ids: tuple[str, ...]
    original_resource_count: int
    replacement_resource_count: int
    remaining_budget: int
    original_objective: Decimal
    replacement_objective: Decimal
    objective_delta: Decimal
    primary_objective_loss: Decimal
    primary_objective_gain: Decimal
    original_covered_population: Decimal
    replacement_covered_population: Decimal
    population_delta: Decimal
    comparator_outcome: ReplacementComparatorOutcome
    decisive_criterion: TieBreakCriterion | None
    reason_code: ReplacementReasonCode
    selected_coverage: FacilityCoverage
    alternative_coverage: FacilityCoverage
    lost_cell_ids: tuple[str, ...]
    lost_heat_weighted_demand: Decimal
    lost_population: Decimal
    gained_cell_ids: tuple[str, ...]
    gained_heat_weighted_demand: Decimal
    gained_population: Decimal
    retained_covered_cell_ids: tuple[str, ...]
    retained_heat_weighted_demand: Decimal
    retained_population: Decimal
    structural_fingerprint: str
    full_state_fingerprint: str
    evidence_provenance_refs: tuple[str, ...]
    algorithm_version: str = ALGORITHM_VERSION


class MarginalAdditionEvidence(FrozenModel):
    unselected_facility_id: str
    original_facility_ids: tuple[str, ...]
    augmented_facility_ids: tuple[str, ...]
    original_objective: Decimal
    augmented_objective: Decimal
    marginal_heat_weighted_demand_gain: Decimal
    original_covered_population: Decimal
    augmented_covered_population: Decimal
    marginal_population_gain: Decimal
    newly_covered_cell_ids: tuple[str, ...]
    newly_covered_heat_weighted_demand: Decimal
    newly_covered_population: Decimal
    redundant_cell_ids: tuple[str, ...]
    redundant_heat_weighted_demand: Decimal
    redundant_population: Decimal
    resource_count_before: int
    resource_count_after: int
    remaining_budget_before: int
    remaining_budget_after: int
    outcome: MarginalAdditionOutcome
    structural_fingerprint: str
    full_state_fingerprint: str
    evidence_provenance_refs: tuple[str, ...]
    algorithm_version: str = ALGORITHM_VERSION


class MarginalAdditionEvidenceSet(FrozenModel):
    status: EvidenceStatus
    not_applicable_reason: MarginalAdditionNotApplicableReason | None = None
    evidence: tuple[MarginalAdditionEvidence, ...] = ()

    @model_validator(mode="after")
    def validate_applicability(self) -> Self:
        if self.status is EvidenceStatus.APPLICABLE:
            if self.not_applicable_reason is not None or not self.evidence:
                raise ValueError("applicable marginal evidence requires records and no reason")
        elif self.not_applicable_reason is None or self.evidence:
            raise ValueError("not-applicable marginal evidence requires a reason and no records")
        return self


class AllocationAnalysisResult(FrozenModel):
    optimized: AllocationResult
    optimized_coverage_percentage: MetricValue
    static_baseline: BaselineResult
    naive_baseline: BaselineResult
    comparisons: tuple[BaselineComparison, ...]
    replacement_evidence: tuple[ReplacementEvidence, ...]
    marginal_addition_evidence: MarginalAdditionEvidenceSet
