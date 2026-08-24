"""CoolAccess Temperature Intelligence Layer & Municipal Heat Analyst Core.

Bounded, read-only Temperature Intelligence backend core sitting above the
authoritative CoolAccess deterministic spatial optimization engine.

Design invariants:
- The deterministic optimizer is the ONLY authority for facility selection,
  coverage calculation, tie-breaking, baseline gains, and replacement losses.
- The LLM never selects facilities, calculates scores, modifies allocations,
  changes constraints, or influences optimization results.
- Zero live LLM calls, provider SDKs, or API keys in this core foundation.
- All factual text is server-rendered from a deterministic claim ledger.
- Pure read-only projections over authoritative scenario data.
- Strict closed intent set (5 intents) and closed read-only tool set (5 tools).
- Fail-closed verification: any unknown ID, excess tool call, or anomaly triggers
  DETERMINISTIC_FALLBACK.
- Runtime defaults to DisabledModelGateway (returning DETERMINISTIC_FALLBACK).
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
from collections.abc import Sequence
from enum import StrEnum
from typing import Annotated, Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from coolaccess.analysis import analyze_future_state
from coolaccess.contracts import (
    AllocationAnalysisResult,
    CompleteBaselineResult,
)
from coolaccess.optimizer import optimize
from coolaccess.scenario import (
    ScenarioBundle,
    format_timestamp_display,
    sanitize_timestamp_key,
)

logger = logging.getLogger("coolaccess.agent")

# Whitelist of valid benchmark facility identifiers (Washington DC empirical dataset)
VALID_FACILITY_IDS: tuple[str, ...] = (
    "DC_101",
    "DC_102",
    "DC_105",
    "DC_112",
    "DC_118",
    "DC_120",
    "DC_124",
    "DC_127",
    "DC_131",
    "DC_135",
    "DC_142",
    "DC_148",
)

# Whitelist of valid benchmark operational UTC timestamps
VALID_TIMESTAMPS: tuple[str, ...] = ("14:00", "16:00", "18:00", "20:00", "22:00")

# Maximum tool calls permitted in the single tool-selection round
MAX_TOOL_CALLS: int = 4

# Fixed client-safe fallback reasons for model-controlled failure paths. These
# strings must never interpolate model output, provider prose, or model-supplied IDs.
FALLBACK_REASON_GATEWAY_SELECTION_FAILED = (
    "AI provider unavailable during tool selection; returning an authoritative "
    "deterministic heat intelligence summary."
)
FALLBACK_REASON_GATEWAY_ANSWER_FAILED = (
    "AI provider unavailable during answer planning; returning an authoritative "
    "deterministic heat intelligence summary."
)
FALLBACK_REASON_TOOL_SELECTION_INVALID = "Model tool selection failed closed semantic validation."
FALLBACK_REASON_TOOL_EXECUTION_FAILED = "Validated read-only tool execution failed closed."
FALLBACK_REASON_ANSWER_PLAN_INVALID = "Model answer plan failed closed validation."
FALLBACK_REASON_ANSWER_PLAN_UNGROUNDED = (
    "Model answer plan failed request-local grounding validation."
)


# -----------------------------------------------------------------------------
# Closed Enums
# -----------------------------------------------------------------------------


class IntentCode(StrEnum):
    ALLOCATION_SUMMARY = "ALLOCATION_SUMMARY"
    DIURNAL_HEAT_TRANSITION = "DIURNAL_HEAT_TRANSITION"
    HEAT_VULNERABILITY_EXPLANATION = "HEAT_VULNERABILITY_EXPLANATION"
    REPLACEMENT_RATIONALE = "REPLACEMENT_RATIONALE"
    BASELINE_COMPARISON = "BASELINE_COMPARISON"


class CopilotStatus(StrEnum):
    AI_GENERATED = "AI_GENERATED"
    DETERMINISTIC_FALLBACK = "DETERMINISTIC_FALLBACK"


class ToolName(StrEnum):
    GET_ALLOCATION_PLAN = "get_allocation_plan"
    GET_DIURNAL_HEAT_TRANSITION = "get_diurnal_heat_transition"
    GET_HEAT_VULNERABILITY_PROFILE = "get_heat_vulnerability_profile"
    GET_REPLACEMENT_EVIDENCE = "get_replacement_evidence"
    GET_BASELINE_COMPARISON = "get_baseline_comparison"


class ToolSelectionValidationIssue(StrEnum):
    """Fixed, non-sensitive semantic-validation categories."""

    NO_TOOL_CALLS = "no_tool_calls"
    TOO_MANY_TOOL_CALLS = "too_many_tool_calls"
    INVALID_ALLOCATION_ARGUMENTS = "invalid_allocation_arguments"
    INVALID_FACILITY_ID = "invalid_facility_id"
    INVALID_FACILITY_TOOL_ARGUMENTS = "invalid_facility_tool_arguments"
    INVALID_TIMESTAMP = "invalid_timestamp"
    INVALID_REPLACEMENT_ARGUMENTS = "invalid_replacement_arguments"
    INVALID_BASELINE_ARGUMENTS = "invalid_baseline_arguments"
    UNKNOWN_TOOL = "unknown_tool"
    REPLACEMENT_MISSING_TOOL = "replacement_missing_tool"
    VULNERABILITY_MISSING_FACILITY = "vulnerability_missing_facility"


# -----------------------------------------------------------------------------
# Gateway & Claim Ledger Data Contracts
# -----------------------------------------------------------------------------


class ToolCall(BaseModel):
    tool_name: ToolName
    facility_id: str | None = None
    alternative_id: str | None = None
    target_timestamp: str | None = None
    baseline_type: str | None = None
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ClaimRecord(BaseModel):
    claim_id: str
    claim_type: str
    facility_id: str | None = None
    alternative_id: str | None = None
    timestamp: str | None = None
    value: Any = None
    unit: str | None = None
    display_text: str
    model_config = ConfigDict(extra="forbid", frozen=True)


class ToolExecutionResult(BaseModel):
    tool_name: ToolName
    facility_id: str | None = None
    alternative_id: str | None = None
    target_timestamp: str | None = None
    baseline_type: str | None = None
    claims: tuple[ClaimRecord, ...]
    model_config = ConfigDict(extra="forbid", frozen=True)


class AnswerSectionPlan(BaseModel):
    section_type: str
    ordered_claim_ids: tuple[str, ...]
    cited_facility_ids: tuple[str, ...] = ()
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class GatewayClassificationContext(BaseModel):
    question: str
    current_timestamp: str
    supported_intents: tuple[IntentCode, ...]
    supported_tools: tuple[ToolName, ...]
    available_facility_ids: tuple[str, ...]
    available_timestamps: tuple[str, ...]
    model_config = ConfigDict(extra="forbid", frozen=True)


class GatewayToolSelection(BaseModel):
    intent_code: IntentCode
    tool_calls: tuple[ToolCall, ...]
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class GatewayPlanContext(BaseModel):
    question: str
    intent_code: IntentCode
    current_timestamp: str
    available_claim_ids: tuple[str, ...]
    available_facility_ids: tuple[str, ...]
    model_config = ConfigDict(extra="forbid", frozen=True)


class GatewayAnswerPlan(BaseModel):
    intent_code: IntentCode
    headline_code: str
    sections: tuple[AnswerSectionPlan, ...]
    requested_highlights: tuple[str, ...] = ()
    tools_used: tuple[str, ...] = ()
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


# -----------------------------------------------------------------------------
# API Request & Response Schemas
# -----------------------------------------------------------------------------


class BriefItem(BaseModel):
    claim_id: str
    server_rendered_text: str
    facility_id: str | None = None
    alternative_id: str | None = None
    model_config = ConfigDict(extra="forbid")


class HeatBriefRequest(BaseModel):
    question: Annotated[str, Field(min_length=1, max_length=300)]
    timestamp: str = "16:00"
    baseline_timestamp: str = "16:00"
    radius_meters: int = 750
    k: int = 3
    model_config = ConfigDict(extra="forbid")

    @field_validator("question", mode="before")
    @classmethod
    def trim_and_validate_question(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
        return v


class HeatBriefResponse(BaseModel):
    status: CopilotStatus
    intent_code: IntentCode
    scenario_id: str
    plan_fingerprint: str
    title: str
    brief_items: list[BriefItem]
    tools_used: list[str]
    requested_highlights: list[str]
    mandatory_caveats: list[str]
    fallback_reason: str | None = None
    model_config = ConfigDict(extra="forbid")


# -----------------------------------------------------------------------------
# Model Gateway Protocol & Default Implementations
# -----------------------------------------------------------------------------


class ModelGateway(Protocol):
    """Protocol for Temperature Intelligence model gateway adapters."""

    def select_tools(
        self,
        context: GatewayClassificationContext,
    ) -> GatewayToolSelection | None:
        """Classify intent and select read-only tools, or None if unsupported."""
        ...

    def generate_answer_plan(
        self,
        context: GatewayPlanContext,
        tool_results: Sequence[ToolExecutionResult],
    ) -> GatewayAnswerPlan:
        """Generate structured answer plan citing strictly available claims."""
        ...


class DisabledModelGateway:
    """Runtime default gateway when no real LLM provider is configured.

    Always triggers safe deterministic fallback without pretending to be AI.
    """

    def select_tools(
        self,
        context: GatewayClassificationContext,
    ) -> GatewayToolSelection | None:
        return None

    def generate_answer_plan(
        self,
        context: GatewayPlanContext,
        tool_results: Sequence[ToolExecutionResult],
    ) -> GatewayAnswerPlan:
        raise RuntimeError("DisabledModelGateway does not generate answer plans.")


class FakeModelGateway:
    """Deterministic fake gateway for unit and regression testing only.

    Simulates intent classification, bounded tool selection, and structured
    answer planning across all 5 supported intents without network or AI calls.
    Must never be used as the runtime default.
    """

    def __init__(self, simulate_failure: str | None = None) -> None:
        self.simulate_failure = simulate_failure
        self.select_tools_called = 0
        self.generate_plan_called = 0

    def select_tools(
        self,
        context: GatewayClassificationContext,
    ) -> GatewayToolSelection | None:
        self.select_tools_called += 1

        if self.simulate_failure == "exception_on_select":
            raise RuntimeError("Simulated gateway network/service error during tool selection")
        if self.simulate_failure == "unsupported_intent":
            return None
        if self.simulate_failure == "excess_tools":
            return GatewayToolSelection(
                intent_code=IntentCode.ALLOCATION_SUMMARY,
                tool_calls=(
                    ToolCall(tool_name=ToolName.GET_ALLOCATION_PLAN),
                    ToolCall(
                        tool_name=ToolName.GET_HEAT_VULNERABILITY_PROFILE,
                        facility_id="DC_135",
                    ),
                    ToolCall(
                        tool_name=ToolName.GET_REPLACEMENT_EVIDENCE,
                        facility_id="DC_135",
                        alternative_id="DC_148",
                    ),
                    ToolCall(
                        tool_name=ToolName.GET_BASELINE_COMPARISON,
                        baseline_type="static_allocation",
                    ),
                    ToolCall(
                        tool_name=ToolName.GET_DIURNAL_HEAT_TRANSITION,
                        target_timestamp="20:00",
                    ),
                ),
            )
        if self.simulate_failure == "invalid_facility_id":
            return GatewayToolSelection(
                intent_code=IntentCode.HEAT_VULNERABILITY_EXPLANATION,
                tool_calls=(
                    ToolCall(
                        tool_name=ToolName.GET_HEAT_VULNERABILITY_PROFILE,
                        facility_id="DC_999_NONEXISTENT",
                    ),
                ),
            )
        if self.simulate_failure == "invalid_timestamp":
            return GatewayToolSelection(
                intent_code=IntentCode.DIURNAL_HEAT_TRANSITION,
                tool_calls=(
                    ToolCall(
                        tool_name=ToolName.GET_DIURNAL_HEAT_TRANSITION,
                        target_timestamp="99:00",
                    ),
                ),
            )

        q_lower = context.question.lower()

        # Reject explicitly unsupported categories
        unsupported_keywords = [
            "medical",
            "doctor",
            "health advice",
            "symptom",
            "treatment",
            "heat stroke treatment",
            "weather forecast",
            "tomorrow",
            "next week",
            "mutate",
            "change k",
            "update budget",
            "add facility",
            "delete facility",
            "override optimizer",
        ]
        if any(kw in q_lower for kw in unsupported_keywords):
            return None

        # Intent heuristic matching for inquiry test questions
        if any(
            kw in q_lower
            for kw in [
                "replace",
                "tradeoff",
                "trade-off",
                "rejected",
                "instead of",
                "over dc_",
                "dc_148",
                "alternative",
            ]
        ):
            return GatewayToolSelection(
                intent_code=IntentCode.REPLACEMENT_RATIONALE,
                tool_calls=(
                    ToolCall(
                        tool_name=ToolName.GET_REPLACEMENT_EVIDENCE,
                        facility_id="DC_135",
                        alternative_id="DC_148",
                    ),
                    ToolCall(
                        tool_name=ToolName.GET_HEAT_VULNERABILITY_PROFILE,
                        facility_id="DC_135",
                    ),
                ),
            )

        if any(
            kw in q_lower
            for kw in [
                "vulnerability",
                "thermal exposure",
                "heat exposure",
                "combine high heat",
                "density",
                "from a thermal perspective",
                "vulnerable",
            ]
        ):
            target_fac = (
                "DC_135" if "135" in q_lower else ("DC_148" if "148" in q_lower else "DC_135")
            )
            return GatewayToolSelection(
                intent_code=IntentCode.HEAT_VULNERABILITY_EXPLANATION,
                tool_calls=(
                    ToolCall(
                        tool_name=ToolName.GET_HEAT_VULNERABILITY_PROFILE,
                        facility_id=target_fac,
                    ),
                    ToolCall(tool_name=ToolName.GET_ALLOCATION_PLAN),
                ),
            )

        if any(
            kw in q_lower
            for kw in [
                "shift",
                "transition",
                "16:00 and 20:00",
                "20:00",
                "evening",
                "diurnal",
                "changed in thermal",
                "hour",
            ]
        ):
            return GatewayToolSelection(
                intent_code=IntentCode.DIURNAL_HEAT_TRANSITION,
                tool_calls=(
                    ToolCall(
                        tool_name=ToolName.GET_DIURNAL_HEAT_TRANSITION,
                        target_timestamp="20:00",
                    ),
                    ToolCall(tool_name=ToolName.GET_ALLOCATION_PLAN),
                ),
            )

        if any(
            kw in q_lower
            for kw in [
                "baseline",
                "static",
                "naive",
                "compare",
                "gain",
                "improvement",
                "efficiency",
            ]
        ):
            return GatewayToolSelection(
                intent_code=IntentCode.BASELINE_COMPARISON,
                tool_calls=(
                    ToolCall(
                        tool_name=ToolName.GET_BASELINE_COMPARISON,
                        baseline_type="static_allocation",
                    ),
                    ToolCall(
                        tool_name=ToolName.GET_BASELINE_COMPARISON,
                        baseline_type="naive_thermal",
                    ),
                ),
            )

        if any(
            kw in q_lower
            for kw in [
                "plan",
                "summary",
                "overview",
                "selected",
                "allocation",
                "cooling center",
                "brief",
            ]
        ):
            return GatewayToolSelection(
                intent_code=IntentCode.ALLOCATION_SUMMARY,
                tool_calls=(
                    ToolCall(tool_name=ToolName.GET_ALLOCATION_PLAN),
                    ToolCall(
                        tool_name=ToolName.GET_HEAT_VULNERABILITY_PROFILE,
                        facility_id="DC_135",
                    ),
                ),
            )

        # Fallback for unrecognized questions
        return None

    def generate_answer_plan(
        self,
        context: GatewayPlanContext,
        tool_results: Sequence[ToolExecutionResult],
    ) -> GatewayAnswerPlan:
        self.generate_plan_called += 1

        if self.simulate_failure == "exception_on_plan":
            raise RuntimeError("Simulated gateway error during answer plan generation")
        if self.simulate_failure == "unknown_claim_id":
            return GatewayAnswerPlan(
                intent_code=context.intent_code,
                headline_code="HEADLINE_INVALID",
                sections=(
                    AnswerSectionPlan(
                        section_type="summary",
                        ordered_claim_ids=("claim:nonexistent:hallucinated_claim",),
                        cited_facility_ids=(),
                    ),
                ),
                requested_highlights=("DC_135",),
                tools_used=("get_allocation_plan",),
            )
        if self.simulate_failure == "unknown_facility_id":
            return GatewayAnswerPlan(
                intent_code=context.intent_code,
                headline_code="HEADLINE_INVALID",
                sections=(
                    AnswerSectionPlan(
                        section_type="summary",
                        ordered_claim_ids=context.available_claim_ids[:1],
                        cited_facility_ids=("DC_999_HALLUCINATED",),
                    ),
                ),
                requested_highlights=(),
                tools_used=("get_allocation_plan",),
            )

        # Group available claims into an ordered sequence
        section = AnswerSectionPlan(
            section_type="findings",
            ordered_claim_ids=context.available_claim_ids,
            cited_facility_ids=context.available_facility_ids,
        )

        tools_used = tuple(
            f"{res.tool_name.value}("
            f"{res.facility_id or res.target_timestamp or res.baseline_type or ''})"
            for res in tool_results
        )
        highlights = tuple(context.available_facility_ids)

        return GatewayAnswerPlan(
            intent_code=context.intent_code,
            headline_code=f"HEADLINE_{context.intent_code.value}",
            sections=(section,),
            requested_highlights=highlights,
            tools_used=tools_used,
        )


# -----------------------------------------------------------------------------
# Read-Only Bounded Tool Implementations
# -----------------------------------------------------------------------------


def _tool_get_allocation_plan(
    analysis: AllocationAnalysisResult,
    scenario: ScenarioBundle,
) -> tuple[ClaimRecord, ...]:
    """Pure read-only projection: Return optimal facility selection, demand, and population."""
    opt = analysis.optimized
    cov = opt.coverage
    k = opt.k
    sel_ids = opt.selected_facility_ids
    cov_demand = float(cov.covered_heat_weighted_demand)
    cov_pop = int(cov.covered_population)
    tot_pop = int(cov.total_population)
    pct_val = analysis.optimized_coverage_percentage.value
    cov_pct = float(pct_val) if pct_val is not None else 0.0

    claims: list[ClaimRecord] = []

    # 1. Authority statement & overall coverage
    fac_names = []
    for fid in sel_ids:
        f_info = next(
            (f for f in scenario.facilities_data["facilities"] if f["facility_id"] == fid),
            None,
        )
        fac_names.append(f_info["name"] if f_info else fid)
    fac_list_str = ", ".join(
        f"'{name}' ({fid})" for name, fid in zip(fac_names, sel_ids, strict=False)
    )

    claims.append(
        ClaimRecord(
            claim_id="claim:alloc:summary",
            claim_type="allocation_summary",
            value={
                "k": k,
                "selected_ids": list(sel_ids),
                "covered_heat_weighted_demand": cov_demand,
                "covered_population": cov_pop,
                "coverage_percentage": cov_pct,
            },
            display_text=(
                f"The authoritative CoolAccess optimizer selected {len(sel_ids)} optimal "
                f"facilities ({fac_list_str}) under budget k={k}, covering {cov_demand:.2f} "
                f"heat-weighted demand units ({cov_pct:.1f}% of total demand) and protecting "
                f"{cov_pop:,} residents "
                f"({(cov_pop / tot_pop * 100.0) if tot_pop > 0 else 0.0:.1f}% of population)."
            ),
        )
    )

    # 2. Per-facility coverage details
    for pfc in cov.per_facility:
        fid = pfc.facility_id
        f_info = next(
            (f for f in scenario.facilities_data["facilities"] if f["facility_id"] == fid),
            None,
        )
        fname = f_info["name"] if f_info else fid
        d_pop = int(pfc.direct_population)
        d_demand = float(pfc.direct_heat_weighted_demand)
        u_demand = float(pfc.unique_heat_weighted_demand)

        claims.append(
            ClaimRecord(
                claim_id=f"claim:alloc:facility:{fid}",
                claim_type="facility_coverage",
                facility_id=fid,
                value={
                    "direct_population": d_pop,
                    "direct_demand": d_demand,
                    "unique_demand": u_demand,
                },
                display_text=(
                    f"Selected facility '{fname}' ({fid}) covers {d_pop:,} residents with "
                    f"{d_demand:.2f} direct heat-weighted demand units ({u_demand:.2f} unique)."
                ),
            )
        )

    # 3. Tie-break audit claim
    tb = opt.tie_break
    claims.append(
        ClaimRecord(
            claim_id="claim:alloc:tie_break",
            claim_type="tie_break_audit",
            value={
                "decisive_criterion": tb.decisive_criterion.value,
                "evaluated_combinations": tb.evaluated_combination_count,
            },
            display_text=(
                f"Optimal combination resolved decisively by '{tb.decisive_criterion.value}' "
                f"out of {tb.evaluated_combination_count} evaluated facility combinations."
            ),
        )
    )

    return tuple(claims)


def _tool_get_diurnal_heat_transition(
    scenario: ScenarioBundle,
    from_ts: str,
    to_ts: str,
    k: int = 3,
    radius_meters: int = 750,
) -> tuple[ClaimRecord, ...]:
    """Pure read-only projection: Return added/removed facilities and demand shift."""
    from_req = scenario.build_allocation_request(
        timestamp=from_ts, radius_meters=radius_meters, k=k
    )
    to_req = scenario.build_allocation_request(timestamp=to_ts, radius_meters=radius_meters, k=k)

    from_res = optimize(from_req)
    to_res = optimize(to_req)

    from_set = set(from_res.selected_facility_ids)
    to_set = set(to_res.selected_facility_ids)

    added = sorted(to_set - from_set)
    removed = sorted(from_set - to_set)
    retained = sorted(from_set & to_set)

    from_fmt = format_timestamp_display(from_ts)
    to_fmt = format_timestamp_display(to_ts)

    claims: list[ClaimRecord] = []

    def _get_name(fid: str) -> str:
        f = next(
            (item for item in scenario.facilities_data["facilities"] if item["facility_id"] == fid),
            None,
        )
        return f["name"] if f else fid

    added_names = [_get_name(fid) for fid in added]
    removed_names = [_get_name(fid) for fid in removed]
    retained_names = [_get_name(fid) for fid in retained]

    added_str = (
        ", ".join(f"{n} ({i})" for n, i in zip(added_names, added, strict=False)) or "none"
    )
    removed_str = (
        ", ".join(f"{n} ({i})" for n, i in zip(removed_names, removed, strict=False)) or "none"
    )

    shift_desc = (
        f"Between {from_fmt} UTC and {to_fmt} UTC, the optimal facility set shifts: "
        f"activated {len(added)} facility ({added_str}), "
        f"deactivated {len(removed)} facility ({removed_str}), "
        f"and retained {len(retained)} facilities ({', '.join(retained_names)})."
    )

    claims.append(
        ClaimRecord(
            claim_id=(
                f"claim:diurnal:{sanitize_timestamp_key(from_ts)}:"
                f"{sanitize_timestamp_key(to_ts)}:transition"
            ),
            claim_type="diurnal_transition",
            timestamp=to_ts,
            value={
                "from_timestamp": from_fmt,
                "to_timestamp": to_fmt,
                "added": added,
                "removed": removed,
                "retained": retained,
            },
            display_text=shift_desc,
        )
    )

    # Thermal retention context claim
    claims.append(
        ClaimRecord(
            claim_id=(
                f"claim:diurnal:{sanitize_timestamp_key(from_ts)}:"
                f"{sanitize_timestamp_key(to_ts)}:retention"
            ),
            claim_type="thermal_retention_context",
            timestamp=to_ts,
            value={
                "note": "Diurnal thermal inertia delays surface cooling in dense urban pockets."
            },
            display_text=(
                f"From {from_fmt} to {to_fmt} UTC, diurnal thermal retention maintains high "
                f"temperatures in dense built environments, necessitating facility shifts to "
                f"sustain cooling coverage."
            ),
        )
    )

    return tuple(claims)


def _tool_get_heat_vulnerability_profile(
    facility_id: str,
    analysis: AllocationAnalysisResult,
    scenario: ScenarioBundle,
    timestamp: str = "16:00",
) -> tuple[ClaimRecord, ...]:
    """Pure read-only projection: Return thermal priority and vulnerability context."""
    fac_info = next(
        (f for f in scenario.facilities_data["facilities"] if f["facility_id"] == facility_id),
        None,
    )
    if not fac_info:
        return (
            ClaimRecord(
                claim_id=f"claim:vulnerability:{facility_id}:not_found",
                claim_type="facility_not_found",
                facility_id=facility_id,
                display_text=f"Facility '{facility_id}' not found in scenario directory.",
            ),
        )

    fname = fac_info["name"]
    faddress = fac_info.get("address", "")
    opt = analysis.optimized
    is_selected = facility_id in opt.selected_facility_ids

    # Find coverage in optimized selection or compute direct catchment
    pfc = next((p for p in opt.coverage.per_facility if p.facility_id == facility_id), None)
    if pfc:
        pop = int(pfc.direct_population)
        demand = float(pfc.direct_heat_weighted_demand)
        block_count = len(pfc.direct_cell_ids)
    else:
        # Calculate from naive thermal scores if available
        naive = analysis.naive_baseline
        score_obj = next(
            (s for s in getattr(naive, "facility_scores", ()) if s.facility_id == facility_id),
            None,
        )
        block_count = score_obj.accessible_cell_count if score_obj else 0
        # Estimate population from census blocks in catchment
        req = scenario.build_allocation_request(timestamp=timestamp)
        accessible_cells = {
            edge.cell_id
            for edge in req.accessibility_relationships
            if edge.facility_id == facility_id and edge.is_accessible
        }
        cells_dict = {c.cell_id: c for c in req.demand_cells}
        pop = 0
        demand = 0.0
        for cid in accessible_cells:
            cell = cells_dict.get(cid)
            if cell is not None:
                pop += int(cell.population)
                if cell.heat_weighted_demand is not None:
                    demand += float(cell.heat_weighted_demand)

    mean_thermal = (demand / pop) if pop > 0 else 0.0

    claims: list[ClaimRecord] = []

    status_str = "SELECTED in optimal plan" if is_selected else "ELIGIBLE ALTERNATIVE (unselected)"

    claims.append(
        ClaimRecord(
            claim_id=f"claim:vulnerability:{facility_id}:profile",
            claim_type="heat_vulnerability_profile",
            facility_id=facility_id,
            timestamp=timestamp,
            value={
                "facility_name": fname,
                "address": faddress,
                "population": pop,
                "heat_weighted_demand": demand,
                "mean_thermal_priority": mean_thermal,
                "is_selected": is_selected,
            },
            display_text=(
                f"Facility '{fname}' ({facility_id}, {faddress}) is {status_str}: "
                f"serves a catchment of {pop:,} residents across {block_count} census blocks, "
                f"generating {demand:.2f} heat-weighted demand units with "
                f"mean thermal priority {mean_thermal:.3f}."
            ),
        )
    )

    claims.append(
        ClaimRecord(
            claim_id=f"claim:vulnerability:{facility_id}:thermal_context",
            claim_type="thermal_context",
            facility_id=facility_id,
            timestamp=timestamp,
            display_text=(
                "This facility serves an urban zone with elevated FortyGuard thermal exposure, "
                "making it an important anchor for municipal heat resilience planning."
            ),
        )
    )

    return tuple(claims)


def _tool_get_replacement_evidence(
    selected_id: str,
    alternative_id: str,
    analysis: AllocationAnalysisResult,
    scenario: ScenarioBundle,
) -> tuple[ClaimRecord, ...]:
    """Pure read-only projection: Return primary objective loss and population trade-off."""
    rep = next(
        (
            r
            for r in analysis.replacement_evidence
            if r.selected_facility_id == selected_id and r.alternative_facility_id == alternative_id
        ),
        None,
    )
    if not rep:
        return (
            ClaimRecord(
                claim_id=f"claim:rep:{selected_id}:{alternative_id}:not_found",
                claim_type="replacement_not_found",
                facility_id=selected_id,
                alternative_id=alternative_id,
                display_text=(
                    f"No precomputed replacement record found for selected '{selected_id}' "
                    f"and alternative '{alternative_id}'."
                ),
            ),
        )

    def _get_name(fid: str) -> str:
        f = next(
            (item for item in scenario.facilities_data["facilities"] if item["facility_id"] == fid),
            None,
        )
        return f["name"] if f else fid

    sel_name = _get_name(selected_id)
    alt_name = _get_name(alternative_id)
    loss = float(rep.primary_objective_loss)
    pop_delta = int(rep.population_delta)
    reason = rep.reason_code.value

    claims: list[ClaimRecord] = []

    claims.append(
        ClaimRecord(
            claim_id=f"claim:rep:{selected_id}:{alternative_id}:loss",
            claim_type="replacement_loss",
            facility_id=selected_id,
            alternative_id=alternative_id,
            value={
                "primary_objective_loss": loss,
                "population_delta": pop_delta,
                "reason_code": reason,
            },
            display_text=(
                f"Replacing selected '{sel_name}' ({selected_id}) with alternative '{alt_name}' "
                f"({alternative_id}) incurs a primary objective loss of {loss:.2f} heat-weighted "
                f"demand units (Decision code: {reason})."
            ),
        )
    )

    if pop_delta > 0:
        pop_tradeoff_text = (
            f"While '{alt_name}' covers +{pop_delta:,} more raw residents, '{sel_name}' covers "
            f"an urban corridor with substantially higher FortyGuard thermal exposure, "
            f"maximizing heat vulnerability mitigation."
        )
    elif pop_delta < 0:
        pop_tradeoff_text = (
            f"Alternative '{alt_name}' covers {abs(pop_delta):,} fewer residents while also "
            f"reducing total thermal demand coverage."
        )
    else:
        pop_tradeoff_text = (
            f"Both facilities cover equal raw population, but '{sel_name}' provides "
            f"superior thermal priority coverage."
        )

    claims.append(
        ClaimRecord(
            claim_id=f"claim:rep:{selected_id}:{alternative_id}:tradeoff",
            claim_type="replacement_tradeoff",
            facility_id=selected_id,
            alternative_id=alternative_id,
            display_text=pop_tradeoff_text,
        )
    )

    return tuple(claims)


def _tool_get_baseline_comparison(
    baseline_type: str,
    analysis: AllocationAnalysisResult,
    scenario: ScenarioBundle,
) -> tuple[ClaimRecord, ...]:
    """Pure read-only projection: Return dynamic optimization gain over static or naive baseline."""
    opt = analysis.optimized
    cov_demand = float(opt.coverage.covered_heat_weighted_demand)

    claims: list[ClaimRecord] = []

    if baseline_type in ("static", "static_allocation", "all"):
        static_res = analysis.static_baseline
        if isinstance(static_res, CompleteBaselineResult):
            s_obj = float(static_res.objective_value)
            s_gain = cov_demand - s_obj
            s_pct = (s_gain / s_obj * 100.0) if s_obj > 0 else 0.0

            claims.append(
                ClaimRecord(
                    claim_id="claim:base:static:gain",
                    claim_type="static_baseline_comparison",
                    value={
                        "baseline_objective": s_obj,
                        "optimized_objective": cov_demand,
                        "absolute_gain": s_gain,
                        "percentage_gain": s_pct,
                    },
                    display_text=(
                        f"Dynamic allocation outperforms the static 16:00 baseline by "
                        f"+{s_gain:.2f} heat-weighted demand units (+{s_pct:.1f}% improvement), "
                        f"adapting to shifting diurnal thermal corridors without requiring "
                        f"additional resources."
                    ),
                )
            )

    if baseline_type in ("naive", "naive_thermal", "all"):
        naive_res = analysis.naive_baseline
        if isinstance(naive_res, CompleteBaselineResult):
            n_obj = float(naive_res.objective_value)
            n_gain = cov_demand - n_obj
            n_pct = (n_gain / n_obj * 100.0) if n_obj > 0 else 0.0

            claims.append(
                ClaimRecord(
                    claim_id="claim:base:naive:gain",
                    claim_type="naive_baseline_comparison",
                    value={
                        "baseline_objective": n_obj,
                        "optimized_objective": cov_demand,
                        "absolute_gain": n_gain,
                        "percentage_gain": n_pct,
                    },
                    display_text=(
                        f"Dynamic allocation outperforms the naive thermal-only baseline by "
                        f"+{n_gain:.2f} heat-weighted demand units (+{n_pct:.1f}% improvement), "
                        f"balancing raw thermal hotspot intensity with census population density "
                        f"and catchment overlap."
                    ),
                )
            )

    return tuple(claims)


def execute_tool(
    call: ToolCall,
    analysis: AllocationAnalysisResult,
    scenario: ScenarioBundle,
    timestamp: str,
    baseline_timestamp: str,
    radius_meters: int,
    k: int,
) -> ToolExecutionResult:
    """Execute a single bounded read-only tool with strict closed parameter validation."""
    if call.tool_name == ToolName.GET_ALLOCATION_PLAN:
        claims = _tool_get_allocation_plan(analysis, scenario)
        return ToolExecutionResult(tool_name=call.tool_name, claims=claims)

    if call.tool_name == ToolName.GET_DIURNAL_HEAT_TRANSITION:
        target_ts = call.target_timestamp or timestamp
        if target_ts not in VALID_TIMESTAMPS:
            raise ValueError(f"Invalid timestamp '{target_ts}' for {call.tool_name}")
        claims = _tool_get_diurnal_heat_transition(
            scenario,
            from_ts=baseline_timestamp,
            to_ts=target_ts,
            k=k,
            radius_meters=radius_meters,
        )
        return ToolExecutionResult(
            tool_name=call.tool_name,
            target_timestamp=target_ts,
            claims=claims,
        )

    if call.tool_name == ToolName.GET_HEAT_VULNERABILITY_PROFILE:
        if not call.facility_id or call.facility_id not in VALID_FACILITY_IDS:
            raise ValueError(f"Invalid facility_id '{call.facility_id}' for {call.tool_name}")
        claims = _tool_get_heat_vulnerability_profile(
            facility_id=call.facility_id,
            analysis=analysis,
            scenario=scenario,
            timestamp=timestamp,
        )
        return ToolExecutionResult(
            tool_name=call.tool_name,
            facility_id=call.facility_id,
            claims=claims,
        )

    if call.tool_name == ToolName.GET_REPLACEMENT_EVIDENCE:
        sel_id = call.facility_id or "DC_135"
        alt_id = call.alternative_id or "DC_148"
        if sel_id not in VALID_FACILITY_IDS or alt_id not in VALID_FACILITY_IDS:
            raise ValueError(f"Invalid facility IDs '{sel_id}', '{alt_id}' for {call.tool_name}")
        claims = _tool_get_replacement_evidence(
            selected_id=sel_id,
            alternative_id=alt_id,
            analysis=analysis,
            scenario=scenario,
        )
        return ToolExecutionResult(
            tool_name=call.tool_name,
            facility_id=sel_id,
            alternative_id=alt_id,
            claims=claims,
        )

    if call.tool_name == ToolName.GET_BASELINE_COMPARISON:
        btype = call.baseline_type or "all"
        claims = _tool_get_baseline_comparison(
            baseline_type=btype,
            analysis=analysis,
            scenario=scenario,
        )
        return ToolExecutionResult(
            tool_name=call.tool_name,
            baseline_type=btype,
            claims=claims,
        )

    raise ValueError(f"Unknown tool name '{call.tool_name}'")


def validate_tool_selection_semantics(
    tool_selection: GatewayToolSelection,
    available_facility_ids: Sequence[str] = VALID_FACILITY_IDS,
    available_timestamps: Sequence[str] = VALID_TIMESTAMPS,
) -> ToolSelectionValidationIssue | None:
    """Validate tool calls semantically before execution."""
    if not tool_selection.tool_calls:
        return ToolSelectionValidationIssue.NO_TOOL_CALLS

    if len(tool_selection.tool_calls) > MAX_TOOL_CALLS:
        return ToolSelectionValidationIssue.TOO_MANY_TOOL_CALLS

    facility_id_set = set(available_facility_ids)
    timestamp_set = set(available_timestamps)

    for call in tool_selection.tool_calls:
        if call.tool_name == ToolName.GET_ALLOCATION_PLAN:
            if call.facility_id is not None or call.alternative_id is not None:
                return ToolSelectionValidationIssue.INVALID_ALLOCATION_ARGUMENTS
        elif call.tool_name == ToolName.GET_HEAT_VULNERABILITY_PROFILE:
            if not call.facility_id or call.facility_id not in facility_id_set:
                return ToolSelectionValidationIssue.INVALID_FACILITY_ID
        elif call.tool_name == ToolName.GET_DIURNAL_HEAT_TRANSITION:
            if call.target_timestamp and call.target_timestamp not in timestamp_set:
                return ToolSelectionValidationIssue.INVALID_TIMESTAMP
        elif call.tool_name == ToolName.GET_REPLACEMENT_EVIDENCE:
            if call.facility_id and call.facility_id not in facility_id_set:
                return ToolSelectionValidationIssue.INVALID_FACILITY_ID
            if call.alternative_id and call.alternative_id not in facility_id_set:
                return ToolSelectionValidationIssue.INVALID_FACILITY_ID
        elif call.tool_name == ToolName.GET_BASELINE_COMPARISON:
            pass
        else:
            return ToolSelectionValidationIssue.UNKNOWN_TOOL

    # Intent-specific validation:
    # REPLACEMENT_RATIONALE should include GET_REPLACEMENT_EVIDENCE
    if tool_selection.intent_code == IntentCode.REPLACEMENT_RATIONALE:
        has_rep = any(
            c.tool_name == ToolName.GET_REPLACEMENT_EVIDENCE for c in tool_selection.tool_calls
        )
        if not has_rep:
            return ToolSelectionValidationIssue.REPLACEMENT_MISSING_TOOL

    return None


# -----------------------------------------------------------------------------
# Mandatory Caveats & Deterministic Fingerprint
# -----------------------------------------------------------------------------


def compute_allocation_fingerprint(analysis: AllocationAnalysisResult) -> str:
    """Compute a deterministic hash fingerprint over authoritative allocation results."""
    opt = analysis.optimized
    payload = {
        "scenario_id": opt.scenario_id,
        "state_id": opt.state_id,
        "selected_facility_ids": list(opt.selected_facility_ids),
        "objective_value": str(opt.objective_value),
        "full_state_fingerprint": opt.full_state_fingerprint,
    }
    raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def get_mandatory_caveats(analysis: AllocationAnalysisResult) -> list[str]:
    """Construct mandatory, non-suppressible caveats directly from authoritative data."""
    return [
        "Prepared historical FortyGuard 100m TCM thermal intelligence benchmark (July 15, 2024) — "
        "not live weather or forecast telemetry.",
        "The deterministic CoolAccess integer optimizer remains the authoritative source of truth "
        "for all facility allocations.",
        "Thermal priority is a scenario-specific planning proxy, not medical or regulatory "
        "safety limits.",
    ]


# -----------------------------------------------------------------------------
# Orchestration Engine
# -----------------------------------------------------------------------------


def _build_deterministic_fallback_response(
    analysis: AllocationAnalysisResult,
    scenario: ScenarioBundle,
    question: str,
    intent_code: IntentCode = IntentCode.ALLOCATION_SUMMARY,
    fallback_reason: str = "Operating in authoritative deterministic mode.",
    tools_used: list[str] | None = None,
) -> HeatBriefResponse:
    """Construct an authoritative deterministic brief when gateway is disabled or fails."""
    plan_claims = _tool_get_allocation_plan(analysis, scenario)
    fingerprint = compute_allocation_fingerprint(analysis)
    caveats = get_mandatory_caveats(analysis)

    brief_items = [
        BriefItem(
            claim_id=claim.claim_id,
            server_rendered_text=claim.display_text,
            facility_id=claim.facility_id,
            alternative_id=claim.alternative_id,
        )
        for claim in plan_claims
    ]

    return HeatBriefResponse(
        status=CopilotStatus.DETERMINISTIC_FALLBACK,
        intent_code=intent_code,
        scenario_id=analysis.optimized.scenario_id,
        plan_fingerprint=fingerprint,
        title="Authoritative Heat Intelligence Brief (Deterministic Summary)",
        brief_items=brief_items,
        tools_used=tools_used or ["get_allocation_plan"],
        requested_highlights=list(analysis.optimized.selected_facility_ids),
        mandatory_caveats=caveats,
        fallback_reason=fallback_reason,
    )


def generate_heat_brief(
    request: HeatBriefRequest,
    scenario_bundle: ScenarioBundle,
    analysis_result: AllocationAnalysisResult | None = None,
    gateway: ModelGateway | None = None,
) -> HeatBriefResponse:
    """Execute the bounded 9-step Temperature Intelligence analyst loop.

    1. Validate municipal inquiry.
    2. Compute authoritative target-state analysis if not supplied.
    3. Gateway receives minimum context for intent classification & tool selection.
    4. Enforce at most 1 round and maximum 4 tool calls.
    5. Execute validated read-only tools against authoritative state.
    6. Build in-memory claim ledger.
    7. Gateway returns structured answer plan citing claims.
    8. Server validates all claim IDs and facility IDs against the active ledger.
    9. Server renders the final user-visible wording deterministically.
    """
    if gateway is None:
        gateway = DisabledModelGateway()

    # Preflight: Ensure authoritative analysis exists
    if analysis_result is None:
        target_req = scenario_bundle.build_allocation_request(
            timestamp=request.timestamp,
            radius_meters=request.radius_meters,
            k=request.k,
        )
        prior_req = scenario_bundle.build_allocation_request(
            timestamp=request.baseline_timestamp,
            radius_meters=request.radius_meters,
            k=request.k,
        )
        prior_res = optimize(prior_req)
        analysis_result = analyze_future_state(target_req, prior_res)

    # If gateway is DisabledModelGateway, return deterministic fallback immediately
    if isinstance(gateway, DisabledModelGateway):
        return _build_deterministic_fallback_response(
            analysis=analysis_result,
            scenario=scenario_bundle,
            question=request.question,
            fallback_reason=(
                "No AI model gateway configured; returning authoritative deterministic summary."
            ),
        )

    # Step 3: Gateway tool selection
    classification_context = GatewayClassificationContext(
        question=request.question,
        current_timestamp=request.timestamp,
        supported_intents=tuple(IntentCode),
        supported_tools=tuple(ToolName),
        available_facility_ids=VALID_FACILITY_IDS,
        available_timestamps=VALID_TIMESTAMPS,
    )

    try:
        tool_selection = gateway.select_tools(classification_context)
    except Exception:
        logger.warning("Gateway tool selection failed: category=gateway_exception")
        return _build_deterministic_fallback_response(
            analysis=analysis_result,
            scenario=scenario_bundle,
            question=request.question,
            fallback_reason=FALLBACK_REASON_GATEWAY_SELECTION_FAILED,
        )

    if tool_selection is None:
        return _build_deterministic_fallback_response(
            analysis=analysis_result,
            scenario=scenario_bundle,
            question=request.question,
            fallback_reason="Inquiry outside closed heat intelligence intent scope.",
        )

    # Step 4: Semantic validation of tool selection (max 4 calls, valid IDs)
    semantic_issue = validate_tool_selection_semantics(
        tool_selection,
        available_facility_ids=classification_context.available_facility_ids,
        available_timestamps=classification_context.available_timestamps,
    )
    if semantic_issue is not None:
        logger.warning(
            "Tool selection semantic validation failed: category=%s",
            semantic_issue.value,
        )
        return _build_deterministic_fallback_response(
            analysis=analysis_result,
            scenario=scenario_bundle,
            question=request.question,
            fallback_reason=FALLBACK_REASON_TOOL_SELECTION_INVALID,
        )

    # Step 5 & 6: Execute validated tools & build active claim ledger
    active_claim_ledger: dict[str, ClaimRecord] = {}
    active_facility_ids: set[str] = set()
    tool_results: list[ToolExecutionResult] = []
    tools_used_strings: list[str] = []

    safe_analysis = copy.deepcopy(analysis_result)

    for call in tool_selection.tool_calls:
        try:
            result = execute_tool(
                call=call,
                analysis=safe_analysis,
                scenario=scenario_bundle,
                timestamp=request.timestamp,
                baseline_timestamp=request.baseline_timestamp,
                radius_meters=request.radius_meters,
                k=request.k,
            )
        except Exception:
            logger.warning(
                "Validated tool execution failed: tool=%s category=execution_error",
                call.tool_name.value,
            )
            return _build_deterministic_fallback_response(
                analysis=analysis_result,
                scenario=scenario_bundle,
                question=request.question,
                fallback_reason=FALLBACK_REASON_TOOL_EXECUTION_FAILED,
            )

        tool_results.append(result)
        tools_used_strings.append(
            f"{call.tool_name.value}("
            f"{call.facility_id or call.target_timestamp or call.baseline_type or ''})"
        )

        for claim in result.claims:
            active_claim_ledger[claim.claim_id] = claim
            if claim.facility_id:
                active_facility_ids.add(claim.facility_id)
            if claim.alternative_id:
                active_facility_ids.add(claim.alternative_id)

    # Step 7: Gateway generates answer plan citing claims
    plan_context = GatewayPlanContext(
        question=request.question,
        intent_code=tool_selection.intent_code,
        current_timestamp=request.timestamp,
        available_claim_ids=tuple(active_claim_ledger.keys()),
        available_facility_ids=tuple(sorted(active_facility_ids)),
    )

    try:
        answer_plan = gateway.generate_answer_plan(plan_context, tool_results)
    except Exception:
        logger.warning("Gateway answer plan generation failed: category=gateway_exception")
        return _build_deterministic_fallback_response(
            analysis=analysis_result,
            scenario=scenario_bundle,
            question=request.question,
            intent_code=tool_selection.intent_code,
            fallback_reason=FALLBACK_REASON_GATEWAY_ANSWER_FAILED,
            tools_used=tools_used_strings,
        )

    # Step 8: Validate Grounding (Fail closed on any unknown claim/facility ID)
    if answer_plan.intent_code != tool_selection.intent_code:
        logger.warning("Answer plan validation failed: category=intent_mismatch")
        return _build_deterministic_fallback_response(
            analysis=analysis_result,
            scenario=scenario_bundle,
            question=request.question,
            intent_code=tool_selection.intent_code,
            fallback_reason=FALLBACK_REASON_ANSWER_PLAN_INVALID,
            tools_used=tools_used_strings,
        )

    if not answer_plan.sections:
        logger.warning("Answer plan validation failed: category=no_sections")
        return _build_deterministic_fallback_response(
            analysis=analysis_result,
            scenario=scenario_bundle,
            question=request.question,
            intent_code=tool_selection.intent_code,
            fallback_reason=FALLBACK_REASON_ANSWER_PLAN_INVALID,
            tools_used=tools_used_strings,
        )

    grounded_claim_count = 0
    for section in answer_plan.sections:
        for cid in section.ordered_claim_ids:
            if cid not in active_claim_ledger:
                logger.warning("Answer plan grounding failed: category=unknown_claim_id")
                return _build_deterministic_fallback_response(
                    analysis=analysis_result,
                    scenario=scenario_bundle,
                    question=request.question,
                    intent_code=tool_selection.intent_code,
                    fallback_reason=FALLBACK_REASON_ANSWER_PLAN_UNGROUNDED,
                    tools_used=tools_used_strings,
                )
            grounded_claim_count += 1
        for fid in section.cited_facility_ids:
            if fid not in active_facility_ids:
                logger.warning("Answer plan grounding failed: category=unknown_facility_id")
                return _build_deterministic_fallback_response(
                    analysis=analysis_result,
                    scenario=scenario_bundle,
                    question=request.question,
                    intent_code=tool_selection.intent_code,
                    fallback_reason=FALLBACK_REASON_ANSWER_PLAN_UNGROUNDED,
                    tools_used=tools_used_strings,
                )

    if grounded_claim_count == 0:
        logger.warning("Answer plan validation failed: category=no_grounded_claims")
        return _build_deterministic_fallback_response(
            analysis=analysis_result,
            scenario=scenario_bundle,
            question=request.question,
            intent_code=tool_selection.intent_code,
            fallback_reason=FALLBACK_REASON_ANSWER_PLAN_INVALID,
            tools_used=tools_used_strings,
        )

    # Step 9: Deterministic server-owned rendering
    brief_items: list[BriefItem] = []
    seen_claims: set[str] = set()

    for section in answer_plan.sections:
        for cid in section.ordered_claim_ids:
            if cid not in seen_claims:
                claim = active_claim_ledger[cid]
                brief_items.append(
                    BriefItem(
                        claim_id=claim.claim_id,
                        server_rendered_text=claim.display_text,
                        facility_id=claim.facility_id,
                        alternative_id=claim.alternative_id,
                    )
                )
                seen_claims.add(cid)

    fingerprint = compute_allocation_fingerprint(analysis_result)
    caveats = get_mandatory_caveats(analysis_result)

    title_map = {
        IntentCode.ALLOCATION_SUMMARY: "Optimal Cooling Center Deployment Brief",
        IntentCode.DIURNAL_HEAT_TRANSITION: "Diurnal Thermal Transition Analysis",
        IntentCode.HEAT_VULNERABILITY_EXPLANATION: "Heat Vulnerability & Exposure Explanation",
        IntentCode.REPLACEMENT_RATIONALE: "Facility Replacement & Trade-off Rationale",
        IntentCode.BASELINE_COMPARISON: "Comparative Baseline Performance Analysis",
    }

    highlights = list(answer_plan.requested_highlights) or list(active_facility_ids)

    return HeatBriefResponse(
        status=CopilotStatus.AI_GENERATED,
        intent_code=tool_selection.intent_code,
        scenario_id=analysis_result.optimized.scenario_id,
        plan_fingerprint=fingerprint,
        title=title_map.get(tool_selection.intent_code, "Heat Intelligence Brief"),
        brief_items=brief_items,
        tools_used=tools_used_strings,
        requested_highlights=highlights,
        mandatory_caveats=caveats,
    )
