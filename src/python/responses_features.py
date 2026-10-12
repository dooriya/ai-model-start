"""Copyable Responses API feature examples for the Python CLI."""

from __future__ import annotations

import base64
import mimetypes
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from openai import OpenAI
from openai.types.responses import Response, ResponseFunctionToolCall
from openai.types.responses.easy_input_message_param import EasyInputMessageParam
from openai.types.responses.response_create_params import PromptCacheOptions
from openai.types.responses.response_format_text_json_schema_config_param import (
    ResponseFormatTextJSONSchemaConfigParam,
)
from openai.types.responses.response_input_image_param import ResponseInputImageParam
from openai.types.responses.response_input_param import (
    FunctionCallOutput,
    ResponseInputItemParam,
)
from openai.types.responses.response_input_text_param import ResponseInputTextParam
from openai.types.responses.response_text_config_param import ResponseTextConfigParam
from openai.types.shared.reasoning_effort import ReasoningEffort
from pydantic import BaseModel, ConfigDict, Field

from responses_common import (
    ExampleConfig,
    ExampleError,
    UsageStats,
    completed_text,
    ensure_completed,
    print_response,
    print_usage,
    usage_stats,
)
from responses_weather import (
    WEATHER_TOOL_NAME,
    WeatherArguments,
    WeatherResult,
    get_weather,
    weather_tool,
)

DEFAULT_PROMPT = "Explain quantum computing in three sentences."
DEFAULT_CACHE_KEY = "foundry-responses-python-cache-v1"
SUPPORTED_REASONING_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")
PARALLEL_WEATHER_LOCATIONS = {"London", "Sydney", "Tokyo"}

_CACHE_POLICY_SENTENCE = (
    "Fictional Contoso Trail policy: answer only from this stable guide, identify assumptions, "
    "and recommend contacting a ranger for emergencies."
)
CACHEABLE_PREFIX = "\n".join(
    f"Section {section:02d}. {_CACHE_POLICY_SENTENCE}" for section in range(1, 49)
)


class SupportTicket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=120)
    priority: Literal["low", "medium", "high"]
    action_items: list[str] = Field(min_length=1, max_length=3)


@dataclass(frozen=True)
class StructuredRun:
    response: Response
    parsed: SupportTicket


@dataclass(frozen=True)
class CacheRun:
    first_response: Response
    second_response: Response
    first_usage: UsageStats
    second_usage: UsageStats


@dataclass(frozen=True)
class ValidatedWeatherCall:
    item: ResponseFunctionToolCall
    arguments: WeatherArguments


def run_basic(
    client: OpenAI,
    config: ExampleConfig,
    *,
    prompt: str = DEFAULT_PROMPT,
) -> Response:
    response = client.responses.create(
        model=config.model,
        input=prompt,
        max_output_tokens=config.max_output_tokens,
    )
    print_response(response)
    return response


def run_streaming(
    client: OpenAI,
    config: ExampleConfig,
    *,
    prompt: str = DEFAULT_PROMPT,
) -> Response:
    stream = client.responses.create(
        model=config.model,
        input=prompt,
        max_output_tokens=config.max_output_tokens,
        stream=True,
    )
    terminal_response: Response | None = None
    try:
        for event in stream:
            if event.type == "response.output_text.delta":
                print(event.delta, end="", flush=True)
            elif event.type == "response.completed":
                terminal_response = event.response
                break
            elif event.type in {"response.failed", "response.incomplete"}:
                ensure_completed(event.response)
            elif event.type == "error":
                code = event.code or "unknown_error"
                raise ExampleError(f"Streaming error {code}: {event.message}")
    finally:
        stream.close()

    if terminal_response is None:
        raise ExampleError("Stream ended before a response.completed terminal event.")
    ensure_completed(terminal_response)
    print()
    print_usage(terminal_response)
    return terminal_response


def _validated_weather_calls(response: Response) -> list[ValidatedWeatherCall]:
    ensure_completed(response)
    calls = [item for item in response.output if isinstance(item, ResponseFunctionToolCall)]
    if not calls:
        raise ExampleError("The response completed without a function call.")

    validated: list[ValidatedWeatherCall] = []
    call_ids: set[str] = set()
    for call in calls:
        if call.name != WEATHER_TOOL_NAME:
            raise ExampleError(
                f"Unexpected tool name {call.name!r}; expected {WEATHER_TOOL_NAME!r}."
            )
        if call.status not in {None, "completed"}:
            raise ExampleError(
                f"Tool call {call.call_id!r} has non-terminal status {call.status!r}."
            )
        if not call.call_id:
            raise ExampleError("Function call is missing call_id.")
        if call.call_id in call_ids:
            raise ExampleError(f"Duplicate function call_id {call.call_id!r}.")
        call_ids.add(call.call_id)
        validated.append(
            ValidatedWeatherCall(
                item=call,
                arguments=WeatherArguments.model_validate_json(call.arguments),
            )
        )
    return validated


