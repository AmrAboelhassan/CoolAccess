"""Tests for CoolAccess AI reliability, latency fail-fast policy, and the 7 supported inquiries."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator

import httpx
import pytest

from coolaccess.agent import (
    CopilotStatus,
    HeatBriefRequest,
    IntentCode,
    generate_heat_brief,
)
from coolaccess.model_gateway import (
    OPENROUTER_DEFAULT_TOTAL_TIMEOUT_SECONDS,
    OPENROUTER_MAX_TURN_TIMEOUT_SECONDS,
    OpenRouterModelGateway,
)
from coolaccess.scenario import ScenarioBundle, load_locked_scenario


@pytest.fixture(scope="module")
def bundle() -> ScenarioBundle:
    return load_locked_scenario()


def test_openrouter_timeout_constants_and_budget() -> None:
    assert OPENROUTER_DEFAULT_TOTAL_TIMEOUT_SECONDS == 45.0
    assert OPENROUTER_MAX_TURN_TIMEOUT_SECONDS == 15.0

    gateway = OpenRouterModelGateway(api_key="mock_key")
    turn_timeout = gateway._get_turn_timeout()
    assert turn_timeout <= 15.0


def test_openrouter_shared_deadline_caps_later_turns() -> None:
    gateway = OpenRouterModelGateway(api_key="mock_key")
    gateway._start_time = time.monotonic() - 30.0
    assert 14.5 <= gateway._get_turn_timeout() <= 15.0

    gateway._start_time = time.monotonic() - 44.6
    with pytest.raises(TimeoutError, match="Overall Temperature Intelligence request deadline"):
        gateway._get_turn_timeout()


def test_openrouter_enforces_outer_wall_clock_attempt_timeout() -> None:
    calls = 0
    active_streams = 0
    cancelled_streams = 0
    closed_streams = 0

    class SlowDripStream(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            nonlocal active_streams, cancelled_streams
            active_streams += 1
            try:
                while True:
                    await asyncio.sleep(0.01)
                    yield b" "
            except asyncio.CancelledError:
                cancelled_streams += 1
                raise
            finally:
                active_streams -= 1

        async def aclose(self) -> None:
            nonlocal closed_streams
            closed_streams += 1

    async def slow_handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            status_code=200,
            headers={"content-type": "application/json"},
            stream=SlowDripStream(),
            request=request,
        )

    transport = httpx.MockTransport(slow_handler)
    gateway = OpenRouterModelGateway(
        api_key="mock_key",
        total_timeout_seconds=1.0,
        max_turn_timeout_seconds=0.05,
        http_transport=transport,
    )

    started = time.monotonic()
    with pytest.raises(TimeoutError, match="wall-clock deadline"):
        gateway._execute_chat_completion(
            messages=[{"role": "user", "content": "test"}],
            schema_name="test_schema",
            schema_dict={"type": "object"},
            operation="tool_selection",
        )
    elapsed = time.monotonic() - started

    assert calls == 1
    assert elapsed < 0.15
    assert active_streams == 0
    assert cancelled_streams == 1
    assert closed_streams >= 1


def test_openrouter_cancels_timed_out_stream_before_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    active_streams = 0
    active_when_retry_started: int | None = None
    cancelled_streams = 0
    closed_streams = 0

    class FirstAttemptSlowStream(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            nonlocal active_streams, cancelled_streams
            active_streams += 1
            try:
                while True:
                    await asyncio.sleep(0.01)
                    yield b" "
            except asyncio.CancelledError:
                cancelled_streams += 1
                raise
            finally:
                active_streams -= 1

        async def aclose(self) -> None:
            nonlocal closed_streams
            closed_streams += 1

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls, active_when_retry_started
        calls += 1
        if calls == 1:
            return httpx.Response(
                status_code=200,
                headers={"content-type": "application/json"},
                stream=FirstAttemptSlowStream(),
                request=request,
            )
        active_when_retry_started = active_streams
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    monkeypatch.setattr("coolaccess.model_gateway.OPENROUTER_RETRY_BACKOFF_SECONDS", 0.01)
    gateway = OpenRouterModelGateway(
        api_key="mock_key",
        total_timeout_seconds=2.0,
        max_turn_timeout_seconds=0.55,
        http_transport=httpx.MockTransport(handler),
    )

    result = gateway._execute_chat_completion(
        messages=[{"role": "user", "content": "test"}],
        schema_name="test_schema",
        schema_dict={"type": "object"},
        operation="tool_selection",
    )

    assert result.attempts_made == 2
    assert calls == 2
    assert active_when_retry_started == 0
    assert active_streams == 0
    assert cancelled_streams == 1
    assert closed_streams >= 1


def test_openrouter_single_retry_on_transient_error() -> None:
    """Verify that OpenRouterModelGateway attempts at most 2 HTTP calls on transient errors."""
    call_count = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(status_code=429, json={"error": {"message": "Rate limit exceeded"}})

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    gateway = OpenRouterModelGateway(api_key="mock_key", http_client=mock_client)

    with pytest.raises(httpx.HTTPStatusError):
        gateway._execute_chat_completion(
            messages=[{"role": "user", "content": "test"}],
            schema_name="test_schema",
            schema_dict={"type": "object"},
            operation="tool_selection",
        )

    # Exactly 2 calls made (initial + 1 retry)
    assert call_count == 2


def test_schema_fallback_and_transient_failure_still_cap_at_two_calls() -> None:
    response_formats: list[str] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        response_format = payload["response_format"]["type"]
        response_formats.append(response_format)
        if len(response_formats) == 1:
            return httpx.Response(status_code=400, json={"error": "schema unsupported"})
        return httpx.Response(
            status_code=429,
            headers={"retry-after": "0.1"},
            json={"error": {"message": "Rate limit exceeded"}},
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    gateway = OpenRouterModelGateway(api_key="mock_key", http_client=mock_client)

    with pytest.raises(httpx.HTTPStatusError):
        gateway._execute_chat_completion(
            messages=[{"role": "user", "content": "test"}],
            schema_name="test_schema",
            schema_dict={"type": "object"},
            operation="tool_selection",
        )

    assert response_formats == ["json_schema", "json_object"]


def test_terminal_second_attempt_400_is_not_hidden_by_stale_retry_error() -> None:
    response_formats: list[str] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        response_formats.append(payload["response_format"]["type"])
        if len(response_formats) == 1:
            return httpx.Response(
                status_code=429,
                headers={"retry-after": "0.1"},
                json={"error": "transient"},
            )
        return httpx.Response(status_code=400, json={"error": "terminal schema error"})

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    gateway = OpenRouterModelGateway(api_key="mock_key", http_client=client)

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        gateway._execute_chat_completion(
            messages=[{"role": "user", "content": "test"}],
            schema_name="test_schema",
            schema_dict={"type": "object"},
            operation="tool_selection",
        )

    assert response_formats == ["json_schema", "json_schema"]
    assert exc_info.value.response.status_code == 400


@pytest.mark.parametrize(
    "question,timestamp,expected_intent",
    [
        (
            "What changed in the prepared thermal pattern between 16:00 and 20:00 UTC?",
            "16:00",
            IntentCode.DIURNAL_HEAT_TRANSITION,
        ),
        (
            "Where does heat-weighted demand remain unmet?",
            "16:00",
            IntentCode.ALLOCATION_SUMMARY,
        ),
        (
            "Why was DC_148 selected instead of DC_135 at 16:00 UTC?",
            "16:00",
            IntentCode.REPLACEMENT_RATIONALE,
        ),
        (
            "Why was DC_135 selected instead of DC_148 at 20:00 UTC?",
            "20:00",
            IntentCode.REPLACEMENT_RATIONALE,
        ),
        (
            "Summarize the thermal-priority and population evidence for this allocation.",
            "16:00",
            IntentCode.ALLOCATION_SUMMARY,
        ),
        (
            "Why is DC_148 selected at 16:00 UTC?",
            "16:00",
            IntentCode.DIURNAL_HEAT_TRANSITION,
        ),
        (
            "Why is DC_135 selected at 20:00 UTC?",
            "20:00",
            IntentCode.DIURNAL_HEAT_TRANSITION,
        ),
        (
            "Compare dynamic allocation against the static baseline",
            "16:00",
            IntentCode.BASELINE_COMPARISON,
        ),
        (
            "What does the K=3 constraint change?",
            "16:00",
            IntentCode.ALLOCATION_SUMMARY,
        ),
    ],
)
def test_all_coolaccess_inquiries_matrix(
    question: str,
    timestamp: str,
    expected_intent: IntentCode,
    bundle: ScenarioBundle,
) -> None:
    """All supported inquiries at 16:00/20:00 UTC must route to valid deterministic briefs."""
    req = HeatBriefRequest(
        question=question,
        timestamp=timestamp,
        baseline_timestamp="20:00" if timestamp == "16:00" else "16:00",
        radius_meters=750,
        k=3,
    )
    resp = generate_heat_brief(req, bundle)

    assert resp.status in (CopilotStatus.AI_GENERATED, CopilotStatus.DETERMINISTIC_FALLBACK)
    assert resp.intent_code == expected_intent
    assert len(resp.brief_items) > 0
    assert len(resp.plan_fingerprint) > 0
    assert len(resp.mandatory_caveats) >= 3


def test_coolaccess_out_of_scope_query_safety(bundle: ScenarioBundle) -> None:
    req = HeatBriefRequest(
        question="Can you forecast tomorrow's heat index for Baltimore?",
        timestamp="16:00",
    )
    resp = generate_heat_brief(req, bundle)

    assert resp.status == CopilotStatus.UNSUPPORTED
    assert resp.fallback_reason is not None
    assert "scope" in resp.fallback_reason.lower() or "intent" in resp.fallback_reason.lower()
