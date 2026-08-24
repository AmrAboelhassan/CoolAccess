"""Unit and regression tests for CoolAccess agent, claim ledger, and tools."""

from __future__ import annotations

from coolaccess.agent import (
    FALLBACK_REASON_ANSWER_PLAN_UNGROUNDED,
    FALLBACK_REASON_TOOL_SELECTION_INVALID,
    CopilotStatus,
    DisabledModelGateway,
    FakeModelGateway,
    HeatBriefRequest,
    IntentCode,
    ToolCall,
    ToolName,
    execute_tool,
    generate_heat_brief,
)
from coolaccess.analysis import analyze_future_state
from coolaccess.optimizer import optimize
from coolaccess.scenario import load_locked_scenario


def test_execute_all_tools_directly() -> None:
    bundle = load_locked_scenario()
    target_req = bundle.build_allocation_request(timestamp="20:00", k=3)
    prior_req = bundle.build_allocation_request(timestamp="16:00", k=3)
    prior_res = optimize(prior_req)
    analysis = analyze_future_state(target_req, prior_res)

    # 1. get_allocation_plan
    call1 = ToolCall(tool_name=ToolName.GET_ALLOCATION_PLAN)
    res1 = execute_tool(call1, analysis, bundle, "20:00", "16:00", 750, 3)
    assert len(res1.claims) >= 3
    claim_types = [c.claim_type for c in res1.claims]
    assert "allocation_summary" in claim_types
    assert "facility_coverage" in claim_types
    assert "tie_break_audit" in claim_types

    # 2. get_diurnal_heat_transition
    call2 = ToolCall(
        tool_name=ToolName.GET_DIURNAL_HEAT_TRANSITION,
        target_timestamp="20:00",
    )
    res2 = execute_tool(call2, analysis, bundle, "20:00", "16:00", 750, 3)
    assert len(res2.claims) >= 2
    assert any("transition" in c.claim_id for c in res2.claims)

    # 3. get_heat_vulnerability_profile
    call3 = ToolCall(
        tool_name=ToolName.GET_HEAT_VULNERABILITY_PROFILE,
        facility_id="DC_135",
    )
    res3 = execute_tool(call3, analysis, bundle, "20:00", "16:00", 750, 3)
    assert len(res3.claims) >= 2
    assert any("profile" in c.claim_id for c in res3.claims)

    # 4. get_replacement_evidence
    call4 = ToolCall(
        tool_name=ToolName.GET_REPLACEMENT_EVIDENCE,
        facility_id="DC_135",
        alternative_id="DC_148",
    )
    res4 = execute_tool(call4, analysis, bundle, "20:00", "16:00", 750, 3)
    assert len(res4.claims) >= 2
    assert any("loss" in c.claim_id for c in res4.claims)

    # 5. get_baseline_comparison
    call5 = ToolCall(
        tool_name=ToolName.GET_BASELINE_COMPARISON,
        baseline_type="all",
    )
    res5 = execute_tool(call5, analysis, bundle, "20:00", "16:00", 750, 3)
    assert len(res5.claims) == 2
    assert any("static" in c.claim_id for c in res5.claims)
    assert any("naive" in c.claim_id for c in res5.claims)


def test_disabled_gateway_returns_deterministic_fallback() -> None:
    bundle = load_locked_scenario()
    req = HeatBriefRequest(question="Why did allocation shift at 20:00 UTC?", timestamp="20:00")
    resp = generate_heat_brief(req, bundle, gateway=DisabledModelGateway())
    assert resp.status == CopilotStatus.DETERMINISTIC_FALLBACK
    assert resp.intent_code == IntentCode.ALLOCATION_SUMMARY
    assert len(resp.brief_items) > 0
    assert len(resp.mandatory_caveats) >= 3
    assert resp.plan_fingerprint != ""


def test_fake_gateway_all_intents_success() -> None:
    bundle = load_locked_scenario()
    gateway = FakeModelGateway()

    inquiries = [
        ("Summarize the optimal cooling center allocation", IntentCode.ALLOCATION_SUMMARY),
        (
            "Why does allocation shift between 16:00 and 20:00 UTC?",
            IntentCode.DIURNAL_HEAT_TRANSITION,
        ),
        (
            "Analyze DC_135 heat vulnerability from a thermal perspective",
            IntentCode.HEAT_VULNERABILITY_EXPLANATION,
        ),
        ("Why was DC_148 rejected over DC_135?", IntentCode.REPLACEMENT_RATIONALE),
        ("Compare dynamic allocation against static baseline", IntentCode.BASELINE_COMPARISON),
    ]

    for question, expected_intent in inquiries:
        req = HeatBriefRequest(question=question, timestamp="20:00")
        resp = generate_heat_brief(req, bundle, gateway=gateway)
        assert resp.status == CopilotStatus.AI_GENERATED
        assert resp.intent_code == expected_intent
        assert len(resp.brief_items) > 0
        assert len(resp.tools_used) > 0
        assert len(resp.mandatory_caveats) >= 3


def test_semantic_validation_excess_tools() -> None:
    gateway = FakeModelGateway(simulate_failure="excess_tools")
    bundle = load_locked_scenario()
    req = HeatBriefRequest(question="Summarize allocation", timestamp="20:00")
    resp = generate_heat_brief(req, bundle, gateway=gateway)
    assert resp.status == CopilotStatus.DETERMINISTIC_FALLBACK
    assert resp.fallback_reason == FALLBACK_REASON_TOOL_SELECTION_INVALID


def test_grounding_validation_unknown_claim_id() -> None:
    gateway = FakeModelGateway(simulate_failure="unknown_claim_id")
    bundle = load_locked_scenario()
    req = HeatBriefRequest(question="Why did DC_148 get rejected for DC_135?", timestamp="20:00")
    resp = generate_heat_brief(req, bundle, gateway=gateway)
    assert resp.status == CopilotStatus.DETERMINISTIC_FALLBACK
    assert resp.fallback_reason == FALLBACK_REASON_ANSWER_PLAN_UNGROUNDED


def test_grounding_validation_unknown_facility_id() -> None:
    gateway = FakeModelGateway(simulate_failure="unknown_facility_id")
    bundle = load_locked_scenario()
    req = HeatBriefRequest(question="Why did DC_148 get rejected for DC_135?", timestamp="20:00")
    resp = generate_heat_brief(req, bundle, gateway=gateway)
    assert resp.status == CopilotStatus.DETERMINISTIC_FALLBACK
    assert resp.fallback_reason == FALLBACK_REASON_ANSWER_PLAN_UNGROUNDED


def test_unsupported_question_fallback() -> None:
    gateway = FakeModelGateway()
    bundle = load_locked_scenario()
    req = HeatBriefRequest(
        question="What are the symptoms and treatment of heat stroke?", timestamp="20:00"
    )
    resp = generate_heat_brief(req, bundle, gateway=gateway)
    assert resp.status == CopilotStatus.DETERMINISTIC_FALLBACK
    assert "Inquiry outside closed heat intelligence intent scope" in (resp.fallback_reason or "")
