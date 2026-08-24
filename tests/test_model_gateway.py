"""Unit tests for CoolAccess Model Gateway abstractions and schema validation."""

from __future__ import annotations

import pytest

from coolaccess.agent import (
    VALID_FACILITY_IDS,
    VALID_TIMESTAMPS,
    DisabledModelGateway,
    FakeModelGateway,
    GatewayClassificationContext,
    IntentCode,
    ToolName,
)
from coolaccess.model_gateway import (
    ANSWER_PLAN_SCHEMA,
    TOOL_SELECTION_SCHEMA,
    get_runtime_model_gateway,
    load_ai_config,
)


def test_schema_validity() -> None:
    assert TOOL_SELECTION_SCHEMA["type"] == "object"
    assert "intent_code" in TOOL_SELECTION_SCHEMA["properties"]
    assert "tool_calls" in TOOL_SELECTION_SCHEMA["properties"]
    assert len(TOOL_SELECTION_SCHEMA["properties"]["intent_code"]["enum"]) == 5

    assert ANSWER_PLAN_SCHEMA["type"] == "object"
    assert "intent_code" in ANSWER_PLAN_SCHEMA["properties"]
    assert "sections" in ANSWER_PLAN_SCHEMA["properties"]


def test_load_ai_config_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COOLACCESS_AI_ENABLED", raising=False)
    assert load_ai_config() is None
    assert isinstance(get_runtime_model_gateway(), DisabledModelGateway)


def test_load_ai_config_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COOLACCESS_AI_ENABLED", "true")
    monkeypatch.setenv("COOLACCESS_AI_PROVIDER", "openrouter")
    monkeypatch.setenv("COOLACCESS_AI_API_KEY", "sk-test-key-12345")
    monkeypatch.setenv("COOLACCESS_AI_MODEL", "openrouter/free")

    config = load_ai_config()
    assert config is not None
    assert config.provider == "openrouter"
    assert config.api_key == "sk-test-key-12345"
    assert config.model == "openrouter/free"


def test_fake_gateway_select_tools() -> None:
    gateway = FakeModelGateway()
    context = GatewayClassificationContext(
        question="Why was DC_148 rejected for DC_135?",
        current_timestamp="20:00",
        supported_intents=tuple(IntentCode),
        supported_tools=tuple(ToolName),
        available_facility_ids=VALID_FACILITY_IDS,
        available_timestamps=VALID_TIMESTAMPS,
    )
    sel = gateway.select_tools(context)
    assert sel is not None
    assert sel.intent_code == IntentCode.REPLACEMENT_RATIONALE
    assert len(sel.tool_calls) > 0
