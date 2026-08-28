from __future__ import annotations

from collections.abc import Sequence

import pytest
from starlette.testclient import TestClient

from coolaccess.agent import (
    AnswerSectionPlan,
    CopilotStatus,
    FakeModelGateway,
    GatewayAnswerPlan,
    GatewayPlanContext,
    HeatBriefRequest,
    IntentCode,
    ToolExecutionResult,
    generate_heat_brief,
)
from coolaccess.scenario import ScenarioBundle, load_locked_scenario
from coolaccess.server import app


class OutOfScopeHighlightGateway(FakeModelGateway):
    """Adversarial gateway attempting to highlight an out-of-scope facility."""

    def generate_answer_plan(
        self,
        context: GatewayPlanContext,
        tool_results: Sequence[ToolExecutionResult],
        deadline: float | None = None,
    ) -> GatewayAnswerPlan:
        return GatewayAnswerPlan(
            intent_code=context.intent_code,
            headline_code="HEADLINE_TRADE_OFF",
            sections=(
                AnswerSectionPlan(
                    section_type="summary",
                    ordered_claim_ids=context.available_claim_ids[:2],
                    cited_facility_ids=context.available_facility_ids[:2],
                ),
            ),
            # Attempt to highlight DC_168 which is NOT part of the DC_135 vs DC_148 request scope
            requested_highlights=("DC_168",),
        )


@pytest.fixture
def scenario_bundle() -> ScenarioBundle:
    return load_locked_scenario()


def test_quick_inquiry_diurnal_thermal_shift(scenario_bundle: ScenarioBundle) -> None:
    gateway = FakeModelGateway()
    req = HeatBriefRequest(
        question="What changed in the prepared thermal pattern between 16:00 and 20:00 UTC?",
        timestamp="16:00",
        baseline_timestamp="16:00",
        radius_meters=750,
        k=3,
    )
    resp = generate_heat_brief(req, scenario_bundle, gateway=gateway)
    assert resp.status == CopilotStatus.AI_GENERATED
    assert resp.intent_code == IntentCode.DIURNAL_HEAT_TRANSITION
    assert len(resp.brief_items) > 0
    assert len(resp.tools_used) > 0
    for item in resp.brief_items:
        assert item.server_rendered_text is not None
        assert len(item.server_rendered_text) > 10


def test_quick_inquiry_unmet_demand(scenario_bundle: ScenarioBundle) -> None:
    gateway = FakeModelGateway()
    req = HeatBriefRequest(
        question="Where does heat-weighted demand remain unmet?",
        timestamp="16:00",
        baseline_timestamp="16:00",
        radius_meters=750,
        k=3,
    )
    resp = generate_heat_brief(req, scenario_bundle, gateway=gateway)
    assert resp.status == CopilotStatus.AI_GENERATED
    assert resp.intent_code == IntentCode.ALLOCATION_SUMMARY
    assert len(resp.brief_items) > 0
    for item in resp.brief_items:
        assert item.server_rendered_text is not None


def test_quick_inquiry_tradeoff_1600(scenario_bundle: ScenarioBundle) -> None:
    gateway = FakeModelGateway()
    req = HeatBriefRequest(
        question="Why was DC_148 selected instead of DC_135 at 16:00 UTC?",
        timestamp="16:00",
        baseline_timestamp="16:00",
        radius_meters=750,
        k=3,
    )
    resp = generate_heat_brief(req, scenario_bundle, gateway=gateway)
    assert resp.status == CopilotStatus.AI_GENERATED
    assert resp.intent_code == IntentCode.REPLACEMENT_RATIONALE
    assert "DC_148" in resp.requested_highlights
    assert "DC_135" in resp.requested_highlights
    assert len(resp.brief_items) > 0


def test_quick_inquiry_tradeoff_2000(scenario_bundle: ScenarioBundle) -> None:
    gateway = FakeModelGateway()
    req = HeatBriefRequest(
        question="Why was DC_135 selected instead of DC_148 at 20:00 UTC?",
        timestamp="20:00",
        baseline_timestamp="16:00",
        radius_meters=750,
        k=3,
    )
    resp = generate_heat_brief(req, scenario_bundle, gateway=gateway)
    assert resp.status == CopilotStatus.AI_GENERATED
    assert resp.intent_code == IntentCode.REPLACEMENT_RATIONALE
    assert "DC_135" in resp.requested_highlights
    assert "DC_148" in resp.requested_highlights
    assert len(resp.brief_items) > 0


def test_quick_inquiry_evidence_heat_brief(scenario_bundle: ScenarioBundle) -> None:
    gateway = FakeModelGateway()
    req = HeatBriefRequest(
        question="Summarize the thermal-priority and population evidence for this allocation.",
        timestamp="16:00",
        baseline_timestamp="16:00",
        radius_meters=750,
        k=3,
    )
    resp = generate_heat_brief(req, scenario_bundle, gateway=gateway)
    assert resp.status == CopilotStatus.AI_GENERATED
    assert resp.intent_code == IntentCode.ALLOCATION_SUMMARY
    assert len(resp.brief_items) > 0


def test_tradeoff_rejects_out_of_scope_highlight_facility(scenario_bundle: ScenarioBundle) -> None:
    """Assert that requesting DC_168 for a DC_135 vs DC_148 query fails closed."""
    adversarial_gateway = OutOfScopeHighlightGateway()
    req = HeatBriefRequest(
        question="Why was DC_135 selected instead of DC_148 at 20:00 UTC?",
        timestamp="20:00",
        baseline_timestamp="16:00",
        radius_meters=750,
        k=3,
    )
    resp = generate_heat_brief(req, scenario_bundle, gateway=adversarial_gateway)
    # Must fail closed to DETERMINISTIC_FALLBACK because DC_168 is out of request scope
    assert resp.status == CopilotStatus.DETERMINISTIC_FALLBACK
    assert resp.fallback_reason is not None


def test_api_endpoint_heat_brief_contract() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/heat-intelligence/brief",
        json={
            "question": "What changed in the prepared thermal pattern between 16:00 and 20:00 UTC?",
            "timestamp": "16:00",
            "baseline_timestamp": "16:00",
            "radius_meters": 750,
            "k": 3,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "intent_code" in data
    assert "brief_items" in data
    assert "tools_used" in data
    assert "requested_highlights" in data
    assert len(data["brief_items"]) > 0
