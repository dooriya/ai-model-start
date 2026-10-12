from __future__ import annotations

import json
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import httpx2
import pytest
from openai import OpenAI
from pydantic import ValidationError

import responses_features
from responses_common import ExampleConfig, ExampleError
from responses_example import build_parser
from responses_features import (
    run_basic,
    run_conversation_state,
    run_function_call,
    run_image_input,
    run_parallel_function_calls,
    run_prompt_caching,
    run_reasoning,
    run_streaming,
    run_structured_output,
)
from responses_weather import WEATHER_TOOL_NAME

MODEL_ALIAS = "opaque-deployment-alias"


def usage(*, cached: int = 0, cache_write: int = 0) -> dict[str, object]:
    return {
        "input_tokens": 1300,
        "input_tokens_details": {
            "cached_tokens": cached,
            "cache_write_tokens": cache_write,
        },
        "output_tokens": 20,
        "output_tokens_details": {"reasoning_tokens": 0},
        "total_tokens": 1320,
    }


def message_output(text: str) -> dict[str, object]:
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "output_text", "text": text, "annotations": []}],
    }


def refusal_output(text: str) -> dict[str, object]:
    return {
        "id": "msg_refusal",
        "type": "message",
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "refusal", "refusal": text}],
    }


def function_call(
    call_id: str,
    *,
    location: str = "Seattle",
    name: str = WEATHER_TOOL_NAME,
    arguments: str | None = None,
) -> dict[str, object]:
    return {
        "id": f"fc_{call_id or 'missing'}",
        "type": "function_call",
        "status": "completed",
        "call_id": call_id,
        "name": name,
        "arguments": arguments
        if arguments is not None
        else json.dumps({"location": location, "unit": "celsius"}),
    }


def response_payload(
    *output: dict[str, object],
    response_id: str = "resp_1",
    status: str = "completed",
    cached: int = 0,
    cache_write: int = 0,
    error: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "id": response_id,
        "object": "response",
        "created_at": 1.0,
        "model": MODEL_ALIAS,
        "output": list(output),
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "tools": [],
        "status": status,
        "error": error,
        "usage": usage(cached=cached, cache_write=cache_write),
    }


Payload = dict[str, object] | str


class MockResponses:
    def __init__(self, payloads: list[Payload]) -> None:
        self.payloads = iter(payloads)
        self.requests: list[dict[str, Any]] = []

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        assert request.url.host == "example.test"
        assert request.url.path == "/openai/v1/responses"
        self.requests.append(json.loads(request.content.decode("utf-8")))
        payload = next(self.payloads)
        if isinstance(payload, str):
            return httpx2.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=payload.encode("utf-8"),
            )
        return httpx2.Response(200, json=payload)


@contextmanager
def mock_client(*payloads: Payload) -> Iterator[tuple[OpenAI, MockResponses]]:
    server = MockResponses(list(payloads))
    http_client = httpx2.Client(transport=httpx2.MockTransport(server.handle))
    client = OpenAI(
        api_key="offline-test",
        base_url="https://example.test/openai/v1",
        http_client=http_client,
        max_retries=0,
    )
    try:
        yield client, server
    finally:
        client.close()


@pytest.fixture
def config() -> ExampleConfig:
    return ExampleConfig(
        endpoint="https://example.test",
        model=MODEL_ALIAS,
        timeout_seconds=5,
        max_output_tokens=321,
    )


def sse(*events: dict[str, object]) -> str:
    return "".join(f"data: {json.dumps(event)}\n\n" for event in events) + "data: [DONE]\n\n"


def test_cli_defaults_to_one_basic_example() -> None:
    args = build_parser().parse_args([])
    assert args.example == "basic"
    assert args.model is None
    assert args.max_output_tokens == 4096
    assert build_parser().parse_args(["--max-output-tokens", "500"]).max_output_tokens == 500


