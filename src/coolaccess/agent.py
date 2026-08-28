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
- Strict closed intent set (5 intents) and closed read-only tool set (6 tools).
- Deterministic Evidence Planner guarantees mandatory evidence completeness.
- Distinct status states: AI_GENERATED, DETERMINISTIC_FALLBACK, UNSUPPORTED.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
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

# Non-authoritative backward-compatibility fixture defaults (ScenarioBundle is authoritative)
VALID_FACILITY_IDS: tuple[str, ...] = (
    "DC_089",
    "DC_135",
    "DC_148",
    "DC_159",
    "DC_166",
    "DC_168",
)

# Whitelist of valid benchmark operational UTC timestamps
VALID_TIMESTAMPS: tuple[str, ...] = ("14:00", "16:00", "18:00", "20:00", "22:00")

# Maximum tool calls permitted in a single tool-selection / evidence-planning round
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

_UNSUPPORTED_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        # Medical, physiological-safety, and outcome-guarantee requests.
        r"\b(?:medical|clinical|doctor|diagnos(?:is|e)|symptoms?|treatments?|first aid)\b",
        r"\b(?:heat[ -]?stroke|heat exhaustion)\b",
        r"\b(?:is|are|will|would|guarantee)\b.{0,50}\b(?:safe|safety|protected)\b",
        r"\b(?:safe|safety)\b.{0,50}\b(?:worker|resident|public|people|person)\b",
        # Regulatory determinations.
        r"\b(?:osha|regulatory|regulation|legally compliant|complies? with)\b",
        # Forecast and live/current-weather requests. Analytical uses of "right now"
        # remain in scope unless they explicitly ask for current weather/temperature.
        r"\b(?:forecast|tomorrow|next week|future weather|live radar|live weather)\b",
        r"\b(?:weather|temperature|temperatures)\b.{0,35}\b(?:right now|currently|live)\b",
        r"\b(?:right now|currently|live)\b.{0,35}\b(?:weather|temperature|temperatures)\b",
        # Commands that would mutate or deploy an authoritative allocation/constraint.
        r"\b(?:override|mutate)\b.{0,40}\b(?:optimizer|allocation|constraint|budget|k)\b",
        r"\b(?:change|set|modify|update)\s+(?:the\s+)?(?:k|budget|allocation|constraint)\b",
        (
            r"\b(?:activate|deactivate|open|close|add|remove|delete)\b.{0,60}"
            r"\b(?:facility|dc[_ -]?\d{3}|library|center)\b.{0,20}"
            r"\b(?:now|today|immediately)\b"
        ),
        r"\b(?:deploy|apply|implement)\b.{0,30}\b(?:allocation|plan|change)\b",
        r"\b(?:add|remove|delete)\s+(?:a\s+|the\s+)?(?:new\s+)?facility\b",
    )
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
    UNSUPPORTED = "UNSUPPORTED"


