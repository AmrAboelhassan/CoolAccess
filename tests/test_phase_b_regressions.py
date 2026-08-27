"""Focused regressions for the Phase B correctness and trust-boundary fixes."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from coolaccess.agent import (
    FALLBACK_REASON_TOOL_SELECTION_INVALID,
    CopilotStatus,
    DisabledModelGateway,
    FakeModelGateway,
    GatewayClassificationContext,
    GatewayToolSelection,
    HeatBriefRequest,
    IntentCode,
    ToolCall,
    ToolName,
    execute_tool,
    generate_heat_brief,
    is_unsupported_question,
    plan_deterministic_evidence,
)
from coolaccess.analysis import analyze_future_state
from coolaccess.contracts import AllocationAnalysisResult
from coolaccess.model_gateway import get_runtime_model_gateway, load_ai_config
from coolaccess.optimizer import optimize
from coolaccess.scenario import ScenarioBundle, load_locked_scenario
from coolaccess.server import app

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _analysis(
    bundle: ScenarioBundle,
    timestamp: str,
    *,
    baseline_timestamp: str = "16:00",
    radius_meters: int = 750,
) -> AllocationAnalysisResult:
    target = bundle.build_allocation_request(
        timestamp=timestamp,
        radius_meters=radius_meters,
        k=3,
    )
    baseline = bundle.build_allocation_request(
        timestamp=baseline_timestamp,
        radius_meters=radius_meters,
        k=3,
    )
    return analyze_future_state(target, optimize(baseline))


class WrongPairGateway(FakeModelGateway):
    """Adversarial model that ignores the two explicit facilities in the question."""

    def select_tools(
        self,
        context: GatewayClassificationContext,
    ) -> GatewayToolSelection:
        self.select_tools_called += 1
        return GatewayToolSelection(
            intent_code=IntentCode.REPLACEMENT_RATIONALE,
            tool_calls=(
                ToolCall(
                    tool_name=ToolName.GET_REPLACEMENT_EVIDENCE,
                    facility_id="DC_089",
                    alternative_id="DC_159",
                ),
            ),
        )


class InvalidSemanticGateway(FakeModelGateway):
    """Model plan is schema-valid but semantically invalid for its tool."""

    def select_tools(
        self,
        context: GatewayClassificationContext,
    ) -> GatewayToolSelection:
        self.select_tools_called += 1
        return GatewayToolSelection(
            intent_code=IntentCode.ALLOCATION_SUMMARY,
            tool_calls=(
                ToolCall(
                    tool_name=ToolName.GET_ALLOCATION_PLAN,
                    facility_id="DC_089",
                ),
            ),
        )


def test_resolves_two_explicit_facilities_by_ids_names_and_aliases() -> None:
    bundle = load_locked_scenario()
    assert bundle.resolve_facilities("Why DC_135 instead of DC_148?") == (
        "DC_135",
        "DC_148",
    )
    assert bundle.resolve_facilities("Compare Shaw and Northeast.") == (
        "DC_089",
        "DC_148",
    )
    assert bundle.resolve_facilities("Compare MLK Library with Randall.") == (
        "DC_135",
        "DC_166",
    )


def test_explicit_pair_fails_closed_when_model_suggests_wrong_pair() -> None:
    bundle = load_locked_scenario()
    gateway = WrongPairGateway()
    response = generate_heat_brief(
        HeatBriefRequest(
            question="Why DC_135 instead of DC_148?",
            timestamp="20:00",
        ),
        bundle,
        gateway=gateway,
    )
    assert response.status == CopilotStatus.DETERMINISTIC_FALLBACK
    assert response.fallback_reason == FALLBACK_REASON_TOOL_SELECTION_INVALID
    assert any(
        item.facility_id == "DC_135" and item.alternative_id == "DC_148"
        for item in response.brief_items
    )
    assert gateway.generate_plan_called == 0


def test_pairwise_alias_question_retrieves_both_facility_profiles() -> None:
    response = generate_heat_brief(
        HeatBriefRequest(question="Compare Shaw and Northeast.", timestamp="16:00"),
        load_locked_scenario(),
        gateway=FakeModelGateway(),
    )
    assert response.status == CopilotStatus.AI_GENERATED
    cited_facilities = {
        item.facility_id for item in response.brief_items if item.facility_id is not None
    }
    assert {"DC_089", "DC_148"}.issubset(cited_facilities)


@pytest.mark.parametrize(
    ("timestamp", "question", "expected_selected", "expected_alternative"),
    [
        ("16:00", "Why DC_135 instead of DC_148?", "DC_148", "DC_135"),
        ("20:00", "Why DC_148 instead of DC_135?", "DC_135", "DC_148"),
    ],
)
def test_replacement_direction_comes_from_authoritative_selected_set(
    timestamp: str,
    question: str,
    expected_selected: str,
    expected_alternative: str,
) -> None:
    bundle = load_locked_scenario()
    analysis = _analysis(bundle, timestamp)
    plan = plan_deterministic_evidence(
        question=question,
        intent_code=IntentCode.REPLACEMENT_RATIONALE,
        suggested_calls=(),
        scenario=bundle,
        analysis=analysis,
        timestamp=timestamp,
        baseline_timestamp="16:00",
    )
    replacement = next(
        call for call in plan if call.tool_name == ToolName.GET_REPLACEMENT_EVIDENCE
    )
    assert replacement.facility_id == expected_selected
    assert replacement.alternative_id == expected_alternative


def test_k_equals_three_analytical_question_is_supported() -> None:
    bundle = load_locked_scenario()
    question = "What does the K=3 constraint change?"
    assert not is_unsupported_question(question)
    response = generate_heat_brief(
        HeatBriefRequest(question=question),
        bundle,
        gateway=FakeModelGateway(),
    )
    assert response.status == CopilotStatus.AI_GENERATED
    assert response.intent_code == IntentCode.ALLOCATION_SUMMARY


def test_two_timestamp_question_uses_the_later_mentioned_target() -> None:
    bundle = load_locked_scenario()
    plan = plan_deterministic_evidence(
        question="What changed between 16:00 and 20:00 UTC?",
        intent_code=IntentCode.DIURNAL_HEAT_TRANSITION,
        suggested_calls=(),
        scenario=bundle,
        analysis=_analysis(bundle, "20:00"),
        timestamp="20:00",
        baseline_timestamp="16:00",
    )
    transition = next(
        call for call in plan if call.tool_name == ToolName.GET_DIURNAL_HEAT_TRANSITION
    )
    assert transition.target_timestamp == "20:00"


@pytest.mark.parametrize(
    "question",
    [
        "Change K to 5 and deploy that allocation.",
        "Activate DC_148 now.",
        "Override the optimizer.",
        "What will tomorrow's temperature be?",
        "Is this medically safe?",
        "Will residents be protected from heat stroke?",
        "Does this guarantee public safety?",
    ],
)
def test_mutation_forecast_and_safety_requests_are_unsupported(question: str) -> None:
    response = generate_heat_brief(
        HeatBriefRequest(question=question),
        load_locked_scenario(),
        gateway=FakeModelGateway(),
    )
    assert response.status == CopilotStatus.UNSUPPORTED


@pytest.mark.parametrize(
    "question",
    [
        "Why wasn't MLK selected?",
        "What tradeoff caused DC_148 to be replaced?",
        "Where does unmet demand remain?",
        "What did FortyGuard data change?",
    ],
)
def test_supported_analytical_questions_are_not_overblocked(question: str) -> None:
    assert not is_unsupported_question(question)


def test_invalid_api_bounds_and_timestamp_are_intentional_errors() -> None:
    client = TestClient(app)
    invalid_k = client.get("/api/replacement?k=6")
    invalid_timestamp = client.get("/api/geojson?layer=thermal&timestamp=19:00")
    invalid_radius = client.get("/api/allocate?radius_meters=99")
    assert invalid_k.status_code == 422
    assert invalid_timestamp.status_code == 400
    assert invalid_radius.status_code == 422
    assert "Unsupported GeoJSON" in invalid_timestamp.json()["detail"]


def test_non_default_radius_propagates_through_api_and_evidence() -> None:
    client = TestClient(app)
    allocation = client.get("/api/allocate?timestamp=20:00&radius_meters=500").json()
    assert allocation["radius_meters"] == 500

    response = generate_heat_brief(
        HeatBriefRequest(
            question="Why wasn't Northeast selected?",
            timestamp="20:00",
            radius_meters=500,
        ),
        load_locked_scenario(),
        gateway=DisabledModelGateway(),
    )
    assert response.radius_meters == 500
    assert any("500 m" in item.server_rendered_text for item in response.brief_items)
    assert all("radius=500m" in tool for tool in response.tools_used)


def test_zero_gain_naive_baseline_uses_tie_language() -> None:
    bundle = load_locked_scenario()
    analysis = _analysis(bundle, "20:00")
    result = execute_tool(
        ToolCall(tool_name=ToolName.GET_BASELINE_COMPARISON, baseline_type="naive"),
        analysis,
        bundle,
        "20:00",
        "16:00",
        750,
        3,
    )
    text = " ".join(claim.display_text for claim in result.claims).casefold()
    assert "matches" in text
    assert "no gain" in text
    assert "outperform" not in text


def test_diurnal_claims_distinguish_unchanged_and_changed_sets() -> None:
    bundle = load_locked_scenario()
    unchanged = execute_tool(
        ToolCall(
            tool_name=ToolName.GET_DIURNAL_HEAT_TRANSITION,
            target_timestamp="18:00",
        ),
        _analysis(bundle, "18:00"),
        bundle,
        "18:00",
        "16:00",
        750,
        3,
    )
    changed = execute_tool(
        ToolCall(
            tool_name=ToolName.GET_DIURNAL_HEAT_TRANSITION,
            target_timestamp="20:00",
        ),
        _analysis(bundle, "20:00"),
        bundle,
        "20:00",
        "16:00",
        750,
        3,
    )
    unchanged_text = " ".join(claim.display_text for claim in unchanged.claims)
    changed_text = " ".join(claim.display_text for claim in changed.claims)
    assert "remained unchanged" in unchanged_text
    assert "Temperature change alone does not imply an allocation change" in unchanged_text
    assert "added" in changed_text and "DC_135" in changed_text
    assert "removed" in changed_text and "DC_148" in changed_text


@pytest.mark.parametrize(
    ("from_timestamp", "to_timestamp", "expected_changed"),
    [
        ("14:00", "16:00", False),
        ("16:00", "18:00", False),
        ("18:00", "20:00", True),
        ("20:00", "22:00", False),
    ],
)
def test_every_adjacent_interval_reports_actual_allocation_change(
    from_timestamp: str,
    to_timestamp: str,
    expected_changed: bool,
) -> None:
    bundle = load_locked_scenario()
    result = execute_tool(
        ToolCall(
            tool_name=ToolName.GET_DIURNAL_HEAT_TRANSITION,
            target_timestamp=to_timestamp,
        ),
        _analysis(bundle, to_timestamp, baseline_timestamp=from_timestamp),
        bundle,
        to_timestamp,
        from_timestamp,
        750,
        3,
    )
    transition_claim = next(
        claim for claim in result.claims if claim.claim_type == "diurnal_transition"
    )
    assert transition_claim.value["allocation_changed"] is expected_changed


def test_authoritative_twenty_hundred_values_remain_unchanged() -> None:
    data = TestClient(app).get(
        "/api/allocate?timestamp=20:00&baseline_timestamp=16:00"
    ).json()
    assert data["selected_facility_ids"] == ["DC_089", "DC_135", "DC_166"]
    assert data["coverage_metrics"]["covered_heat_weighted_demand"] == 8328.93
    assert data["static_baseline"]["objective_value"] == 6734.48
    assert data["static_baseline"]["absolute_gain"] == 1594.45
    assert data["static_baseline"]["percentage_gain"] == 23.68
    assert data["coverage_metrics"]["covered_population"] == 38357
    assert data["static_baseline"]["covered_population"] == 41876
    assert data["naive_baseline"]["absolute_gain"] == 0.0


def test_semantic_validation_is_invoked_before_answer_planning() -> None:
    gateway = InvalidSemanticGateway()
    response = generate_heat_brief(
        HeatBriefRequest(question="Summarize the current allocation."),
        load_locked_scenario(),
        gateway=gateway,
    )
    assert response.status == CopilotStatus.DETERMINISTIC_FALLBACK
    assert response.fallback_reason == FALLBACK_REASON_TOOL_SELECTION_INVALID
    assert gateway.generate_plan_called == 0


def test_unpackaged_gemini_provider_is_not_advertised_as_runtime_supported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COOLACCESS_AI_ENABLED", "true")
    monkeypatch.setenv("COOLACCESS_AI_PROVIDER", "gemini")
    monkeypatch.setenv("COOLACCESS_AI_API_KEY", "test-only-placeholder")
    assert load_ai_config() is None
    assert isinstance(get_runtime_model_gateway(), DisabledModelGateway)


def test_frontend_contract_and_truth_guards_are_present() -> None:
    map_source = (PROJECT_ROOT / "frontend/src/components/MapView.tsx").read_text(
        encoding="utf-8"
    )
    app_source = (PROJECT_ROOT / "frontend/src/App.tsx").read_text(encoding="utf-8")
    panel_source = (
        PROJECT_ROOT / "frontend/src/components/HeatIntelligencePanel.tsx"
    ).read_text(encoding="utf-8")
    overlay_source = (
        PROJECT_ROOT / "frontend/src/components/ProcessingOverlay.tsx"
    ).read_text(encoding="utf-8")
    baseline_source = (
        PROJECT_ROOT / "frontend/src/components/BaselineComparison.tsx"
    ).read_text(encoding="utf-8")
    replacement_source = (
        PROJECT_ROOT / "frontend/src/components/ReplacementDrawer.tsx"
    ).read_text(encoding="utf-8")

    assert "props.thermal_priority" in map_source
    assert "props.thermal_weight" not in map_source
    assert "?? 34.0" not in map_source
    assert "return '#475569'" in map_source
    assert "AbortController" in app_source
    assert "requestGeneration !== requestGenerationRef.current" in app_source
    assert "Why was DC_148 rejected in favor of DC_135?" not in panel_source
    assert "comparisonSelectedId" in panel_source
    assert "exact live stage is not reported" in panel_source
    assert "timer reports elapsed request time, not backend stage completion" in panel_source
    assert "currentStageIndex" not in panel_source
    assert "isCompleted" not in panel_source
    assert "EXACT LIVE STAGE NOT REPORTED" in overlay_source
    assert "phase completion is not inferred from elapsed time" in overlay_source
    assert "currentStageIdx" not in overlay_source
    assert "sequenceFinished" not in overlay_source
    assert "ADDITIONAL PROTECTED RESIDENTS" not in baseline_source
    assert "$0 Cost Increase" not in baseline_source
    assert "AI Explainability:" not in replacement_source
    assert "Deterministic Replacement Evidence" in replacement_source