def test_basic_sends_exactly_one_minimal_request(config: ExampleConfig) -> None:
    with mock_client(response_payload(message_output("A concise answer."))) as (client, server):
        run_basic(client, config)

    assert server.requests == [
        {
            "model": MODEL_ALIAS,
            "input": responses_features.DEFAULT_PROMPT,
            "max_output_tokens": 321,
        }
    ]


def test_completed_response_rejects_refusal(config: ExampleConfig) -> None:
    with mock_client(response_payload(refusal_output("Not available."))) as (client, server):
        with pytest.raises(ExampleError, match="Model refusal"):
            run_basic(client, config)

    assert len(server.requests) == 1


def test_streaming_requires_completed_terminal_event(config: ExampleConfig) -> None:
    completed = response_payload(message_output("Hello"), response_id="resp_stream")
    events = sse(
        {
            "type": "response.output_text.delta",
            "delta": "Hello",
            "item_id": "msg_1",
            "output_index": 0,
            "content_index": 0,
            "sequence_number": 1,
        },
        {
            "type": "response.completed",
            "response": completed,
            "sequence_number": 2,
        },
    )
    with mock_client(events) as (client, server):
        response = run_streaming(client, config)

    assert response.id == "resp_stream"
    assert server.requests == [
        {
            "model": MODEL_ALIAS,
            "input": responses_features.DEFAULT_PROMPT,
            "max_output_tokens": 321,
            "stream": True,
        }
    ]


def test_partial_stream_is_not_success(config: ExampleConfig) -> None:
    events = sse(
        {
            "type": "response.output_text.delta",
            "delta": "partial",
            "item_id": "msg_1",
            "output_index": 0,
            "content_index": 0,
            "sequence_number": 1,
        }
    )
    with mock_client(events) as (client, server):
        with pytest.raises(ExampleError, match="before a response.completed"):
            run_streaming(client, config)

    assert len(server.requests) == 1


def test_failed_stream_surfaces_terminal_error(config: ExampleConfig) -> None:
    failed = response_payload(
        response_id="resp_failed",
        status="failed",
        error={"code": "model_error", "message": "fictional failure"},
    )
    events = sse(
        {
            "type": "response.failed",
            "response": failed,
            "sequence_number": 1,
        }
    )
    with mock_client(events) as (client, _server):
        with pytest.raises(ExampleError, match="fictional failure"):
            run_streaming(client, config)


def test_stream_error_event_surfaces_code_and_message(config: ExampleConfig) -> None:
    events = sse(
        {
            "type": "error",
            "code": "stream_error",
            "message": "fictional stream error",
            "param": None,
            "sequence_number": 1,
        }
    )
    with mock_client(events) as (client, _server):
        with pytest.raises(ExampleError, match="stream_error: fictional stream error"):
            run_streaming(client, config)


def test_single_function_round_trip_validates_and_matches_call_id(
    config: ExampleConfig,
) -> None:
    first = response_payload(function_call("call_weather"), response_id="resp_tool")
    second = response_payload(message_output("Seattle is fictional and overcast."))
    with mock_client(first, second) as (client, server):
        run_function_call(client, config)

    assert len(server.requests) == 2
    initial = server.requests[0]
    assert initial["parallel_tool_calls"] is False
    assert initial["tool_choice"] == {"type": "function", "name": WEATHER_TOOL_NAME}
    tool = initial["tools"][0]
    assert tool["name"] == WEATHER_TOOL_NAME
    assert tool["strict"] is True
    assert tool["parameters"]["additionalProperties"] is False
    assert set(tool["parameters"]["required"]) == {"location", "unit"}

    outputs = [
        item for item in server.requests[1]["input"] if item["type"] == "function_call_output"
    ]
    assert len(outputs) == 1
    assert outputs[0]["call_id"] == "call_weather"
    assert outputs[0]["name"] == WEATHER_TOOL_NAME
    assert json.loads(outputs[0]["output"])["source"] == "fictional-local-fixture"


