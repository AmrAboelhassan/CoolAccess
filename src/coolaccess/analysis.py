"""Deterministic allocation, baseline, metric, and evidence orchestration."""

from __future__ import annotations

from coolaccess.baselines import evaluate_naive_baseline, evaluate_static_baseline
from coolaccess.contracts import (
    AllocationAnalysisResult,
    AllocationRequest,
    AllocationResult,
    EligibilityStatus,
)
from coolaccess.metrics import calculate_coverage_percentage, compare_with_baseline
from coolaccess.optimizer import optimize
from coolaccess.replacement import (
    build_marginal_addition_evidence_set,
    build_replacement_evidence,
    validate_marginal_optimality,
    validate_replacement_optimality,
)


def analyze_future_state(
    target_request: AllocationRequest,
    prior_allocation: AllocationResult,
) -> AllocationAnalysisResult:
    """Build one atomic, internally verified target-state analysis.

    ``prior_allocation`` supplies only the fixed selection for the static
    baseline.  Every target-state number is recalculated from ``target_request``.
    """

    optimized = optimize(target_request)
    static_baseline = evaluate_static_baseline(target_request, prior_allocation)
    naive_baseline = evaluate_naive_baseline(target_request)
    comparisons = (
        compare_with_baseline(optimized, static_baseline),
        compare_with_baseline(optimized, naive_baseline),
    )

    selected = optimized.selected_facility_ids
    selected_set = set(selected)
    eligible_unselected = tuple(
        facility.facility_id
        for facility in target_request.facilities
        if facility.eligibility_status is EligibilityStatus.ELIGIBLE
        and facility.facility_id not in selected_set
    )
    replacements = tuple(
        build_replacement_evidence(
            target_request,
            optimized,
            selected_id,
            alternative_id,
        )
        for selected_id in selected
        for alternative_id in eligible_unselected
    )
    for replacement_record in replacements:
        validate_replacement_optimality(replacement_record)

    marginal_evidence = build_marginal_addition_evidence_set(
        target_request,
        optimized,
    )
    for marginal_record in marginal_evidence.evidence:
        validate_marginal_optimality(marginal_record)

    return AllocationAnalysisResult(
        optimized=optimized,
        optimized_coverage_percentage=calculate_coverage_percentage(optimized.coverage),
        static_baseline=static_baseline,
        naive_baseline=naive_baseline,
        comparisons=comparisons,
        replacement_evidence=replacements,
        marginal_addition_evidence=marginal_evidence,
    )
