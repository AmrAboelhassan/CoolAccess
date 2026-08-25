"""Table-driven free-form question test matrix for CoolAccess AI layer.

Tests ~45 representative judge and operator utterances across:
1. ALLOCATION_SUMMARY
2. DIURNAL_HEAT_TRANSITION
3. HEAT_VULNERABILITY_EXPLANATION (all 6 locked scenario facilities)
4. REPLACEMENT_RATIONALE
5. BASELINE_COMPARISON
6. OUT_OF_SCOPE / UNSUPPORTED inquiries
"""

from __future__ import annotations

import pytest

from coolaccess.agent import (
    CopilotStatus,
    FakeModelGateway,
    HeatBriefRequest,
    IntentCode,
    generate_heat_brief,
)
from coolaccess.scenario import ScenarioBundle, load_locked_scenario


@pytest.fixture(scope="module")
def bundle() -> ScenarioBundle:
    return load_locked_scenario()


@pytest.fixture(scope="module")
def fake_gateway() -> FakeModelGateway:
    return FakeModelGateway()


# -----------------------------------------------------------------------------
# 1. Allocation Summary Utterances
# -----------------------------------------------------------------------------
ALLOCATION_UTTERANCES = [
    "Which facilities are prioritized right now?",
    "Summarize the current cooling allocation.",
    "Why are these three active?",
    "Show the active cooling centers.",
    "Give me an overview of the selected facilities.",
    "What is the optimal deployment plan?",
    "Current cooling center distribution overview.",
]


@pytest.mark.parametrize("query", ALLOCATION_UTTERANCES)
def test_allocation_summary_utterances(
    bundle: ScenarioBundle, fake_gateway: FakeModelGateway, query: str
) -> None:
    req = HeatBriefRequest(question=query, timestamp="16:00")
    resp = generate_heat_brief(req, bundle, gateway=fake_gateway)
    assert resp.status == CopilotStatus.AI_GENERATED
    assert resp.intent_code == IntentCode.ALLOCATION_SUMMARY
    assert len(resp.brief_items) >= 2
    assert any("claim:alloc" in item.claim_id for item in resp.brief_items)


# -----------------------------------------------------------------------------
# 2. Diurnal Transition Utterances
# -----------------------------------------------------------------------------
DIURNAL_UTTERANCES = [
    "What changed between noon and 4 PM?",
    "How did thermal exposure shift through the day?",
    "What did FortyGuard data change in the allocation?",
    "Why did facility selection shift at 20:00 UTC?",
    "Explain the diurnal transition between 16:00 and 20:00.",
    "How did the spatial heat pattern evolve?",
    "Which areas stayed hotter later in the evening?",
    "Why did cooling centers change in the evening?",
]


@pytest.mark.parametrize("query", DIURNAL_UTTERANCES)
def test_diurnal_transition_utterances(
    bundle: ScenarioBundle, fake_gateway: FakeModelGateway, query: str
) -> None:
    req = HeatBriefRequest(question=query, timestamp="20:00")
    resp = generate_heat_brief(req, bundle, gateway=fake_gateway)
    assert resp.status == CopilotStatus.AI_GENERATED
    assert resp.intent_code == IntentCode.DIURNAL_HEAT_TRANSITION
    assert len(resp.brief_items) >= 2
    claim_ids = [item.claim_id for item in resp.brief_items]
    assert any("diurnal" in cid or "thermal" in cid or "alloc" in cid for cid in claim_ids)


# -----------------------------------------------------------------------------
# 3. Facility Rationale & Exposure Utterances (All 6 Scenario Facilities)
# -----------------------------------------------------------------------------
FACILITY_EXPOSURE_UTTERANCES = [
    ("Why is Shaw Library important?", "DC_089"),
    ("What thermal and population evidence supports DC_089?", "DC_089"),
    ("Why Martin Luther King Jr. Memorial Library?", "DC_135"),
    ("Analyze DC_135 heat exposure and population density.", "DC_135"),
    ("Why is Northeast Library selected?", "DC_148"),
    ("What evidence supports DC_148?", "DC_148"),
    ("Explain the role of Southeast Library.", "DC_159"),
    ("What thermal evidence supports DC_159?", "DC_159"),
    ("Why is Randall Recreation Center prioritized?", "DC_166"),
    ("What population and heat numbers justify DC_166?", "DC_166"),
    ("Why Southwest Library?", "DC_168"),
    ("What evidence supports DC_168 from FortyGuard data?", "DC_168"),
]