@pytest.mark.parametrize(
    ("call", "error_type", "message"),
    [
        (
            function_call("call_1", name="unknown_tool"),
            ExampleError,
            "Unexpected tool name",
        ),
        (
            function_call("call_1", arguments='{"location":"Atlantis","unit":"celsius"}'),
            ValidationError,
            "location",
        ),
        (
            function_call(""),
            ExampleError,
            "missing call_id",
        ),
    ],
)
def test_tool_name_arguments_and_call_id_are_validated(
    config: ExampleConfig,
    call: dict[str, object],
    error_type: type[Exception],
    message: str,
) -> None:
    with mock_client(response_payload(call)) as (client, server):
        with pytest.raises(error_type, match=message):
            run_function_call(client, config)
    assert len(server.requests) == 1


def test_parallel_calls_are_in_one_response_and_local_workers_are_bounded(
    config: ExampleConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = response_payload(
        function_call("call_london", location="London"),
        function_call("call_sydney", location="Sydney"),
        function_call("call_tokyo", location="Tokyo"),
        response_id="resp_parallel",
    )
    second = response_payload(message_output("Comparison complete."))
    worker_counts: list[int] = []
    real_executor = ThreadPoolExecutor

    class RecordingExecutor(ThreadPoolExecutor):
        def __init__(self, max_workers: int) -> None:
            worker_counts.append(max_workers)
            super().__init__(max_workers=max_workers)

    monkeypatch.setattr(responses_features, "ThreadPoolExecutor", RecordingExecutor)
    with mock_client(first, second) as (client, server):
        run_parallel_function_calls(client, config, max_concurrency=1)
    monkeypatch.setattr(responses_features, "ThreadPoolExecutor", real_executor)

    assert worker_counts == [1]
    assert server.requests[0]["parallel_tool_calls"] is True
    assert server.requests[0]["tool_choice"] == "auto"
    assert server.requests[0]["tools"][0]["strict"] is False
    assert "exactly three times together" in server.requests[0]["input"]
    outputs = [
        item for item in server.requests[1]["input"] if item["type"] == "function_call_output"
    ]
    assert [item["call_id"] for item in outputs] == [
        "call_london",
        "call_sydney",
        "call_tokyo",
    ]


def test_parallel_example_rejects_one_call_and_duplicate_ids(
    config: ExampleConfig,
) -> None:
    one_call = response_payload(function_call("call_only"))
    with mock_client(one_call) as (client, _server):
        with pytest.raises(ExampleError, match="exactly three function calls"):
            run_parallel_function_calls(client, config, max_concurrency=2)

    duplicates = response_payload(
        function_call("duplicate", location="London"),
        function_call("duplicate", location="Tokyo"),
    )
    with mock_client(duplicates) as (client, _server):
        with pytest.raises(ExampleError, match="Duplicate function call_id"):
            run_parallel_function_calls(client, config, max_concurrency=2)

    wrong_locations = response_payload(
        function_call("call_london", location="London"),
        function_call("call_sydney", location="Sydney"),
        function_call("call_seattle", location="Seattle"),
    )
    with mock_client(wrong_locations) as (client, _server):
        with pytest.raises(ExampleError, match="exactly one call each"):
            run_parallel_function_calls(client, config, max_concurrency=2)


def test_structured_output_sends_strict_schema_and_parses_with_pydantic(
    config: ExampleConfig,
) -> None:
    ticket = {
        "summary": "Customer cannot sign in",
        "priority": "high",
        "action_items": ["Verify recovery options"],
    }
    with mock_client(response_payload(message_output(json.dumps(ticket)))) as (client, server):
        result = run_structured_output(client, config)

    assert result.parsed.priority == "high"
    response_format = server.requests[0]["text"]["format"]
    assert response_format["type"] == "json_schema"
    assert response_format["strict"] is True
    assert response_format["schema"]["additionalProperties"] is False


def test_invalid_structured_output_is_not_repaired_or_retried(
    config: ExampleConfig,
) -> None:
    invalid = {"summary": "Missing required fields"}
    with mock_client(response_payload(message_output(json.dumps(invalid)))) as (client, server):
        with pytest.raises(ValidationError):
            run_structured_output(client, config)
    assert len(server.requests) == 1


def test_reasoning_effort_is_passed_unchanged(config: ExampleConfig) -> None:
    with mock_client(response_payload(message_output("A migration plan."))) as (client, server):
        run_reasoning(client, config, effort="xhigh")
    assert server.requests[0]["reasoning"] == {"effort": "xhigh"}


def test_prompt_cache_requires_positive_cached_tokens(config: ExampleConfig) -> None:
    first = response_payload(
        message_output("First answer."),
        cache_write=1200,
        response_id="resp_cache_write",
    )
    second = response_payload(
        message_output("Second answer."),
        cached=1100,
        response_id="resp_cache_hit",
    )
    with mock_client(first, second) as (client, server):
        result = run_prompt_caching(client, config, cache_key="stable-key")

    assert result.first_usage.cache_write_tokens == 1200
    assert result.second_usage.cached_tokens == 1100
    assert len(server.requests) == 2
    questions = [
        "Summarize the guide's safety rule.",
        "Summarize the guide's assumption rule.",
    ]
    for request, question in zip(server.requests, questions, strict=True):
        assert request["prompt_cache_key"] == "stable-key"
        assert request["prompt_cache_options"] == {"mode": "explicit", "ttl": "30m"}
        assert request["input"] == [
            {
                "type": "message",
                "role": "developer",
                "content": [
                    {
                        "type": "input_text",
                        "text": responses_features.CACHEABLE_PREFIX,
                        "prompt_cache_breakpoint": {"mode": "explicit"},
                    }
                ],
            },
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": question}],
            },
        ]
    assert server.requests[0]["input"][0] == server.requests[1]["input"][0]


