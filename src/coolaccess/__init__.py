"""CoolAccess provider-neutral deterministic allocation foundation."""

from coolaccess.analysis import analyze_future_state
from coolaccess.baselines import evaluate_naive_baseline, evaluate_static_baseline
from coolaccess.contracts import (
    AccessibilityRelationship,
    AllocationAnalysisResult,
    AllocationRequest,
    AllocationResult,
    BaselineAlgorithm,
    BaselineComparison,
    BaselineResult,
    ConfigurationReference,
    EligibilityStatus,
    FacilityDefinition,
    MarginalAdditionEvidence,
    MarginalAdditionEvidenceSet,
    PopulationCell,
    ProvenanceRecord,
    ReplacementEvidence,
)
from coolaccess.coverage import evaluate_coverage
from coolaccess.demand import calculate_heat_weighted_demand
from coolaccess.metrics import calculate_coverage_percentage, compare_with_baseline
from coolaccess.optimizer import optimize
from coolaccess.replacement import (
    build_marginal_addition_evidence,
    build_marginal_addition_evidence_set,
    build_replacement_evidence,
)
from coolaccess.scenario import ScenarioBundle, load_locked_scenario
from coolaccess.server import app, create_app

__all__ = [
    "AccessibilityRelationship",
    "AllocationAnalysisResult",
    "AllocationRequest",
    "AllocationResult",
    "BaselineAlgorithm",
    "BaselineComparison",
    "BaselineResult",
    "ConfigurationReference",
    "EligibilityStatus",
    "FacilityDefinition",
    "MarginalAdditionEvidence",
    "MarginalAdditionEvidenceSet",
    "PopulationCell",
    "ProvenanceRecord",
    "ReplacementEvidence",
    "ScenarioBundle",
    "analyze_future_state",
    "app",
    "build_marginal_addition_evidence",
    "build_marginal_addition_evidence_set",
    "build_replacement_evidence",
    "calculate_coverage_percentage",
    "calculate_heat_weighted_demand",
    "compare_with_baseline",
    "create_app",
    "evaluate_coverage",
    "evaluate_naive_baseline",
    "evaluate_static_baseline",
    "load_locked_scenario",
    "optimize",
]