def _response_input_items(response: Response) -> list[ResponseInputItemParam]:
    return [
        cast(
            ResponseInputItemParam,
            item.model_dump(mode="json", by_alias=True, exclude_none=True),
        )
        for item in response.output
    ]


def _function_output(call: ValidatedWeatherCall, result: WeatherResult) -> FunctionCallOutput:
    return {
        "type": "function_call_output",
        "call_id": call.item.call_id,
        "name": call.item.name,
        "output": result.model_dump_json(),
    }


def _tool_follow_up(
    client: OpenAI,
    config: ExampleConfig,
    first_response: Response,
    calls: list[ValidatedWeatherCall],
    results: list[WeatherResult],
    *,
    parallel_tool_calls: bool,
) -> Response:
    if len(calls) != len(results):
        raise ExampleError("Every validated tool call must have exactly one local result.")

    input_items = _response_input_items(first_response)
    input_items.extend(
        _function_output(call, result) for call, result in zip(calls, results, strict=True)
    )
    response = client.responses.create(
        model=config.model,
        input=input_items,
        tools=[weather_tool()],
        parallel_tool_calls=parallel_tool_calls,
        max_output_tokens=config.max_output_tokens,
    )
    print_response(response)
    return response


def run_function_call(client: OpenAI, config: ExampleConfig) -> Response:
    first_response = client.responses.create(
        model=config.model,
        input="What is the fictional weather in Seattle in Fahrenheit?",
        tools=[weather_tool()],
        tool_choice={"type": "function", "name": WEATHER_TOOL_NAME},
        parallel_tool_calls=False,
        max_output_tokens=config.max_output_tokens,
    )
    calls = _validated_weather_calls(first_response)
    if len(calls) != 1:
        raise ExampleError(f"Expected exactly one function call, received {len(calls)}.")

    result = get_weather(calls[0].arguments)
    return _tool_follow_up(
        client,
        config,
        first_response,
        calls,
        [result],
        parallel_tool_calls=False,
    )


def _run_weather_call(call: ValidatedWeatherCall) -> WeatherResult:
    return get_weather(call.arguments)


def run_parallel_function_calls(
    client: OpenAI,
    config: ExampleConfig,
    *,
    max_concurrency: int,
) -> Response:
    if not 1 <= max_concurrency <= 16:
        raise ExampleError("--max-concurrency must be between 1 and 16.")

    first_response = client.responses.create(
        model=config.model,
        input=(
            "Call get_weather exactly three times together in the next response, before "
            "receiving any tool result. All arguments are already known: London in celsius, "
            "Sydney in celsius, and Tokyo in celsius. Return those three function calls and "
            "no prose."
        ),
        tools=[weather_tool(strict=False)],
        tool_choice="auto",
        parallel_tool_calls=True,
        max_output_tokens=config.max_output_tokens,
    )
    calls = _validated_weather_calls(first_response)
    if len(calls) != 3:
        raise ExampleError(
            "Parallel example requires exactly three function calls in one response; "
            f"received {len(calls)}."
        )
    locations = [call.arguments.location for call in calls]
    if set(locations) != PARALLEL_WEATHER_LOCATIONS or len(set(locations)) != len(locations):
        raise ExampleError(
            "Parallel example requires exactly one call each for London, Sydney, and Tokyo."
        )
    if any(call.arguments.unit != "celsius" for call in calls):
        raise ExampleError("Parallel example requires celsius for all three known arguments.")

    workers = min(max_concurrency, len(calls))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(_run_weather_call, calls))

    return _tool_follow_up(
        client,
        config,
        first_response,
        calls,
        results,
        parallel_tool_calls=True,
    )


def run_structured_output(client: OpenAI, config: ExampleConfig) -> StructuredRun:
    schema = cast(dict[str, object], SupportTicket.model_json_schema())
    format_config: ResponseFormatTextJSONSchemaConfigParam = {
        "type": "json_schema",
        "name": "support_ticket",
        "description": "A triaged fictional support ticket.",
        "schema": schema,
        "strict": True,
    }
    text_config: ResponseTextConfigParam = {"format": format_config}
    response = client.responses.create(
        model=config.model,
        input=(
            "A fictional customer cannot sign in after changing phones. "
            "Create a concise support ticket."
        ),
        text=text_config,
        max_output_tokens=config.max_output_tokens,
    )
    parsed = SupportTicket.model_validate_json(completed_text(response))
    print(parsed.model_dump_json(indent=2))
    print_usage(response)
    return StructuredRun(response=response, parsed=parsed)