class ToolName(StrEnum):
    GET_ALLOCATION_PLAN = "get_allocation_plan"
    GET_DIURNAL_HEAT_TRANSITION = "get_diurnal_heat_transition"
    GET_DIURNAL_THERMAL_PROFILE = "get_diurnal_thermal_profile"
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
    INTENT_MISMATCH = "intent_mismatch"
    EXPLICIT_ENTITY_CONFLICT = "explicit_entity_conflict"
    INVALID_REPLACEMENT_DIRECTION = "invalid_replacement_direction"
    MISSING_MANDATORY_EVIDENCE = "missing_mandatory_evidence"


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
    selected_facility_ids: tuple[str, ...] = ()
    radius_meters: int = 750
    k: int = 3
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
    radius_meters: int = 750
    k: int = 3
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
    radius_meters: Annotated[int, Field(ge=100, le=5000)] = 750
    k: Annotated[int, Field(ge=1, le=6)] = 3
    model_config = ConfigDict(extra="forbid")

    @field_validator("question", mode="before")
    @classmethod
    def trim_and_validate_question(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
        return v


class HeatBriefResponse(BaseModel):
    status: CopilotStatus
    intent_code: IntentCode | None = None
    scenario_id: str
    plan_fingerprint: str
    timestamp: str
    radius_meters: int
    k: int
    title: str
    brief_items: list[BriefItem]
    tools_used: list[str]
    requested_highlights: list[str]
    mandatory_caveats: list[str]
    fallback_reason: str | None = None
    model_config = ConfigDict(extra="forbid")


# -----------------------------------------------------------------------------
# Scope & Intent Heuristic Classifiers
# -----------------------------------------------------------------------------


def is_unsupported_question(question: str) -> bool:
    """Detect if a question is out of scope for municipal cooling optimization."""
    return any(pattern.search(question) is not None for pattern in _UNSUPPORTED_PATTERNS)


def infer_intent_from_question(question: str) -> IntentCode:
    """Heuristic classifier mapping free-form inquiries into the 5 closed intent codes."""
    q_lower = question.lower()

    # 1. Baseline Comparison (tested before generic comparison words)
    if any(
        kw in q_lower
        for kw in (
            "baseline",
            "static",
            "naive",
            "compare dynamic",
            "gain over",
            "efficiency gain",
            "improvement",
            "why not keep",
            "keep the midday",
            "choose the hottest",
            "how much better",
            "outperform",
        )
    ):
        return IntentCode.BASELINE_COMPARISON

    # 2. Replacement / Trade-off
    if any(
        kw in q_lower
        for kw in (
            "replace",
            "replacement",
            "tradeoff",
            "trade-off",
            "trade off",
            "rejected",
            "not selected",
            "wasn't selected",
            "was not selected",
            "instead of",
            "over dc_",
            "swap",
            "swapping",
            "would be lost",
            "lose by choosing",
        )
    ):
        return IntentCode.REPLACEMENT_RATIONALE

    # 3. Diurnal / Time Transition
    if any(
        kw in q_lower
        for kw in (
            "shift",
            "transition",
            "diurnal",
            "evening",
            "afternoon",
            "noon",
            "midday",
            "between",
            "hour",
            "20:00",
            "18:00",
            "14:00",
            "16:00",
            "22:00",
            "2pm",
            "4pm",
            "6pm",
            "8pm",
            "10pm",
            "evolve",
            "through the day",
            "stayed hotter",
            "hotter later",
            "changed in thermal",
            "fortyguard data change",
        )
    ):
        return IntentCode.DIURNAL_HEAT_TRANSITION

    # 4. Heat Vulnerability / Facility Exposure
    if any(
        kw in q_lower
        for kw in (
            "vulnerability",
            "vulnerable",
            "thermal exposure",
            "heat exposure",
            "exposure",
            "density",
            "combine high heat",
            "combines heat",
            "shaw",
            "mlk",
            "martin",
            "luther",
            "king",
            "randall",
            "northeast",
            "southeast",
            "southwest",
            "dc_089",
            "dc_135",
            "dc_148",
            "dc_159",
            "dc_166",
            "dc_168",
            "why is ",
            "why martin",
            "evidence supports",
            "what thermal and population",
        )
    ):
        return IntentCode.HEAT_VULNERABILITY_EXPLANATION

    return IntentCode.ALLOCATION_SUMMARY


# -----------------------------------------------------------------------------
# Model Gateway Protocol & Test Doubles
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

    Triggers intent-aware deterministic fallback without pretending to be AI.
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

        if is_unsupported_question(context.question):
            return None

        inferred = infer_intent_from_question(context.question)
        avail = context.available_facility_ids or VALID_FACILITY_IDS
        selected = set(context.selected_facility_ids)
        unselected = [fid for fid in avail if fid not in selected]
        normalized_question = re.sub(
            r"[^a-z0-9]+", " ", context.question.casefold()
        ).strip()
        alias_map = {
            "DC_089": ("dc 089", "dc089", "shaw", "watha"),
            "DC_135": ("dc 135", "dc135", "mlk", "martin luther king"),
            "DC_148": ("dc 148", "dc148", "northeast"),
            "DC_159": ("dc 159", "dc159", "southeast"),
            "DC_166": ("dc 166", "dc166", "randall"),
            "DC_168": ("dc 168", "dc168", "southwest"),
        }
        explicit: list[tuple[int, str]] = []
        padded_question = f" {normalized_question} "
        for fid in avail:
            positions = [
                padded_question.find(f" {alias} ")
                for alias in alias_map.get(fid, ())
                if padded_question.find(f" {alias} ") >= 0
            ]
            if positions:
                explicit.append((min(positions), fid))
        explicit_fids = [fid for _, fid in sorted(explicit)]

        fac1 = explicit_fids[0] if explicit_fids else (avail[0] if avail else "DC_135")
        fac2 = (
            explicit_fids[1]
            if len(explicit_fids) > 1
            else (avail[1] if len(avail) > 1 else "DC_148")
        )

        if inferred == IntentCode.REPLACEMENT_RATIONALE:
            if len(explicit_fids) >= 2:
                pair_selected = [fid for fid in explicit_fids[:2] if fid in selected]
                pair_unselected = [fid for fid in explicit_fids[:2] if fid not in selected]
                if len(pair_selected) == 1 and len(pair_unselected) == 1:
                    fac1, fac2 = pair_selected[0], pair_unselected[0]
            elif explicit_fids and selected:
                if explicit_fids[0] in selected:
                    fac1 = explicit_fids[0]
                    fac2 = unselected[0]
                else:
                    fac1 = next(iter(context.selected_facility_ids))
                    fac2 = explicit_fids[0]
            elif selected and unselected:
                fac1 = next(iter(context.selected_facility_ids))
                fac2 = unselected[0]
            return GatewayToolSelection(
                intent_code=IntentCode.REPLACEMENT_RATIONALE,
                tool_calls=(
                    ToolCall(
                        tool_name=ToolName.GET_REPLACEMENT_EVIDENCE,
                        facility_id=fac1,
                        alternative_id=fac2,
                    ),
                ),
            )
        elif inferred == IntentCode.HEAT_VULNERABILITY_EXPLANATION:
            return GatewayToolSelection(
                intent_code=IntentCode.HEAT_VULNERABILITY_EXPLANATION,
                tool_calls=(
                    ToolCall(
                        tool_name=ToolName.GET_HEAT_VULNERABILITY_PROFILE,
                        facility_id=fac1,
                    ),
                ),
            )
        elif inferred == IntentCode.DIURNAL_HEAT_TRANSITION:
            return GatewayToolSelection(
                intent_code=IntentCode.DIURNAL_HEAT_TRANSITION,
                tool_calls=(
                    ToolCall(
                        tool_name=ToolName.GET_DIURNAL_HEAT_TRANSITION,
                        target_timestamp="20:00",
                    ),
                ),
            )
        elif inferred == IntentCode.BASELINE_COMPARISON:
            return GatewayToolSelection(
                intent_code=IntentCode.BASELINE_COMPARISON,
                tool_calls=(
                    ToolCall(
                        tool_name=ToolName.GET_BASELINE_COMPARISON,
                        baseline_type="all",
                    ),
                ),
            )
        else:
            return GatewayToolSelection(
                intent_code=IntentCode.ALLOCATION_SUMMARY,
                tool_calls=(ToolCall(tool_name=ToolName.GET_ALLOCATION_PLAN),),
            )

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
    radius_meters: int = 750,
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
    allocation_timestamp = format_timestamp_display(opt.state_id.replace("state_dc_", ""))

    claims: list[ClaimRecord] = []

    name_map = scenario.get_facility_name_map()
    fac_names = [name_map.get(fid, fid) for fid in sel_ids]
    fac_list_str = ", ".join(
        f"'{name}' ({fid})" for name, fid in zip(fac_names, sel_ids, strict=False)
    )

    claims.append(
        ClaimRecord(
            claim_id="claim:alloc:summary",
            claim_type="allocation_summary",
            timestamp=allocation_timestamp,
            value={
                "k": k,
                "selected_ids": list(sel_ids),
                "covered_heat_weighted_demand": cov_demand,
                "covered_population": cov_pop,
                "coverage_percentage": cov_pct,
                "radius_meters": radius_meters,
            },
            display_text=(
                f"At {allocation_timestamp} UTC, the authoritative CoolAccess optimizer "
                f"selected {len(sel_ids)} optimal "
                f"facilities ({fac_list_str}) under facility-count budget k={k} and a "
                f"{radius_meters} m catchment radius, "
                f"covering {cov_demand:.2f} heat-weighted demand units "
                f"({cov_pct:.1f}% of total demand) and {cov_pop:,} residential population "
                f"({(cov_pop / tot_pop * 100.0) if tot_pop > 0 else 0.0:.1f}% of AOI population)."
            ),
        )
    )

    for pfc in cov.per_facility:
        fid = pfc.facility_id
        fname = name_map.get(fid, fid)
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
                    f"Selected facility '{fname}' ({fid}) covers {d_pop:,} residential "
                    f"population with {d_demand:.2f} direct heat-weighted demand units "
                    f"({u_demand:.2f} unique)."
                ),
            )
        )

    tb = opt.tie_break
    claims.append(
        ClaimRecord(
            claim_id="claim:alloc:tie_break",
            claim_type="tie_break_audit",
            timestamp=allocation_timestamp,
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
    """Pure read-only projection: Return added/removed facilities and optimization shift."""
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

    name_map = scenario.get_facility_name_map()
    added_names = [name_map.get(fid, fid) for fid in added]
    removed_names = [name_map.get(fid, fid) for fid in removed]
    retained_names = [name_map.get(fid, fid) for fid in retained]

    added_str = (
        ", ".join(f"{n} ({i})" for n, i in zip(added_names, added, strict=False)) or "none"
    )
    removed_str = (
        ", ".join(f"{n} ({i})" for n, i in zip(removed_names, removed, strict=False)) or "none"
    )

    if added or removed:
        shift_desc = (
            f"Between {from_fmt} UTC and {to_fmt} UTC, the authoritative optimal allocation "
            f"changed under the same k={k} facility-count budget and {radius_meters} m radius: "
            f"added {added_str}, removed {removed_str}, and retained "
            f"{', '.join(retained_names)}."
        )
        context_text = (
            f"Using the prepared FortyGuard thermal state at {to_fmt} UTC, the deterministic "
            f"optimizer returned a different facility set than at {from_fmt} UTC. The exact "
            "added and removed facilities are listed in the transition evidence."
        )
    else:
        retained_str = ", ".join(
            f"{name_map.get(fid, fid)} ({fid})" for fid in sorted(retained)
        )
        shift_desc = (
            f"Between {from_fmt} UTC and {to_fmt} UTC, the authoritative optimal allocation "
            f"remained unchanged under the same k={k} facility-count budget and "
            f"{radius_meters} m radius: {retained_str}."
        )
        context_text = (
            f"The prepared FortyGuard thermal inputs differ between {from_fmt} UTC and "
            f"{to_fmt} UTC, but recomputing the deterministic objective returned the same "
            "selected facility set. Temperature change alone does not imply an allocation change."
        )

    from_key = sanitize_timestamp_key(from_ts)
    to_key = sanitize_timestamp_key(to_ts)

    claims.append(
        ClaimRecord(
            claim_id=f"claim:diurnal:{from_key}:{to_key}:transition",
            claim_type="diurnal_transition",
            timestamp=to_ts,
            value={
                "from_timestamp": from_fmt,
                "to_timestamp": to_fmt,
                "added": added,
                "removed": removed,
                "retained": retained,
                "allocation_changed": bool(added or removed),
                "radius_meters": radius_meters,
                "k": k,
            },
            display_text=shift_desc,
        )
    )

    claims.append(
        ClaimRecord(
            claim_id=f"claim:diurnal:{from_key}:{to_key}:retention",
            claim_type="thermal_shift_context",
            timestamp=to_ts,
            value={
                "allocation_changed": bool(added or removed),
            },
            display_text=context_text,
        )
    )

    return tuple(claims)


def _tool_get_diurnal_thermal_profile(
    scenario: ScenarioBundle,
    from_ts: str,
    to_ts: str,
) -> tuple[ClaimRecord, ...]:
    """Pure read-only projection: Return empirical FortyGuard 100m raster thermal statistics."""
    stats = scenario.get_thermal_statistics(from_ts, to_ts)
    from_fmt = format_timestamp_display(from_ts)
    to_fmt = format_timestamp_display(to_ts)
    from_key = sanitize_timestamp_key(from_ts)
    to_key = sanitize_timestamp_key(to_ts)

    claims: list[ClaimRecord] = []

    dist_text = (
        f"Measured FortyGuard 100m raster temperatures across the study area averaged "
        f"{stats['from_stats']['mean_c']:.2f}°C (range {stats['from_stats']['min_c']:.2f}°C to "
        f"{stats['from_stats']['max_c']:.2f}°C, p90 {stats['from_stats']['p90_c']:.2f}°C) "
        f"at {from_fmt} UTC, shifting to an average of {stats['to_stats']['mean_c']:.2f}°C "
        f"(range {stats['to_stats']['min_c']:.2f}°C to {stats['to_stats']['max_c']:.2f}°C, "
        f"p90 {stats['to_stats']['p90_c']:.2f}°C) at {to_fmt} UTC "
        f"(study area mean temperature delta: {stats['mean_temp_delta_c']:+.2f}°C)."
    )
    claims.append(
        ClaimRecord(
            claim_id=f"claim:thermal:{from_key}:{to_key}:distribution",
            claim_type="thermal_distribution_profile",
            timestamp=to_ts,
            value=stats,
            display_text=dist_text,
        )
    )

    priority_text = (
        f"Under fixed robust normalization anchors (32.02°C to 37.70°C), "
        f"{stats['to_high_priority_cells']} of {stats['total_tiles']} grid cells meet the "
        f"elevated thermal-priority weight threshold (>0.70) at {to_fmt} UTC, compared to "
        f"{stats['from_high_priority_cells']} cells at {from_fmt} UTC "
        f"(net change: {stats['high_priority_cell_delta']:+d} cells)."
    )
    claims.append(
        ClaimRecord(
            claim_id=f"claim:thermal:{from_key}:{to_key}:priority_shift",
            claim_type="thermal_priority_shift",
            timestamp=to_ts,
            value={
                "from_high_priority_cells": stats["from_high_priority_cells"],
                "to_high_priority_cells": stats["to_high_priority_cells"],
                "high_priority_cell_delta": stats["high_priority_cell_delta"],
                "threshold": 0.70,
            },
            display_text=priority_text,
        )
    )

    return tuple(claims)


def _tool_get_heat_vulnerability_profile(
    facility_id: str,
    analysis: AllocationAnalysisResult,
    scenario: ScenarioBundle,
    timestamp: str = "16:00",
    radius_meters: int = 750,
) -> tuple[ClaimRecord, ...]:
    """Pure read-only projection: Return thermal priority and residential population context."""
    name_map = scenario.get_facility_name_map()
    address_map = scenario.get_facility_address_map()
    if facility_id not in name_map:
        return (
            ClaimRecord(
                claim_id=f"claim:vulnerability:{facility_id}:not_found",
                claim_type="facility_not_found",
                facility_id=facility_id,
                display_text=f"Facility '{facility_id}' not found in scenario directory.",
            ),
        )

    fname = name_map[facility_id]
    faddress = address_map.get(facility_id, "")
    opt = analysis.optimized
    is_selected = facility_id in opt.selected_facility_ids

    pfc = next((p for p in opt.coverage.per_facility if p.facility_id == facility_id), None)
    if pfc:
        pop = int(pfc.direct_population)
        demand = float(pfc.direct_heat_weighted_demand)
        block_count = len(pfc.direct_cell_ids)
    else:
        req = scenario.build_allocation_request(
            timestamp=timestamp,
            radius_meters=radius_meters,
            k=opt.k,
        )
        accessible_cells = {
            edge.cell_id
            for edge in req.accessibility_relationships
            if edge.facility_id == facility_id and edge.is_accessible
        }
        cells_dict = {c.cell_id: c for c in req.demand_cells}
        pop = 0
        demand = 0.0
        block_count = len(accessible_cells)
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
                "radius_meters": radius_meters,
            },
            display_text=(
                f"Facility '{fname}' ({facility_id}"
                f"{f', {faddress}' if faddress else ''}) is {status_str}: "
                f"has {pop:,} residents within its {radius_meters} m catchment across "
                f"{block_count} census blocks, generating {demand:.2f} heat-weighted "
                f"demand units with mean normalized thermal priority weight {mean_thermal:.3f}."
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
                f"Facility '{fname}' ({facility_id}) operates with mean normalized thermal "
                f"priority weight {mean_thermal:.3f} across accessible census blocks "
                f"under FortyGuard 100m thermal measurement."
            ),
        )
    )

    return tuple(claims)