def test_cache_write_without_read_is_not_success(config: ExampleConfig) -> None:
    first = response_payload(message_output("First."), cache_write=1200)
    second = response_payload(message_output("Second."), cache_write=1200)
    with mock_client(first, second) as (client, server):
        with pytest.raises(ExampleError, match="Cache writes alone are not a hit"):
            run_prompt_caching(client, config)
    assert len(server.requests) == 2


def test_missing_cache_write_telemetry_does_not_break_basic_usage(
    config: ExampleConfig,
) -> None:
    payload = response_payload(message_output("No cache telemetry."))
    del payload["usage"]["input_tokens_details"]["cache_write_tokens"]
    with mock_client(payload) as (client, server):
        response = run_basic(client, config)
    assert response.output_text == "No cache telemetry."
    assert len(server.requests) == 1


def test_local_image_is_sent_as_base64_data_url(
    config: ExampleConfig,
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "fixture.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\nfictional")
    with mock_client(response_payload(message_output("An image."))) as (client, server):
        run_image_input(client, config, image_path=image_path)

    image = server.requests[0]["input"][0]["content"][1]
    assert image["type"] == "input_image"
    assert image["detail"] == "auto"
    assert image["image_url"].startswith("data:image/png;base64,")
    assert str(image_path) not in image["image_url"]


def test_conversation_state_uses_store_and_previous_response_id(
    config: ExampleConfig,
) -> None:
    first = response_payload(message_output("I will remember."), response_id="resp_state_1")
    second = response_payload(message_output("Lantern."), response_id="resp_state_2")
    with mock_client(first, second) as (client, server):
        run_conversation_state(client, config)

    assert len(server.requests) == 2
    assert server.requests[0]["store"] is True
    assert "previous_response_id" not in server.requests[0]
    assert server.requests[1]["store"] is True
    assert server.requests[1]["previous_response_id"] == "resp_state_1"
