from __future__ import annotations

import json
import logging

import httpx
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
    OpenRouterModelGateway,
    _clean_json_content,
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
    monkeypatch.setenv("COOLACCESS_AI_ENABLED", "false")
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


def test_clean_json_content() -> None:
    # Plain JSON string
    assert _clean_json_content('{"key": "value"}') == '{"key": "value"}'
    # Markdown code fence with json
    assert _clean_json_content('```json\n{"key": "value"}\n```') == '{"key": "value"}'
    # Markdown code fence without language
    assert _clean_json_content('```\n{"key": "value"}\n```') == '{"key": "value"}'
    # Whitespace padding
    assert _clean_json_content('   \n {"key": "value"} \n  ') == '{"key": "value"}'


def test_openrouter_schema_fallback_to_json_object() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        body = json.loads(request.content.decode("utf-8"))
        # First call uses json_schema, simulate provider rejection with 400
        if body.get("response_format", {}).get("type") == "json_schema":
            return httpx.Response(
                400,
                json={
                    "error": {
                        "message": "Provider does not support response_format json_schema"
                    }
                },
            )
        # Second call uses json_object mode, simulate successful markdown-wrapped response
        elif body.get("response_format", {}).get("type") == "json_object":
            assert (
                "IMPORTANT: Respond with ONLY a valid raw JSON object"
                in body["messages"][-1]["content"]
            )
            valid_tool_selection = {
                "intent_code": "REPLACEMENT_RATIONALE",
                "tool_calls": [
                    {
                        "tool_name": "get_replacement_evidence",
                        "facility_id": "DC_148",
                        "alternative_id": "DC_135",
                        "target_timestamp": None,
                        "baseline_type": None,
                    }
                ],
            }
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": (
                                    "```json\n" + json.dumps(valid_tool_selection) + "\n```"
                                ),
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 120, "completion_tokens": 45},
                },
            )
        return httpx.Response(500, json={"error": "Unexpected payload format"})

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    gateway = OpenRouterModelGateway(
        api_key="sk-test-key",
        model="google/gemma-4-31b-it:free",
        http_client=mock_client,
    )
    context = GatewayClassificationContext(
        question="Why was DC_148 rejected for DC_135?",
        current_timestamp="20:00",
        supported_intents=tuple(IntentCode),
        supported_tools=tuple(ToolName),
        available_facility_ids=VALID_FACILITY_IDS,
        available_timestamps=VALID_TIMESTAMPS,
    )

    result = gateway.select_tools(context)
    assert result is not None
    assert result.intent_code == IntentCode.REPLACEMENT_RATIONALE
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool_name == ToolName.GET_REPLACEMENT_EVIDENCE
    assert result.tool_calls[0].facility_id == "DC_148"
    assert result.tool_calls[0].alternative_id == "DC_135"
    assert len(calls) == 2  # Proves strict attempt 1 followed by json_object attempt 2


def test_openrouter_schema_fallback_fails_closed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        if body.get("response_format", {}).get("type") == "json_schema":
            return httpx.Response(400, json={"error": {"message": "json_schema not supported"}})
        # Even json_object returns invalid JSON
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "I am not a JSON string!"},
                        "finish_reason": "stop",
                    }
                ]
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    gateway = OpenRouterModelGateway(
        api_key="sk-test-key",
        model="google/gemma-4-31b-it:free",
        http_client=mock_client,
    )
    context = GatewayClassificationContext(
        question="Why was DC_148 rejected for DC_135?",
        current_timestamp="20:00",
        supported_intents=tuple(IntentCode),
        supported_tools=tuple(ToolName),
        available_facility_ids=VALID_FACILITY_IDS,
        available_timestamps=VALID_TIMESTAMPS,
    )

    with pytest.raises(RuntimeError):
        gateway.select_tools(context)


def test_openrouter_rate_limit_retry_success() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(
                429,
                headers={"retry-after": "0.1"},
                json={"error": {"message": "Rate limit exceeded"}},
            )
        valid_tool_selection = {
            "intent_code": "REPLACEMENT_RATIONALE",
            "tool_calls": [
                {
                    "tool_name": "get_replacement_evidence",
                    "facility_id": "DC_148",
                    "alternative_id": "DC_135",
                }
            ],
        }
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(valid_tool_selection),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 30},
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    gateway = OpenRouterModelGateway(
        api_key="sk-test-key",
        model="google/gemma-4-31b-it:free",
        http_client=mock_client,
    )
    context = GatewayClassificationContext(
        question="Why was DC_148 rejected for DC_135?",
        current_timestamp="20:00",
        supported_intents=tuple(IntentCode),
        supported_tools=tuple(ToolName),
        available_facility_ids=VALID_FACILITY_IDS,
        available_timestamps=VALID_TIMESTAMPS,
    )

    result = gateway.select_tools(context)
    assert result is not None
    assert result.intent_code == IntentCode.REPLACEMENT_RATIONALE
    assert len(calls) == 2


def test_openrouter_rate_limit_exhausted(caplog: pytest.LogCaptureFixture) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            429,
            headers={"retry-after": "0.1"},
            json={"error": {"message": "Rate limit exceeded"}},
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    gateway = OpenRouterModelGateway(
        api_key="sk-test-key",
        model="google/gemma-4-31b-it:free",
        http_client=mock_client,
    )
    context = GatewayClassificationContext(
        question="Why was DC_148 rejected for DC_135?",
        current_timestamp="20:00",
        supported_intents=tuple(IntentCode),
        supported_tools=tuple(ToolName),
        available_facility_ids=VALID_FACILITY_IDS,
        available_timestamps=VALID_TIMESTAMPS,
    )

    with caplog.at_level(logging.INFO), pytest.raises(RuntimeError) as exc_info:
        gateway.select_tools(context)
    assert "quota exceeded" in str(exc_info.value)
    # Hardened fail-fast policy executes at most 2 attempts (initial + 1 retry)
    assert len(calls) == 2
    assert "operation=tool_selection attempt=2" in caplog.text