def _tool_get_replacement_evidence(
    selected_id: str,
    alternative_id: str,
    analysis: AllocationAnalysisResult,
    scenario: ScenarioBundle,
    radius_meters: int = 750,
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

    name_map = scenario.get_facility_name_map()
    sel_name = name_map.get(selected_id, selected_id)
    alt_name = name_map.get(alternative_id, alternative_id)

    if not rep:
        from coolaccess.replacement import build_replacement_evidence
        opt = analysis.optimized
        all_fids = scenario.get_facility_ids()
        if (
            selected_id in opt.selected_facility_ids
            and alternative_id in all_fids
            and alternative_id not in opt.selected_facility_ids
        ):
            ts_val = opt.state_id.replace("state_dc_", "")
            req = scenario.build_allocation_request(
                timestamp=ts_val,
                radius_meters=radius_meters,
                k=opt.k,
            )
            rep = build_replacement_evidence(req, opt, selected_id, alternative_id)

    if not rep:
        selected_set = set(analysis.optimized.selected_facility_ids)
        if selected_id in selected_set and alternative_id in selected_set:
            pair_text = (
                f"'{sel_name}' ({selected_id}) and '{alt_name}' ({alternative_id}) are both "
                "selected in the authoritative allocation at this timestamp, so neither "
                "replaced the other and no one-for-one replacement loss applies."
            )
            pair_status = "both_selected"
        elif selected_id not in selected_set and alternative_id not in selected_set:
            pair_text = (
                f"'{sel_name}' ({selected_id}) and '{alt_name}' ({alternative_id}) are both "
                "unselected in the authoritative allocation at this timestamp, so they do "
                "not form a selected-versus-alternative replacement pair."
            )
            pair_status = "both_unselected"
        else:
            pair_text = (
                f"No authoritative replacement record exists for selected '{selected_id}' "
                f"and alternative '{alternative_id}' at this timestamp."
            )
            pair_status = "invalid_direction"
        return (
            ClaimRecord(
                claim_id=f"claim:rep:{selected_id}:{alternative_id}:pair_context",
                claim_type="replacement_pair_context",
                facility_id=selected_id,
                alternative_id=alternative_id,
                value={"pair_status": pair_status},
                display_text=pair_text,
            ),
        )

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
                "radius_meters": radius_meters,
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
            f"While '{alt_name}' ({alternative_id}) covers +{pop_delta:,} more residential "
            f"population within its catchment, '{sel_name}' ({selected_id}) provides higher "
            f"heat-weighted demand coverage due to higher normalized thermal priority across "
            f"its accessible census blocks."
        )
    elif pop_delta < 0:
        pop_tradeoff_text = (
            f"Alternative '{alt_name}' ({alternative_id}) covers {abs(pop_delta):,} fewer "
            f"residents while also providing lower total "
            f"heat-weighted demand coverage."
        )
    else:
        pop_tradeoff_text = (
            f"Both facilities cover equal residential population, but '{sel_name}' ({selected_id}) "
            f"achieves higher heat-weighted demand coverage."
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

            if abs(s_gain) < 0.005:
                static_text = (
                    f"The dynamic allocation matches the static baseline at "
                    f"{cov_demand:.2f} heat-weighted demand units under the same "
                    f"facility-count budget; there is no objective gain at this timestamp."
                )
            elif s_gain > 0:
                static_text = (
                    f"The dynamic allocation covers {s_gain:.2f} more heat-weighted demand "
                    f"units than the static baseline ({s_pct:.2f}% gain) under the same "
                    "facility-count budget."
                )
            else:
                static_text = (
                    f"The dynamic allocation covers {abs(s_gain):.2f} fewer heat-weighted "
                    f"demand units than the static baseline ({abs(s_pct):.2f}% lower) under "
                    "the same facility-count budget."
                )

            claims.append(
                ClaimRecord(
                    claim_id="claim:base:static:gain",
                    claim_type="static_baseline_comparison",
                    value={
                        "baseline_objective": s_obj,
                        "optimized_objective": cov_demand,
                        "absolute_gain": s_gain,
                        "percentage_gain": s_pct,
                        "baseline_selected_ids": list(static_res.selected_facility_ids),
                        "optimized_selected_ids": list(opt.selected_facility_ids),
                    },
                    display_text=static_text,
                )
            )

    if baseline_type in ("naive", "naive_thermal", "all"):
        naive_res = analysis.naive_baseline
        if isinstance(naive_res, CompleteBaselineResult):
            n_obj = float(naive_res.objective_value)
            n_gain = cov_demand - n_obj
            n_pct = (n_gain / n_obj * 100.0) if n_obj > 0 else 0.0

            if abs(n_gain) < 0.005:
                naive_text = (
                    f"The dynamic optimum matches the naive hottest-catchment baseline: both "
                    f"select {', '.join(opt.selected_facility_ids)} and produce the same "
                    f"{cov_demand:.2f} heat-weighted demand objective. There is no gain over "
                    "the naive baseline at this timestamp."
                )
            elif n_gain > 0:
                naive_text = (
                    f"The dynamic optimum covers {n_gain:.2f} more heat-weighted demand units "
                    f"than the naive hottest-catchment baseline ({n_pct:.2f}% gain) under the "
                    "same facility-count budget."
                )
            else:
                naive_text = (
                    f"The dynamic optimum covers {abs(n_gain):.2f} fewer heat-weighted demand "
                    f"units than the naive hottest-catchment baseline ({abs(n_pct):.2f}% lower) "
                    "under the same facility-count budget."
                )

            claims.append(
                ClaimRecord(
                    claim_id="claim:base:naive:gain",
                    claim_type="naive_baseline_comparison",
                    value={
                        "baseline_objective": n_obj,
                        "optimized_objective": cov_demand,
                        "absolute_gain": n_gain,
                        "percentage_gain": n_pct,
                        "baseline_selected_ids": list(naive_res.selected_facility_ids),
                        "optimized_selected_ids": list(opt.selected_facility_ids),
                    },
                    display_text=naive_text,
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
    """Execute a single bounded read-only tool with scenario-validated arguments."""
    valid_facility_ids = set(scenario.get_facility_ids())
    valid_timestamps = set(scenario.get_timestamps())

    if call.tool_name == ToolName.GET_ALLOCATION_PLAN:
        claims = _tool_get_allocation_plan(analysis, scenario, radius_meters=radius_meters)
        return ToolExecutionResult(tool_name=call.tool_name, claims=claims)

    if call.tool_name == ToolName.GET_DIURNAL_HEAT_TRANSITION:
        target_ts = call.target_timestamp or timestamp
        if target_ts not in valid_timestamps and target_ts not in VALID_TIMESTAMPS:
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

    if call.tool_name == ToolName.GET_DIURNAL_THERMAL_PROFILE:
        target_ts = call.target_timestamp or timestamp
        if target_ts not in valid_timestamps and target_ts not in VALID_TIMESTAMPS:
            raise ValueError(f"Invalid timestamp '{target_ts}' for {call.tool_name}")
        claims = _tool_get_diurnal_thermal_profile(
            scenario,
            from_ts=baseline_timestamp,
            to_ts=target_ts,
        )
        return ToolExecutionResult(
            tool_name=call.tool_name,
            target_timestamp=target_ts,
            claims=claims,
        )

    if call.tool_name == ToolName.GET_HEAT_VULNERABILITY_PROFILE:
        if not call.facility_id or (
            call.facility_id not in valid_facility_ids
            and call.facility_id not in VALID_FACILITY_IDS
        ):
            raise ValueError(f"Invalid facility_id '{call.facility_id}' for {call.tool_name}")
        claims = _tool_get_heat_vulnerability_profile(
            facility_id=call.facility_id,
            analysis=analysis,
            scenario=scenario,
            timestamp=timestamp,
            radius_meters=radius_meters,
        )
        return ToolExecutionResult(
            tool_name=call.tool_name,
            facility_id=call.facility_id,
            claims=claims,
        )

    if call.tool_name == ToolName.GET_REPLACEMENT_EVIDENCE:
        selected_ids = analysis.optimized.selected_facility_ids
        default_sel = selected_ids[0] if selected_ids else "DC_135"
        eligible_unsel = [fid for fid in scenario.get_facility_ids() if fid not in selected_ids]
        default_unsel = eligible_unsel[0] if eligible_unsel else "DC_148"

        sel_id = call.facility_id or default_sel
        alt_id = call.alternative_id or default_unsel
        all_valid = valid_facility_ids | set(VALID_FACILITY_IDS)
        if sel_id not in all_valid or alt_id not in all_valid:
            raise ValueError(f"Invalid facility IDs '{sel_id}', '{alt_id}' for {call.tool_name}")
        claims = _tool_get_replacement_evidence(
            selected_id=sel_id,
            alternative_id=alt_id,
            analysis=analysis,
            scenario=scenario,
            radius_meters=radius_meters,
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


# -----------------------------------------------------------------------------
# Deterministic Evidence Planner
# -----------------------------------------------------------------------------


def plan_deterministic_evidence(
    question: str,
    intent_code: IntentCode,
    suggested_calls: Sequence[ToolCall],
    scenario: ScenarioBundle,
    analysis: AllocationAnalysisResult,
    timestamp: str,
    baseline_timestamp: str,
    max_budget: int = MAX_TOOL_CALLS,
) -> tuple[ToolCall, ...]:
    """Build a bounded authoritative evidence plan.

    Explicit facilities in the user's text are deterministic and take priority.
    Model suggestions may fill missing entities or add optional evidence only.
    """
    if max_budget < 1:
        return ()

    valid_fids = scenario.get_facility_ids()
    valid_fid_set = set(valid_fids)
    selected_fids = list(analysis.optimized.selected_facility_ids)
    selected_set = set(selected_fids)
    unselected_fids = [fid for fid in valid_fids if fid not in selected_set]
    explicit_fids = [
        fid for fid in scenario.resolve_facilities(question) if fid in valid_fid_set
    ]

    suggested_fids: list[str] = []
    for call in suggested_calls:
        for fid in (call.facility_id, call.alternative_id):
            if fid and fid in valid_fid_set and fid not in suggested_fids:
                suggested_fids.append(fid)
    mentioned_fids = [*explicit_fids]
    for fid in suggested_fids:
        if fid not in mentioned_fids:
            mentioned_fids.append(fid)

    q_lower = question.casefold()
    available_timestamps = scenario.get_timestamps()
    target_ts = timestamp
    explicit_time = False
    time_mentions: list[tuple[int, str]] = []
    for ts in available_timestamps:
        hour_int = int(ts[:2])
        twelve_hour = hour_int % 12 or 12
        labels = (
            ts,
            ts.replace(":", ""),
            f"{twelve_hour}pm" if hour_int >= 12 else f"{twelve_hour}am",
            f"{twelve_hour} pm" if hour_int >= 12 else f"{twelve_hour} am",
        )
        positions = [
            match.start()
            for label in labels
            if (match := re.search(rf"(?<!\d){re.escape(label)}(?!\d)", q_lower))
        ]
        if positions:
            time_mentions.append((min(positions), ts))
    if time_mentions:
        target_ts = max(time_mentions)[1]
        explicit_time = True
    if not explicit_time:
        target_ts = next(
            (
                call.target_timestamp
                for call in suggested_calls
                if call.target_timestamp in available_timestamps
            ),
            target_ts,
        )
    if (
        target_ts == baseline_timestamp
        and baseline_timestamp == "16:00"
        and intent_code == IntentCode.DIURNAL_HEAT_TRANSITION
        and not explicit_time
        and "20:00" in available_timestamps
    ):
        target_ts = "20:00"

    planned: list[ToolCall] = []

    if intent_code == IntentCode.ALLOCATION_SUMMARY:
        planned.append(ToolCall(tool_name=ToolName.GET_ALLOCATION_PLAN))
        target_fid = next(iter(mentioned_fids), next(iter(selected_fids), None))
        if target_fid:
            planned.append(
                ToolCall(
                    tool_name=ToolName.GET_HEAT_VULNERABILITY_PROFILE,
                    facility_id=target_fid,
                )
            )

    elif intent_code == IntentCode.DIURNAL_HEAT_TRANSITION:
        planned.extend(
            (
                ToolCall(
                    tool_name=ToolName.GET_DIURNAL_HEAT_TRANSITION,
                    target_timestamp=target_ts,
                ),
                ToolCall(
                    tool_name=ToolName.GET_DIURNAL_THERMAL_PROFILE,
                    target_timestamp=target_ts,
                ),
                ToolCall(tool_name=ToolName.GET_ALLOCATION_PLAN),
            )
        )
        if mentioned_fids:
            planned.append(
                ToolCall(
                    tool_name=ToolName.GET_HEAT_VULNERABILITY_PROFILE,
                    facility_id=mentioned_fids[0],
                )
            )

    elif intent_code == IntentCode.HEAT_VULNERABILITY_EXPLANATION:
        target_fids = mentioned_fids[:2] or selected_fids[:1]
        for fid in target_fids:
            planned.append(
                ToolCall(
                    tool_name=ToolName.GET_HEAT_VULNERABILITY_PROFILE,
                    facility_id=fid,
                )
            )
        planned.append(ToolCall(tool_name=ToolName.GET_ALLOCATION_PLAN))
        if len(target_fids) == 1:
            planned.append(
                ToolCall(
                    tool_name=ToolName.GET_DIURNAL_THERMAL_PROFILE,
                    target_timestamp=timestamp,
                )
            )

    elif intent_code == IntentCode.REPLACEMENT_RATIONALE:
        sel_candidate: str | None
        alt_candidate: str | None
        if len(explicit_fids) >= 2:
            explicit_selected = [fid for fid in explicit_fids[:2] if fid in selected_set]
            explicit_unselected = [fid for fid in explicit_fids[:2] if fid not in selected_set]
            if len(explicit_selected) == 1 and len(explicit_unselected) == 1:
                sel_candidate = explicit_selected[0]
                alt_candidate = explicit_unselected[0]
            else:
                # A false pairwise premise (both selected or both unselected) is preserved so
                # the evidence tool can state that no replacement relationship exists.
                sel_candidate, alt_candidate = explicit_fids[:2]
        else:
            explicit_fid = explicit_fids[0] if explicit_fids else None
            sel_candidate = explicit_fid if explicit_fid in selected_set else None
            alt_candidate = (
                explicit_fid
                if explicit_fid and explicit_fid not in selected_set
                else None
            )

            transition = scenario.metadata.get("primary_transition", {})
            transition_selected = transition.get("activated_facility")
            transition_unselected = transition.get("replaced_facility")
            if (
                alt_candidate == transition_unselected
                and transition_selected in selected_set
            ):
                sel_candidate = transition_selected
            elif (
                alt_candidate == transition_selected
                and transition_unselected in selected_set
            ):
                sel_candidate = transition_unselected
            elif (
                sel_candidate == transition_selected
                and transition_unselected in unselected_fids
            ):
                alt_candidate = transition_unselected
            elif (
                sel_candidate == transition_unselected
                and transition_selected in unselected_fids
            ):
                alt_candidate = transition_selected

            if sel_candidate is None:
                sel_candidate = next(
                    (fid for fid in suggested_fids if fid in selected_set),
                    selected_fids[0],
                )
            if alt_candidate is None:
                alt_candidate = next(
                    (fid for fid in suggested_fids if fid in unselected_fids),
                    unselected_fids[0],
                )

        planned.extend(
            (
                ToolCall(
                    tool_name=ToolName.GET_REPLACEMENT_EVIDENCE,
                    facility_id=sel_candidate,
                    alternative_id=alt_candidate,
                ),
                ToolCall(
                    tool_name=ToolName.GET_HEAT_VULNERABILITY_PROFILE,
                    facility_id=sel_candidate,
                ),
                ToolCall(
                    tool_name=ToolName.GET_HEAT_VULNERABILITY_PROFILE,
                    facility_id=alt_candidate,
                ),
                ToolCall(tool_name=ToolName.GET_ALLOCATION_PLAN),
            )
        )

    elif intent_code == IntentCode.BASELINE_COMPARISON:
        baseline_type = next(
            (
                call.baseline_type
                for call in suggested_calls
                if call.tool_name == ToolName.GET_BASELINE_COMPARISON
                and call.baseline_type
                in {"static", "static_allocation", "naive", "naive_thermal", "all"}
            ),
            "all",
        )
        planned.extend(
            (
                ToolCall(
                    tool_name=ToolName.GET_BASELINE_COMPARISON,
                    baseline_type=baseline_type,
                ),
                ToolCall(tool_name=ToolName.GET_ALLOCATION_PLAN),
                ToolCall(
                    tool_name=ToolName.GET_DIURNAL_THERMAL_PROFILE,
                    target_timestamp=timestamp,
                ),
            )
        )

    # Optional model-suggested evidence comes after deterministic mandatory evidence.
    for call in suggested_calls:
        if len(planned) >= max_budget:
            break
        planned.append(call)

    unique_planned: list[ToolCall] = []
    for call in planned:
        if call not in unique_planned:
            unique_planned.append(call)

    return tuple(unique_planned[:max_budget])


def validate_tool_selection_semantics(
    tool_selection: GatewayToolSelection,
    available_facility_ids: Sequence[str] = VALID_FACILITY_IDS,
    available_timestamps: Sequence[str] = VALID_TIMESTAMPS,
    *,
    expected_intent: IntentCode | None = None,
    explicit_facility_ids: Sequence[str] = (),
    selected_facility_ids: Sequence[str] = (),
    require_mandatory_evidence: bool = False,
) -> ToolSelectionValidationIssue | None:
    """Validate model or final evidence tool calls before execution."""
    if not tool_selection.tool_calls:
        return ToolSelectionValidationIssue.NO_TOOL_CALLS

    if len(tool_selection.tool_calls) > MAX_TOOL_CALLS:
        return ToolSelectionValidationIssue.TOO_MANY_TOOL_CALLS

    if expected_intent is not None and tool_selection.intent_code != expected_intent:
        return ToolSelectionValidationIssue.INTENT_MISMATCH

    facility_id_set = set(available_facility_ids)
    timestamp_set = set(available_timestamps)
    selected_id_set = set(selected_facility_ids)

    for call in tool_selection.tool_calls:
        if call.tool_name == ToolName.GET_ALLOCATION_PLAN:
            if any(
                value is not None
                for value in (
                    call.facility_id,
                    call.alternative_id,
                    call.target_timestamp,
                    call.baseline_type,
                )
            ):
                return ToolSelectionValidationIssue.INVALID_ALLOCATION_ARGUMENTS
        elif call.tool_name == ToolName.GET_HEAT_VULNERABILITY_PROFILE:
            if not call.facility_id or call.facility_id not in facility_id_set:
                return ToolSelectionValidationIssue.INVALID_FACILITY_ID
            if any(
                value is not None
                for value in (call.alternative_id, call.target_timestamp, call.baseline_type)
            ):
                return ToolSelectionValidationIssue.INVALID_FACILITY_TOOL_ARGUMENTS
        elif call.tool_name in (
            ToolName.GET_DIURNAL_HEAT_TRANSITION,
            ToolName.GET_DIURNAL_THERMAL_PROFILE,
        ):
            if call.tool_name == ToolName.GET_DIURNAL_HEAT_TRANSITION and not call.target_timestamp:
                return ToolSelectionValidationIssue.INVALID_TIMESTAMP
            if call.target_timestamp and call.target_timestamp not in timestamp_set:
                return ToolSelectionValidationIssue.INVALID_TIMESTAMP
            if any(
                value is not None
                for value in (call.facility_id, call.alternative_id, call.baseline_type)
            ):
                return ToolSelectionValidationIssue.INVALID_TIMESTAMP
        elif call.tool_name == ToolName.GET_REPLACEMENT_EVIDENCE:
            if (
                not call.facility_id
                or not call.alternative_id
                or call.facility_id == call.alternative_id
            ):
                return ToolSelectionValidationIssue.INVALID_REPLACEMENT_ARGUMENTS
            if (
                call.facility_id not in facility_id_set
                or call.alternative_id not in facility_id_set
            ):
                return ToolSelectionValidationIssue.INVALID_FACILITY_ID
            if call.target_timestamp is not None or call.baseline_type is not None:
                return ToolSelectionValidationIssue.INVALID_REPLACEMENT_ARGUMENTS

            if selected_id_set:
                facility_selected = call.facility_id in selected_id_set
                alternative_selected = call.alternative_id in selected_id_set
                if facility_selected != alternative_selected and not facility_selected:
                    return ToolSelectionValidationIssue.INVALID_REPLACEMENT_DIRECTION
                if facility_selected == alternative_selected:
                    explicit_pair = set(explicit_facility_ids[:2])
                    if len(explicit_pair) != 2 or explicit_pair != {
                        call.facility_id,
                        call.alternative_id,
                    }:
                        return ToolSelectionValidationIssue.INVALID_REPLACEMENT_DIRECTION
        elif call.tool_name == ToolName.GET_BASELINE_COMPARISON:
            if call.baseline_type not in {
                None,
                "static",
                "static_allocation",
                "naive",
                "naive_thermal",
                "all",
            }:
                return ToolSelectionValidationIssue.INVALID_BASELINE_ARGUMENTS
            if any(
                value is not None
                for value in (call.facility_id, call.alternative_id, call.target_timestamp)
            ):
                return ToolSelectionValidationIssue.INVALID_BASELINE_ARGUMENTS
        else:
            return ToolSelectionValidationIssue.UNKNOWN_TOOL

    explicit_ids = tuple(fid for fid in explicit_facility_ids if fid in facility_id_set)
    supplied_ids = {
        fid
        for call in tool_selection.tool_calls
        for fid in (call.facility_id, call.alternative_id)
        if fid is not None
    }
    if explicit_ids and supplied_ids:
        explicit_set = set(explicit_ids)
        if len(explicit_ids) >= 2 and not supplied_ids.issubset(explicit_set):
            return ToolSelectionValidationIssue.EXPLICIT_ENTITY_CONFLICT
        if len(explicit_ids) == 1 and explicit_ids[0] not in supplied_ids:
            return ToolSelectionValidationIssue.EXPLICIT_ENTITY_CONFLICT

    if tool_selection.intent_code == IntentCode.REPLACEMENT_RATIONALE:
        replacement_calls = [
            call
            for call in tool_selection.tool_calls
            if call.tool_name == ToolName.GET_REPLACEMENT_EVIDENCE
        ]
        if not replacement_calls:
            return ToolSelectionValidationIssue.REPLACEMENT_MISSING_TOOL
        if len(explicit_ids) >= 2 and {
            replacement_calls[0].facility_id,
            replacement_calls[0].alternative_id,
        } != set(explicit_ids[:2]):
            return ToolSelectionValidationIssue.EXPLICIT_ENTITY_CONFLICT

    if require_mandatory_evidence:
        tool_names = {call.tool_name for call in tool_selection.tool_calls}
        required_tools = {
            IntentCode.ALLOCATION_SUMMARY: {ToolName.GET_ALLOCATION_PLAN},
            IntentCode.DIURNAL_HEAT_TRANSITION: {
                ToolName.GET_DIURNAL_HEAT_TRANSITION,
                ToolName.GET_DIURNAL_THERMAL_PROFILE,
                ToolName.GET_ALLOCATION_PLAN,
            },
            IntentCode.HEAT_VULNERABILITY_EXPLANATION: {
                ToolName.GET_HEAT_VULNERABILITY_PROFILE,
                ToolName.GET_ALLOCATION_PLAN,
            },
            IntentCode.REPLACEMENT_RATIONALE: {
                ToolName.GET_REPLACEMENT_EVIDENCE,
                ToolName.GET_HEAT_VULNERABILITY_PROFILE,
                ToolName.GET_ALLOCATION_PLAN,
            },
            IntentCode.BASELINE_COMPARISON: {
                ToolName.GET_BASELINE_COMPARISON,
                ToolName.GET_ALLOCATION_PLAN,
            },
        }[tool_selection.intent_code]
        if not required_tools.issubset(tool_names):
            return ToolSelectionValidationIssue.MISSING_MANDATORY_EVIDENCE

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


def _extract_safe_fallback_reason(exc: Exception, default_reason: str) -> str:
    msg = str(exc)
    if msg.startswith("AI provider unavailable (") and msg.endswith(")"):
        inner = msg[len("AI provider unavailable (") : -1]
        return f"{inner}; returning an authoritative deterministic heat intelligence summary."
    return default_reason


def _build_unsupported_scope_response(
    analysis: AllocationAnalysisResult,
    scenario: ScenarioBundle,
    question: str,
    reason: str = "Inquiry outside closed heat intelligence intent scope.",
    timestamp: str = "16:00",
    radius_meters: int = 750,
    k: int = 3,
) -> HeatBriefResponse:
    """Construct a clean, non-error UNSUPPORTED scope boundary response."""
    return HeatBriefResponse(
        status=CopilotStatus.UNSUPPORTED,
        intent_code=None,
        scenario_id=analysis.optimized.scenario_id,
        plan_fingerprint=compute_allocation_fingerprint(analysis),
        timestamp=format_timestamp_display(timestamp),
        radius_meters=radius_meters,
        k=k,
        title="Inquiry Outside Municipal Cooling Scope",
        brief_items=[
            BriefItem(
                claim_id="claim:scope:unsupported",
                server_rendered_text=(
                    "This inquiry is outside the operational scope of CoolAccess. "
                    "CoolAccess is an evidence-grounded municipal cooling resource allocation "
                    "engine operating on prepared historical FortyGuard 100m thermal data. "
                    "It cannot provide medical or health advice, live weather forecasts, "
                    "or modify optimizer mathematical constraints."
                ),
            )
        ],
        tools_used=[],
        requested_highlights=[],
        mandatory_caveats=get_mandatory_caveats(analysis),
        fallback_reason=reason,
    )


def _build_deterministic_fallback_response(
    analysis: AllocationAnalysisResult,
    scenario: ScenarioBundle,
    question: str,
    intent_code: IntentCode = IntentCode.ALLOCATION_SUMMARY,
    fallback_reason: str = "Operating in authoritative deterministic mode.",
    tools_used: list[str] | None = None,
    planned_claims: Sequence[ClaimRecord] | None = None,
    timestamp: str = "16:00",
    baseline_timestamp: str = "16:00",
    radius_meters: int = 750,
    k: int | None = None,
) -> HeatBriefResponse:
    """Construct an intent-aware deterministic brief when gateway is disabled or fails."""
    fmt_ts = format_timestamp_display(timestamp)
    fmt_base_ts = format_timestamp_display(baseline_timestamp)
    effective_k = analysis.optimized.k if k is None else k

    if planned_claims is None or len(planned_claims) == 0:
        planned_tools = plan_deterministic_evidence(
            question=question,
            intent_code=intent_code,
            suggested_calls=(),
            scenario=scenario,
            analysis=analysis,
            timestamp=fmt_ts,
            baseline_timestamp=fmt_base_ts,
        )
        claims_list: list[ClaimRecord] = []
        tools_used_list: list[str] = []
        for call in planned_tools:
            res = execute_tool(
                call=call,
                analysis=analysis,
                scenario=scenario,
                timestamp=fmt_ts,
                baseline_timestamp=fmt_base_ts,
                radius_meters=radius_meters,
                k=effective_k,
            )
            claims_list.extend(res.claims)
            arguments = [
                value
                for value in (
                    call.facility_id,
                    call.alternative_id,
                    call.target_timestamp,
                    call.baseline_type,
                )
                if value is not None
            ]
            arguments.extend((f"radius={radius_meters}m", f"k={effective_k}"))
            tools_used_list.append(f"{call.tool_name.value}({', '.join(arguments)})")
        planned_claims = tuple(claims_list)
        if tools_used is None:
            tools_used = tools_used_list

    fingerprint = compute_allocation_fingerprint(analysis)
    caveats = get_mandatory_caveats(analysis)

    brief_items = [
        BriefItem(
            claim_id=claim.claim_id,
            server_rendered_text=claim.display_text,
            facility_id=claim.facility_id,
            alternative_id=claim.alternative_id,
        )
        for claim in planned_claims
    ]

    title_map = {
        IntentCode.ALLOCATION_SUMMARY: (
            "Authoritative Allocation Brief (Deterministic Summary)"
        ),
        IntentCode.DIURNAL_HEAT_TRANSITION: (
            "Diurnal Thermal Transition Brief (Deterministic Summary)"
        ),
        IntentCode.HEAT_VULNERABILITY_EXPLANATION: (
            "Facility Thermal-Priority & Population Brief (Deterministic Summary)"
        ),
        IntentCode.REPLACEMENT_RATIONALE: (
            "Replacement & Trade-off Brief (Deterministic Summary)"
        ),
        IntentCode.BASELINE_COMPARISON: (
            "Baseline Comparison Brief (Deterministic Summary)"
        ),
    }

    highlights: list[str] = []
    for c in planned_claims:
        if c.facility_id and c.facility_id not in highlights:
            highlights.append(c.facility_id)
        if c.alternative_id and c.alternative_id not in highlights:
            highlights.append(c.alternative_id)
    if not highlights:
        highlights = list(analysis.optimized.selected_facility_ids)

    return HeatBriefResponse(
        status=CopilotStatus.DETERMINISTIC_FALLBACK,
        intent_code=intent_code,
        scenario_id=analysis.optimized.scenario_id,
        plan_fingerprint=fingerprint,
        timestamp=fmt_ts,
        radius_meters=radius_meters,
        k=effective_k,
        title=title_map.get(
            intent_code, "Authoritative Heat Intelligence Brief (Deterministic Summary)"
        ),
        brief_items=brief_items,
        tools_used=tools_used or ["get_allocation_plan"],
        requested_highlights=highlights,
        mandatory_caveats=caveats,
        fallback_reason=fallback_reason,
    )


CANONICAL_PRESET_INQUIRIES: frozenset[str] = frozenset(
    {
        "why was dc_135 selected instead of dc_148 at 20:00 utc?",
        "why was dc_135 selected instead of dc_148 at 20:00 utc",
        "why was dc_148 selected instead of dc_135 at 16:00 utc?",
        "why was dc_148 selected instead of dc_135 at 16:00 utc",
        "compare dynamic allocation against the static baseline",
        "compare dynamic allocation against the static baseline.",
        "explain diurnal heat transition",
        "explain diurnal heat transition.",
        "what changed in the prepared thermal pattern between 16:00 and 20:00 utc?",
        "what changed in the prepared thermal pattern between 16:00 and 20:00 utc",
        "show heat vulnerability profile for dc_135",
        "show heat vulnerability profile for dc_135.",
    }
)


def _try_resolve_deterministic_preset_selection(
    question: str,
    explicit_facility_ids: Sequence[str],
    current_timestamp: str,
    baseline_timestamp: str,
) -> GatewayToolSelection | None:
    """Attempt unambiguous deterministic Turn-1 resolution for recognized preset inquiries.

    Returns a valid GatewayToolSelection ONLY if the question strictly matches a supported
    canonical deterministic preset pattern.
    Returns None for all free-form, custom, or variant inquiries, preserving the full 2-turn
    LLM path.
    """
    q_clean = question.strip().lower()
    if q_clean not in CANONICAL_PRESET_INQUIRIES:
        return None

    # Timestamp-bearing presets are only canonical for the matching request
    # context. A stale UI question/request pair must take the normal Turn-1 path.
    if " at 20:00 utc" in q_clean and current_timestamp != "20:00":
        return None
    if " at 16:00 utc" in q_clean and current_timestamp != "16:00":
        return None
    if "between 16:00 and 20:00 utc" in q_clean and (
        baseline_timestamp != "16:00" or current_timestamp != "20:00"
    ):
        return None

    # 1. Preset Replacement Pair
    if (
        "selected instead of" in q_clean or "replace" in q_clean
    ) and len(explicit_facility_ids) == 2:
        incumbent = explicit_facility_ids[0]
        alternative = explicit_facility_ids[1]
        return GatewayToolSelection(
            intent_code=IntentCode.REPLACEMENT_RATIONALE,
            tool_calls=(
                ToolCall(
                    tool_name=ToolName.GET_REPLACEMENT_EVIDENCE,
                    facility_id=incumbent,
                    alternative_id=alternative,
                ),
                ToolCall(
                    tool_name=ToolName.GET_HEAT_VULNERABILITY_PROFILE,
                    facility_id=incumbent,
                ),
                ToolCall(
                    tool_name=ToolName.GET_HEAT_VULNERABILITY_PROFILE,
                    facility_id=alternative,
                ),
                ToolCall(tool_name=ToolName.GET_ALLOCATION_PLAN),
            ),
        )

    # 2. Preset Baseline Comparison
    if "static baseline" in q_clean or "compare dynamic allocation" in q_clean:
        return GatewayToolSelection(
            intent_code=IntentCode.BASELINE_COMPARISON,
            tool_calls=(
                ToolCall(
                    tool_name=ToolName.GET_BASELINE_COMPARISON,
                    baseline_type="static_allocation",
                ),
                ToolCall(tool_name=ToolName.GET_ALLOCATION_PLAN),
                ToolCall(
                    tool_name=ToolName.GET_DIURNAL_THERMAL_PROFILE,
                    target_timestamp=current_timestamp,
                ),
            ),
        )

    # 3. Preset Diurnal Heat Transition
    if (
        "diurnal heat transition" in q_clean
        or "thermal pattern between 16:00 and 20:00" in q_clean
    ):
        return GatewayToolSelection(
            intent_code=IntentCode.DIURNAL_HEAT_TRANSITION,
            tool_calls=(
                ToolCall(
                    tool_name=ToolName.GET_DIURNAL_HEAT_TRANSITION,
                    target_timestamp=current_timestamp,
                ),
                ToolCall(
                    tool_name=ToolName.GET_DIURNAL_THERMAL_PROFILE,
                    target_timestamp=current_timestamp,
                ),
                ToolCall(tool_name=ToolName.GET_ALLOCATION_PLAN),
            ),
        )

    # 4. Preset Heat Vulnerability Profile
    if "heat vulnerability profile" in q_clean and len(explicit_facility_ids) == 1:
        target_fac = explicit_facility_ids[0]
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

    return None


def generate_heat_brief(
    request: HeatBriefRequest,
    scenario_bundle: ScenarioBundle,
    analysis_result: AllocationAnalysisResult | None = None,
    gateway: ModelGateway | None = None,
) -> HeatBriefResponse:
    """Execute a bounded AI organization pass over authoritative deterministic evidence."""
    if gateway is None:
        gateway = DisabledModelGateway()

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
        analysis_result = analyze_future_state(target_req, optimize(prior_req))

    inferred_intent = infer_intent_from_question(request.question)
    explicit_facility_ids = scenario_bundle.resolve_facilities(request.question)

    def deterministic_fallback(
        reason: str,
        *,
        intent: IntentCode = inferred_intent,
        tools_used: list[str] | None = None,
        planned_claims: Sequence[ClaimRecord] | None = None,
    ) -> HeatBriefResponse:
        return _build_deterministic_fallback_response(
            analysis=analysis_result,
            scenario=scenario_bundle,
            question=request.question,
            intent_code=intent,
            fallback_reason=reason,
            tools_used=tools_used,
            planned_claims=planned_claims,
            timestamp=request.timestamp,
            baseline_timestamp=request.baseline_timestamp,
            radius_meters=request.radius_meters,
            k=request.k,
        )

    if is_unsupported_question(request.question):
        return _build_unsupported_scope_response(
            analysis=analysis_result,
            scenario=scenario_bundle,
            question=request.question,
            reason="Inquiry outside closed heat intelligence intent scope.",
            timestamp=request.timestamp,
            radius_meters=request.radius_meters,
            k=request.k,
        )

    if isinstance(gateway, DisabledModelGateway):
        return deterministic_fallback(
            "No AI model gateway configured; returning authoritative deterministic summary."
        )

    question_lower = request.question.casefold()
    has_deterministic_intent_signal = bool(explicit_facility_ids) or any(
        signal in question_lower
        for signal in (
            "allocation",
            "baseline",
            "static",
            "naive",
            "replace",
            "rejected",
            "instead of",
            "tradeoff",
            "trade-off",
            "not selected",
            "wasn't selected",
            "transition",
            "through the day",
            "fortyguard data change",
            "unmet demand",
            "constraint",
            "k=",
            "k =",
        )
    )
    expected_intent = inferred_intent if has_deterministic_intent_signal else None

    classification_context = GatewayClassificationContext(
        question=request.question,
        current_timestamp=request.timestamp,
        supported_intents=tuple(IntentCode),
        supported_tools=tuple(ToolName),
        available_facility_ids=scenario_bundle.get_facility_ids(),
        available_timestamps=tuple(scenario_bundle.get_timestamps()),
        selected_facility_ids=analysis_result.optimized.selected_facility_ids,
        radius_meters=request.radius_meters,
        k=request.k,
    )

    is_live_gateway = getattr(
        gateway, "supports_turn1_bypass", False
    ) or type(gateway).__name__ in (
        "OpenRouterModelGateway",
        "GeminiModelGateway",
    )
    deterministic_selection = (
        _try_resolve_deterministic_preset_selection(
            request.question,
            explicit_facility_ids,
            request.timestamp,
            request.baseline_timestamp,
        )
        if is_live_gateway
        else None
    )

    if deterministic_selection is not None:
        tool_selection = deterministic_selection
    else:
        try:
            raw_tool_selection = gateway.select_tools(classification_context)
        except Exception as exc:
            logger.warning("Gateway tool selection failed: category=gateway_exception")
            return deterministic_fallback(
                _extract_safe_fallback_reason(exc, FALLBACK_REASON_GATEWAY_SELECTION_FAILED)
            )

        # A model returning no supported plan is a provider/planning failure, not proof that a
        # deterministically in-scope question is unsupported.
        if raw_tool_selection is None:
            return deterministic_fallback(FALLBACK_REASON_TOOL_SELECTION_INVALID)

        tool_selection = raw_tool_selection

    # Deterministic bypass plans cross the same semantic trust boundary as
    # model-generated selections before authoritative evidence planning.
    selection_issue = validate_tool_selection_semantics(
        tool_selection,
        available_facility_ids=scenario_bundle.get_facility_ids(),
        available_timestamps=scenario_bundle.get_timestamps(),
        expected_intent=expected_intent,
        explicit_facility_ids=explicit_facility_ids,
        selected_facility_ids=analysis_result.optimized.selected_facility_ids,
    )
    if selection_issue is not None:
        logger.warning(
            "Gateway tool selection failed semantic validation: category=%s",
            selection_issue.value,
        )
        return deterministic_fallback(FALLBACK_REASON_TOOL_SELECTION_INVALID)

    intent_code = expected_intent or tool_selection.intent_code
    planned_tool_calls = plan_deterministic_evidence(
        question=request.question,
        intent_code=intent_code,
        suggested_calls=tool_selection.tool_calls,
        scenario=scenario_bundle,
        analysis=analysis_result,
        timestamp=request.timestamp,
        baseline_timestamp=request.baseline_timestamp,
        max_budget=MAX_TOOL_CALLS,
    )

    final_selection = GatewayToolSelection(
        intent_code=intent_code,
        tool_calls=planned_tool_calls,
    )
    final_issue = validate_tool_selection_semantics(
        final_selection,
        available_facility_ids=scenario_bundle.get_facility_ids(),
        available_timestamps=scenario_bundle.get_timestamps(),
        expected_intent=intent_code,
        explicit_facility_ids=explicit_facility_ids,
        selected_facility_ids=analysis_result.optimized.selected_facility_ids,
        require_mandatory_evidence=True,
    )
    if final_issue is not None:
        logger.warning(
            "Authoritative evidence plan failed semantic validation: category=%s",
            final_issue.value,
        )
        return deterministic_fallback(FALLBACK_REASON_TOOL_SELECTION_INVALID, intent=intent_code)

    active_claim_ledger: dict[str, ClaimRecord] = {}
    active_facility_ids: set[str] = set()
    tool_results: list[ToolExecutionResult] = []
    tools_used_strings: list[str] = []
    safe_analysis = copy.deepcopy(analysis_result)

    for call in planned_tool_calls:
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
            return deterministic_fallback(FALLBACK_REASON_TOOL_EXECUTION_FAILED, intent=intent_code)

        tool_results.append(result)
        arguments = [
            value
            for value in (
                call.facility_id,
                call.alternative_id,
                call.target_timestamp,
                call.baseline_type,
            )
            if value is not None
        ]
        arguments.extend((f"radius={request.radius_meters}m", f"k={request.k}"))
        tools_used_strings.append(f"{call.tool_name.value}({', '.join(arguments)})")

        for claim in result.claims:
            active_claim_ledger[claim.claim_id] = claim
            if claim.facility_id:
                active_facility_ids.add(claim.facility_id)
            if claim.alternative_id:
                active_facility_ids.add(claim.alternative_id)

    plan_context = GatewayPlanContext(
        question=request.question,
        intent_code=intent_code,
        current_timestamp=request.timestamp,
        available_claim_ids=tuple(active_claim_ledger),
        available_facility_ids=tuple(sorted(active_facility_ids)),
        radius_meters=request.radius_meters,
        k=request.k,
    )

    try:
        answer_plan = gateway.generate_answer_plan(plan_context, tool_results)
    except Exception as exc:
        logger.warning("Gateway answer plan generation failed: category=gateway_exception")
        return deterministic_fallback(
            _extract_safe_fallback_reason(exc, FALLBACK_REASON_GATEWAY_ANSWER_FAILED),
            intent=intent_code,
            tools_used=tools_used_strings,
            planned_claims=list(active_claim_ledger.values()),
        )

    if answer_plan.intent_code != intent_code or not answer_plan.sections:
        logger.warning("Answer plan validation failed: category=intent_or_sections")
        return deterministic_fallback(
            FALLBACK_REASON_ANSWER_PLAN_INVALID,
            intent=intent_code,
            tools_used=tools_used_strings,
            planned_claims=list(active_claim_ledger.values()),
        )

    cited_claim_ids: list[str] = []
    for section in answer_plan.sections:
        for claim_id in section.ordered_claim_ids:
            if claim_id not in active_claim_ledger:
                logger.warning("Answer plan grounding failed: category=unknown_claim_id")
                return deterministic_fallback(
                    FALLBACK_REASON_ANSWER_PLAN_UNGROUNDED,
                    intent=intent_code,
                    tools_used=tools_used_strings,
                    planned_claims=list(active_claim_ledger.values()),
                )
            cited_claim_ids.append(claim_id)
        if any(fid not in active_facility_ids for fid in section.cited_facility_ids):
            logger.warning("Answer plan grounding failed: category=unknown_facility_id")
            return deterministic_fallback(
                FALLBACK_REASON_ANSWER_PLAN_UNGROUNDED,
                intent=intent_code,
                tools_used=tools_used_strings,
                planned_claims=list(active_claim_ledger.values()),
            )

    if not cited_claim_ids or any(
        fid not in active_facility_ids for fid in answer_plan.requested_highlights
    ):
        logger.warning("Answer plan grounding failed: category=empty_or_invalid_highlight")
        return deterministic_fallback(
            FALLBACK_REASON_ANSWER_PLAN_INVALID,
            intent=intent_code,
            tools_used=tools_used_strings,
            planned_claims=list(active_claim_ledger.values()),
        )

    cited_claim_types = {active_claim_ledger[cid].claim_type for cid in cited_claim_ids}
    required_claim_types: dict[IntentCode, tuple[set[str], ...]] = {
        IntentCode.ALLOCATION_SUMMARY: ({"allocation_summary"},),
        IntentCode.DIURNAL_HEAT_TRANSITION: (
            {"diurnal_transition"},
            {"thermal_distribution_profile"},
        ),
        IntentCode.HEAT_VULNERABILITY_EXPLANATION: ({"heat_vulnerability_profile"},),
        IntentCode.REPLACEMENT_RATIONALE: (
            {"replacement_loss", "replacement_pair_context"},
        ),
        IntentCode.BASELINE_COMPARISON: (
            {"static_baseline_comparison", "naive_baseline_comparison"},
        ),
    }
    if any(
        not accepted.intersection(cited_claim_types)
        for accepted in required_claim_types[intent_code]
    ):
        logger.warning("Answer plan grounding failed: category=missing_intent_evidence")
        return deterministic_fallback(
            FALLBACK_REASON_ANSWER_PLAN_INVALID,
            intent=intent_code,
            tools_used=tools_used_strings,
            planned_claims=list(active_claim_ledger.values()),
        )

    brief_items: list[BriefItem] = []
    seen_claims: set[str] = set()
    for claim_id in cited_claim_ids:
        if claim_id in seen_claims:
            continue
        claim = active_claim_ledger[claim_id]
        brief_items.append(
            BriefItem(
                claim_id=claim.claim_id,
                server_rendered_text=claim.display_text,
                facility_id=claim.facility_id,
                alternative_id=claim.alternative_id,
            )
        )
        seen_claims.add(claim_id)

    title_map = {
        IntentCode.ALLOCATION_SUMMARY: "Optimal Cooling Center Allocation Brief",
        IntentCode.DIURNAL_HEAT_TRANSITION: "Diurnal Thermal & Allocation Analysis",
        IntentCode.HEAT_VULNERABILITY_EXPLANATION: (
            "Facility Thermal-Priority & Population Evidence"
        ),
        IntentCode.REPLACEMENT_RATIONALE: "Facility Replacement & Trade-off Rationale",
        IntentCode.BASELINE_COMPARISON: "Comparative Baseline Performance Analysis",
    }
    highlights = list(answer_plan.requested_highlights) or sorted(active_facility_ids)

    return HeatBriefResponse(
        status=CopilotStatus.AI_GENERATED,
        intent_code=intent_code,
        scenario_id=analysis_result.optimized.scenario_id,
        plan_fingerprint=compute_allocation_fingerprint(analysis_result),
        timestamp=format_timestamp_display(request.timestamp),
        radius_meters=request.radius_meters,
        k=request.k,
        title=title_map[intent_code],
        brief_items=brief_items,
        tools_used=tools_used_strings,
        requested_highlights=highlights,
        mandatory_caveats=get_mandatory_caveats(analysis_result),
    )