@pytest.mark.parametrize("query, expected_fid", FACILITY_EXPOSURE_UTTERANCES)
def test_facility_exposure_all_six_facilities(
    bundle: ScenarioBundle, fake_gateway: FakeModelGateway, query: str, expected_fid: str
) -> None:
    req = HeatBriefRequest(question=query, timestamp="16:00")
    resp = generate_heat_brief(req, bundle, gateway=fake_gateway)
    assert resp.status == CopilotStatus.AI_GENERATED
    assert resp.intent_code == IntentCode.HEAT_VULNERABILITY_EXPLANATION
    assert len(resp.brief_items) >= 2
    # Verify the specific facility is cited
    assert any(
        item.facility_id == expected_fid or expected_fid in item.server_rendered_text
        for item in resp.brief_items
    )


# -----------------------------------------------------------------------------
# 4. Replacement Rationale Utterances
# -----------------------------------------------------------------------------
REPLACEMENT_UTTERANCES = [
    "Why Shaw instead of MLK?",
    "Why was Northeast Library replaced at 20:00?",
    "What would be lost by swapping these facilities?",
    "Why DC_135 over DC_148?",
    "What is the tradeoff between DC_135 and DC_148?",
    "Why not replace Shaw with Southwest?",
    "Evaluate the replacement of DC_166 with DC_159.",
    "Why was the alternative facility rejected?",
]


@pytest.mark.parametrize("query", REPLACEMENT_UTTERANCES)
def test_replacement_rationale_utterances(
    bundle: ScenarioBundle, fake_gateway: FakeModelGateway, query: str
) -> None:
    req = HeatBriefRequest(question=query, timestamp="20:00")
    resp = generate_heat_brief(req, bundle, gateway=fake_gateway)
    assert resp.status == CopilotStatus.AI_GENERATED
    assert resp.intent_code == IntentCode.REPLACEMENT_RATIONALE
    assert len(resp.brief_items) >= 2
    claim_ids = [item.claim_id for item in resp.brief_items]
    assert any("claim:rep" in cid for cid in claim_ids)


# -----------------------------------------------------------------------------
# 5. Baseline Comparison Utterances
# -----------------------------------------------------------------------------
BASELINE_UTTERANCES = [
    "Why not keep the midday plan?",
    "Why not just choose the hottest facilities?",
    "How much better is the optimized allocation?",
    "Compare dynamic allocation to the static baseline.",
    "How does optimization outperform naive thermal selection?",
    "What is the efficiency gain over static allocation?",
]


@pytest.mark.parametrize("query", BASELINE_UTTERANCES)
def test_baseline_comparison_utterances(
    bundle: ScenarioBundle, fake_gateway: FakeModelGateway, query: str
) -> None:
    req = HeatBriefRequest(question=query, timestamp="16:00")
    resp = generate_heat_brief(req, bundle, gateway=fake_gateway)
    assert resp.status == CopilotStatus.AI_GENERATED
    assert resp.intent_code == IntentCode.BASELINE_COMPARISON
    assert len(resp.brief_items) >= 2
    claim_ids = [item.claim_id for item in resp.brief_items]
    assert any("claim:base" in cid for cid in claim_ids)


# -----------------------------------------------------------------------------
# 6. Out-of-Scope / Unsupported Inquiries
# -----------------------------------------------------------------------------
UNSUPPORTED_UTTERANCES = [
    "What are the clinical symptoms of heat stroke?",
    "How should a doctor treat heat exhaustion?",
    "What is the weather forecast for tomorrow?",
    "Show live radar for next week.",
    "Please change k=5 to open 5 facilities.",
    "Add a new facility at Dupont Circle.",
    "Override the integer optimizer constraints.",
]


@pytest.mark.parametrize("query", UNSUPPORTED_UTTERANCES)
def test_unsupported_scope_utterances(
    bundle: ScenarioBundle, fake_gateway: FakeModelGateway, query: str
) -> None:
    req = HeatBriefRequest(question=query, timestamp="16:00")
    resp = generate_heat_brief(req, bundle, gateway=fake_gateway)
    assert resp.status == CopilotStatus.UNSUPPORTED
    assert resp.intent_code is None
    assert "Inquiry outside closed heat intelligence intent scope" in (resp.fallback_reason or "")
    assert len(resp.brief_items) == 1
    assert "outside the operational scope of CoolAccess" in resp.brief_items[0].server_rendered_text
