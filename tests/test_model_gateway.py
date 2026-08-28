from __future__ import annotations

import json
import logging
import time

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


def test_openrouter_json_object_mode() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        body = json.loads(request.content.decode("utf-8"))
        assert body.get("response_format", {}).get("type") == "json_object"
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
    assert len(calls) == 1


def test_openrouter_sequential_calls_no_timing_leak(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[httpx.Request] = []
    current_simulated_time = 1000.0

    def fake_monotonic() -> float:
        nonlocal current_simulated_time
        return current_simulated_time

    monkeypatch.setattr(time, "monotonic", fake_monotonic)

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        valid_tool_selection = {
            "intent_code": "ALLOCATION_SUMMARY",
            "tool_calls": [{"tool_name": "get_allocation_plan"}],
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
                "usage": {"prompt_tokens": 80, "completion_tokens": 20},
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    gateway = OpenRouterModelGateway(
        api_key="sk-test-key",
        model="nvidia/nemotron-3-super-120b-a12b:free",
        total_timeout_seconds=50.0,
        max_turn_timeout_seconds=25.0,
        http_client=mock_client,
    )

    # Structural assertion: Assert no mutable request timing state exists on gateway
    forbidden_attributes = [
        "_start_time",
        "_request_started_at",
        "_request_deadline",
        "_turn_start_time",
        "_start",
    ]
    for attr in forbidden_attributes:
        assert not hasattr(gateway, attr), f"Gateway instance contains forbidden attribute: {attr}"

    context = GatewayClassificationContext(
        question="Which facilities are active at 20:00 UTC?",
        current_timestamp="20:00",
        supported_intents=tuple(IntentCode),
        supported_tools=tuple(ToolName),
        available_facility_ids=VALID_FACILITY_IDS,
        available_timestamps=VALID_TIMESTAMPS,
    )

    # Call 1: at simulated time 1000.0, request deadline is 1050.0
    deadline1 = current_simulated_time + 50.0
    res1 = gateway.select_tools(context, deadline=deadline1)
    assert res1 is not None
    assert len(calls) == 1

    # Advance simulated monotonic time by 60.0s (to 1060.0), far exceeding timeout
    current_simulated_time = 1060.0

    # Call 2 on SAME gateway succeeds with fresh request deadline
    deadline2 = current_simulated_time + 50.0
    res2 = gateway.select_tools(context, deadline=deadline2)
    assert res2 is not None
    assert len(calls) == 2

    # Advance simulated time by another 100.0s (to 1160.0)
    current_simulated_time = 1160.0

    # Call 3 without explicit deadline uses fresh monotonic + total_timeout
    res3 = gateway.select_tools(context)
    assert res3 is not None
    assert len(calls) == 3

    # Structural assertion: Re-verify that calls did NOT inject mutable timing fields
    for attr in forbidden_attributes:
        assert not hasattr(gateway, attr), f"Gateway acquired forbidden attribute {attr}"
    for key in gateway.__dict__:
        assert (
            not key.startswith("_request_")
            and not key.startswith("_turn_")
            and key != "_start_time"
        )


def test_openrouter_concurrent_calls_independent_deadlines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[httpx.Request] = []
    current_simulated_time = 2000.0

    def fake_monotonic() -> float:
        nonlocal current_simulated_time
        return current_simulated_time

    monkeypatch.setattr(time, "monotonic", fake_monotonic)

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {"intent_code": "ALLOCATION_SUMMARY", "tool_calls": []}
                            ),
                        },
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    gateway = OpenRouterModelGateway(
        api_key="sk-test-key",
        model="nvidia/nemotron-3-super-120b-a12b:free",
        total_timeout_seconds=50.0,
        max_turn_timeout_seconds=25.0,
        http_client=mock_client,
    )

    context = GatewayClassificationContext(
        question="Which facilities are active at 20:00 UTC?",
        current_timestamp="20:00",
        supported_intents=tuple(IntentCode),
        supported_tools=tuple(ToolName),
        available_facility_ids=VALID_FACILITY_IDS,
        available_timestamps=VALID_TIMESTAMPS,
    )

    # Request A: starts at t=2000, deadline=2015.0 -> turn timeout is 15.0s
    req_a_deadline = 2015.0
    turn_timeout_a = gateway._get_turn_timeout(deadline=req_a_deadline)
    assert turn_timeout_a == 15.0

    # Request B: starts at t=2005, deadline=2055.0 -> turn timeout is 25.0s (capped by max_turn)
    current_simulated_time = 2005.0
    req_b_deadline = 2055.0
    turn_timeout_b = gateway._get_turn_timeout(deadline=req_b_deadline)
    assert turn_timeout_b == 25.0

    # Request A re-evaluated at t=2005 has remaining 10.0s, unaffected by Request B
    turn_timeout_a_later = gateway._get_turn_timeout(deadline=req_a_deadline)
    assert turn_timeout_a_later == 10.0

    # Both requests execute successfully on the same gateway instance
    res_a = gateway.select_tools(context, deadline=req_a_deadline)
    res_b = gateway.select_tools(context, deadline=req_b_deadline)
    assert res_a is not None
    assert res_b is not None
    assert len(calls) == 2


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
    assert len(calls) == 2
    assert "operation=tool_selection attempt=2" in caplog.text
