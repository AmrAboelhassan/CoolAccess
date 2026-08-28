from collections.abc import Sequence

import pytest

import coolaccess.agent as agent_module
from coolaccess.agent import (
    FALLBACK_REASON_ANSWER_PLAN_INVALID,
    FALLBACK_REASON_ANSWER_PLAN_UNGROUNDED,
    FALLBACK_REASON_TOOL_SELECTION_INVALID,
    AnswerSectionPlan,
    CopilotStatus,
    GatewayAnswerPlan,
    GatewayClassificationContext,
    GatewayPlanContext,
    GatewayToolSelection,
    HeatBriefRequest,
    IntentCode,
    ToolCall,
    ToolExecutionResult,
    ToolName,
    generate_heat_brief,
)
from coolaccess.scenario import ScenarioBundle


class CountingLiveGateway:
    """Mock simulating a live gateway to count exact select_tools vs generate_answer_plan calls."""

    def __init__(self) -> None:
        self.supports_turn1_bypass = True
        self.select_tools_calls = 0
        self.generate_plan_calls = 0

    def select_tools(
        self,
        context: GatewayClassificationContext,
    ) -> GatewayToolSelection | None:
        self.select_tools_calls += 1
        return GatewayToolSelection(
            intent_code=IntentCode.ALLOCATION_SUMMARY,
            tool_calls=(
                ToolCall(tool_name=ToolName.GET_ALLOCATION_PLAN),
            ),
        )

    def generate_answer_plan(
        self,
        context: GatewayPlanContext,
        tool_results: Sequence[ToolExecutionResult],
    ) -> GatewayAnswerPlan:
        self.generate_plan_calls += 1
        return GatewayAnswerPlan(
            intent_code=context.intent_code,
            headline_code=f"HEADLINE_{context.intent_code.value}",
            sections=(
                AnswerSectionPlan(
                    section_type="summary",
                    ordered_claim_ids=context.available_claim_ids,
                    cited_facility_ids=(),
                ),
            ),
            requested_highlights=(),
        )


class HallucinatedPlanGateway(CountingLiveGateway):
    def generate_answer_plan(
        self,
        context: GatewayPlanContext,
        tool_results: Sequence[ToolExecutionResult],
    ) -> GatewayAnswerPlan:
        self.generate_plan_calls += 1
        return GatewayAnswerPlan(
            intent_code=context.intent_code,
            headline_code=f"HEADLINE_{context.intent_code.value}",
            sections=(
                AnswerSectionPlan(
                    section_type="summary",
                    ordered_claim_ids=("claim:hallucinated:bypass",),
                    cited_facility_ids=("DC_135",),
                ),
            ),
            requested_highlights=("DC_135",),
        )


class UnknownHighlightGateway(CountingLiveGateway):
    def generate_answer_plan(
        self,
        context: GatewayPlanContext,
        tool_results: Sequence[ToolExecutionResult],
    ) -> GatewayAnswerPlan:
        self.generate_plan_calls += 1
        return GatewayAnswerPlan(
            intent_code=context.intent_code,
            headline_code=f"HEADLINE_{context.intent_code.value}",
            sections=(
                AnswerSectionPlan(
                    section_type="summary",
                    ordered_claim_ids=context.available_claim_ids,
                    cited_facility_ids=(),
                ),
            ),
            requested_highlights=("DC_999",),
        )


def test_preset_query_bypasses_turn_1() -> None:
    scenario = ScenarioBundle()
    gateway = CountingLiveGateway()
    request = HeatBriefRequest(
        question="Why was DC_135 selected instead of DC_148 at 20:00 UTC?",
        timestamp="20:00",
        baseline_timestamp="16:00",
        radius_meters=750,
        k=3,
    )
    resp = generate_heat_brief(request, scenario, gateway=gateway)

    assert resp.status == CopilotStatus.AI_GENERATED
    assert resp.intent_code == IntentCode.REPLACEMENT_RATIONALE
    # Turn 1 must be bypassed: 0 select_tools calls
    assert gateway.select_tools_calls == 0
    # Turn 2 must be executed: exactly 1 generate_answer_plan call
    assert gateway.generate_plan_calls == 1