def run_reasoning(
    client: OpenAI,
    config: ExampleConfig,
    *,
    effort: ReasoningEffort,
) -> Response:
    if effort is None:
        raise ExampleError("A reasoning effort value is required.")
    response = client.responses.create(
        model=config.model,
        input="Plan a safe two-day migration for a small fictional service.",
        reasoning={"effort": effort},
        max_output_tokens=config.max_output_tokens,
    )
    print_response(response)
    return response


def _cache_input(question: str) -> list[ResponseInputItemParam]:
    stable_content: ResponseInputTextParam = {
        "type": "input_text",
        "text": CACHEABLE_PREFIX,
        "prompt_cache_breakpoint": {"mode": "explicit"},
    }
    question_content: ResponseInputTextParam = {
        "type": "input_text",
        "text": question,
    }
    developer_message: EasyInputMessageParam = {
        "type": "message",
        "role": "developer",
        "content": [stable_content],
    }
    user_message: EasyInputMessageParam = {
        "type": "message",
        "role": "user",
        "content": [question_content],
    }
    return [developer_message, user_message]


def run_prompt_caching(
    client: OpenAI,
    config: ExampleConfig,
    *,
    cache_key: str = DEFAULT_CACHE_KEY,
) -> CacheRun:
    if not cache_key.strip():
        raise ExampleError("--cache-key must not be empty.")
    cache_options: PromptCacheOptions = {"mode": "explicit", "ttl": "30m"}

    first_response = client.responses.create(
        model=config.model,
        input=_cache_input("Summarize the guide's safety rule."),
        prompt_cache_key=cache_key,
        prompt_cache_options=cache_options,
        max_output_tokens=config.max_output_tokens,
    )
    completed_text(first_response)
    first_usage = usage_stats(first_response)
    print_usage(first_response, label="First request")

    second_response = client.responses.create(
        model=config.model,
        input=_cache_input("Summarize the guide's assumption rule."),
        prompt_cache_key=cache_key,
        prompt_cache_options=cache_options,
        max_output_tokens=config.max_output_tokens,
    )
    completed_text(second_response)
    second_usage = usage_stats(second_response)
    print_usage(second_response, label="Second request")

    if second_usage.cached_tokens <= 0:
        raise ExampleError(
            "Prompt caching was not observed: the second response reported "
            f"cached_tokens={second_usage.cached_tokens}. Cache writes alone are not a hit."
        )

    print("Prompt cache hit observed.")
    return CacheRun(
        first_response=first_response,
        second_response=second_response,
        first_usage=first_usage,
        second_usage=second_usage,
    )


def local_image_data_url(path: Path) -> str:
    if not path.is_file():
        raise ExampleError(f"Image file does not exist: {path}")
    media_type = mimetypes.guess_type(path.name)[0]
    if media_type is None or not media_type.startswith("image/"):
        raise ExampleError(f"Could not determine an image media type for: {path}")
    data = path.read_bytes()
    if not data:
        raise ExampleError(f"Image file is empty: {path}")
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def run_image_input(client: OpenAI, config: ExampleConfig, *, image_path: Path) -> Response:
    image: ResponseInputImageParam = {
        "type": "input_image",
        "detail": "auto",
        "image_url": local_image_data_url(image_path),
    }
    message: EasyInputMessageParam = {
        "role": "user",
        "content": [
            {"type": "input_text", "text": "Describe this local image concisely."},
            image,
        ],
    }
    response = client.responses.create(
        model=config.model,
        input=[message],
        max_output_tokens=config.max_output_tokens,
    )
    print_response(response)
    return response


def run_conversation_state(
    client: OpenAI,
    config: ExampleConfig,
) -> tuple[Response, Response]:
    first_response = client.responses.create(
        model=config.model,
        input="Remember that the fictional project codename is Lantern.",
        store=True,
        max_output_tokens=config.max_output_tokens,
    )
    print_response(first_response, label="First response")

    second_response = client.responses.create(
        model=config.model,
        input="What is the project codename?",
        previous_response_id=first_response.id,
        store=True,
        max_output_tokens=config.max_output_tokens,
    )
    print_response(second_response, label="Second response")
    return first_response, second_response