def test_baseline_preset_query_bypasses_turn_1() -> None:
    scenario = ScenarioBundle()
    gateway = CountingLiveGateway()
    request = HeatBriefRequest(
        question="Compare dynamic allocation against the static baseline",
        timestamp="20:00",
        baseline_timestamp="16:00",
        radius_meters=750,
        k=3,
    )
    resp = generate_heat_brief(request, scenario, gateway=gateway)

    assert resp.status == CopilotStatus.AI_GENERATED
    assert resp.intent_code == IntentCode.BASELINE_COMPARISON
    assert gateway.select_tools_calls == 0
    assert gateway.generate_plan_calls == 1


def test_freeform_ambiguous_query_executes_turn_1() -> None:
    scenario = ScenarioBundle()
    gateway = CountingLiveGateway()
    # Ambiguous / novel free-form query
    request = HeatBriefRequest(
        question="How does temperature distribution change municipal cooling efficiency?",
        timestamp="20:00",
        baseline_timestamp="16:00",
        radius_meters=750,
        k=3,
    )
    resp = generate_heat_brief(request, scenario, gateway=gateway)

    assert resp.status == CopilotStatus.AI_GENERATED
    # Ambiguous query must NOT bypass Turn 1: exactly 1 select_tools call
    assert gateway.select_tools_calls == 1
    # Followed by exactly 1 generate_answer_plan call (total 2 calls)
    assert gateway.generate_plan_calls == 1


@pytest.mark.parametrize(
    ("timestamp", "question", "selected_id", "alternative_id"),
    (
        (
            "16:00",
            "Why was DC_148 selected instead of DC_135 at 16:00 UTC?",
            "DC_148",
            "DC_135",
        ),
        (
            "20:00",
            "Why was DC_135 selected instead of DC_148 at 20:00 UTC?",
            "DC_135",
            "DC_148",
        ),
    ),
)
def test_dynamic_replacement_presets_preserve_authoritative_direction(
    timestamp: str,
    question: str,
    selected_id: str,
    alternative_id: str,
) -> None:
    gateway = CountingLiveGateway()
    response = generate_heat_brief(
        HeatBriefRequest(
            question=question,
            timestamp=timestamp,
            baseline_timestamp="16:00",
        ),
        ScenarioBundle(),
        gateway=gateway,
    )

    assert response.status == CopilotStatus.AI_GENERATED
    assert gateway.select_tools_calls == 0
    assert gateway.generate_plan_calls == 1
    assert any(
        f"get_replacement_evidence({selected_id}, {alternative_id}," in tool
        for tool in response.tools_used
    )


def test_no_time_diurnal_preset_uses_current_request_timestamp() -> None:
    gateway = CountingLiveGateway()
    response = generate_heat_brief(
        HeatBriefRequest(
            question="Explain diurnal heat transition",
            timestamp="20:00",
            baseline_timestamp="16:00",
        ),
        ScenarioBundle(),
        gateway=gateway,
    )

    assert response.status == CopilotStatus.AI_GENERATED
    assert gateway.select_tools_calls == 0
    assert any(
        "get_diurnal_heat_transition(20:00," in tool for tool in response.tools_used
    )
    assert any(
        "get_diurnal_thermal_profile(20:00," in tool for tool in response.tools_used
    )
    assert all("(14:00," not in tool for tool in response.tools_used)


def test_authoritative_sixteen_to_twenty_diurnal_preset_uses_twenty() -> None:
    gateway = CountingLiveGateway()
    response = generate_heat_brief(
        HeatBriefRequest(
            question=(
                "What changed in the prepared thermal pattern between 16:00 and 20:00 UTC?"
            ),
            timestamp="20:00",
            baseline_timestamp="16:00",
        ),
        ScenarioBundle(),
        gateway=gateway,
    )

    assert response.status == CopilotStatus.AI_GENERATED
    assert gateway.select_tools_calls == 0
    assert any(
        "get_diurnal_heat_transition(20:00," in tool for tool in response.tools_used
    )
    assert any(
        "get_diurnal_thermal_profile(20:00," in tool for tool in response.tools_used
    )


def test_timestamp_mismatched_preset_retains_turn_1() -> None:
    gateway = CountingLiveGateway()
    generate_heat_brief(
        HeatBriefRequest(
            question="Why was DC_135 selected instead of DC_148 at 20:00 UTC?",
            timestamp="16:00",
            baseline_timestamp="16:00",
        ),
        ScenarioBundle(),
        gateway=gateway,
    )

    assert gateway.select_tools_calls == 1
    assert gateway.generate_plan_calls == 0


def test_case_and_outer_whitespace_preserve_exact_preset_bypass() -> None:
    gateway = CountingLiveGateway()
    response = generate_heat_brief(
        HeatBriefRequest(
            question="  COMPARE DYNAMIC ALLOCATION AGAINST THE STATIC BASELINE\r\n",
            timestamp="20:00",
            baseline_timestamp="16:00",
        ),
        ScenarioBundle(),
        gateway=gateway,
    )

    assert response.status == CopilotStatus.AI_GENERATED
    assert gateway.select_tools_calls == 0
    assert gateway.generate_plan_calls == 1


@pytest.mark.parametrize(
    "question",
    (
        "Compare dynamic allocation against the static baseline!",
        "Compare  dynamic allocation against the static baseline",
        "Compare dynamic allocation against the static baseline today",
        "How does cooling allocation shift between 14:00 and 20:00?",
    ),
)
def test_near_match_queries_retain_turn_1(question: str) -> None:
    gateway = CountingLiveGateway()
    generate_heat_brief(
        HeatBriefRequest(
            question=question,
            timestamp="20:00",
            baseline_timestamp="16:00",
        ),
        ScenarioBundle(),
        gateway=gateway,
    )

    assert gateway.select_tools_calls == 1


def test_bypassed_selection_still_fails_closed_on_wrong_explicit_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def wrong_selection(
        _question: str,
        _explicit_facility_ids: Sequence[str],
        _current_timestamp: str,
        _baseline_timestamp: str,
    ) -> GatewayToolSelection:
        return GatewayToolSelection(
            intent_code=IntentCode.REPLACEMENT_RATIONALE,
            tool_calls=(
                ToolCall(
                    tool_name=ToolName.GET_REPLACEMENT_EVIDENCE,
                    facility_id="DC_089",
                    alternative_id="DC_148",
                ),
            ),
        )

    monkeypatch.setattr(
        agent_module,
        "_try_resolve_deterministic_preset_selection",
        wrong_selection,
    )
    gateway = CountingLiveGateway()
    response = generate_heat_brief(
        HeatBriefRequest(
            question="Why was DC_135 selected instead of DC_148 at 20:00 UTC?",
            timestamp="20:00",
            baseline_timestamp="16:00",
        ),
        ScenarioBundle(),
        gateway=gateway,
    )

    assert response.status == CopilotStatus.DETERMINISTIC_FALLBACK
    assert response.fallback_reason == FALLBACK_REASON_TOOL_SELECTION_INVALID
    assert gateway.select_tools_calls == 0
    assert gateway.generate_plan_calls == 0


def test_grounding_validation_runs_after_bypass() -> None:
    gateway = HallucinatedPlanGateway()
    response = generate_heat_brief(
        HeatBriefRequest(
            question="Why was DC_135 selected instead of DC_148 at 20:00 UTC?",
            timestamp="20:00",
            baseline_timestamp="16:00",
        ),
        ScenarioBundle(),
        gateway=gateway,
    )

    assert response.status == CopilotStatus.DETERMINISTIC_FALLBACK
    assert response.fallback_reason == FALLBACK_REASON_ANSWER_PLAN_UNGROUNDED
    assert gateway.select_tools_calls == 0
    assert gateway.generate_plan_calls == 1


def test_unknown_requested_highlight_fails_closed_after_bypass() -> None:
    gateway = UnknownHighlightGateway()
    response = generate_heat_brief(
        HeatBriefRequest(
            question="Compare dynamic allocation against the static baseline",
            timestamp="20:00",
            baseline_timestamp="16:00",
        ),
        ScenarioBundle(),
        gateway=gateway,
    )

    assert response.status == CopilotStatus.DETERMINISTIC_FALLBACK
    assert response.fallback_reason == FALLBACK_REASON_ANSWER_PLAN_INVALID
    assert gateway.select_tools_calls == 0
    assert gateway.generate_plan_calls == 1
