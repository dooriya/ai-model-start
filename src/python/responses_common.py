"""Shared configuration, client lifecycle, response checks, and usage reporting."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from openai import OpenAI
from openai.types.responses import Response

TOKEN_SCOPE = "https://ai.azure.com/.default"
DEFAULT_MODEL = "DeepSeek-R1-0528"


class ExampleError(RuntimeError):
    """Raised when an example does not observe its documented success signal."""


@dataclass(frozen=True)
class ExampleConfig:
    endpoint: str
    model: str
    timeout_seconds: float
    max_output_tokens: int


@dataclass(frozen=True)
class UsageStats:
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    cached_tokens: int
    cache_write_tokens: int


def load_config(
    *,
    model: str | None,
    timeout_seconds: float,
    max_output_tokens: int,
) -> ExampleConfig:
    """Load local configuration without overriding values already in the process."""
    load_dotenv(override=False)

    endpoint = os.environ.get("AZURE_AI_PROJECT_ENDPOINT", "").strip()
    if not endpoint:
        raise ExampleError("AZURE_AI_PROJECT_ENDPOINT must be set.")

    deployment = (model or os.environ.get("AZURE_MODEL_DEPLOYMENT_NAME") or DEFAULT_MODEL).strip()
    if not deployment:
        raise ExampleError("A non-empty deployment alias is required.")
    if timeout_seconds <= 0:
        raise ExampleError("--timeout must be greater than zero.")
    if max_output_tokens <= 0:
        raise ExampleError("--max-output-tokens must be greater than zero.")

    return ExampleConfig(
        endpoint=endpoint,
        model=deployment,
        timeout_seconds=timeout_seconds,
        max_output_tokens=max_output_tokens,
    )


@contextmanager
def foundry_client(config: ExampleConfig) -> Iterator[OpenAI]:
    """Create one keyless OpenAI client and close both client and credential."""
    credential = DefaultAzureCredential()
    client = OpenAI(
        base_url=config.endpoint.rstrip("/") + "/openai/v1",
        api_key=get_bearer_token_provider(credential, TOKEN_SCOPE),
        timeout=config.timeout_seconds,
        max_retries=0,
    )
    try:
        yield client
    finally:
        client.close()
        credential.close()


def ensure_completed(response: Response) -> Response:
    """Require terminal completion and reject refusals instead of printing success."""
    if response.status != "completed":
        details: list[str] = []
        if response.error is not None:
            details.append(f"{response.error.code}: {response.error.message}")
        if response.incomplete_details is not None:
            details.append(f"reason={response.incomplete_details.reason}")
        suffix = f" ({'; '.join(details)})" if details else ""
        raise ExampleError(f"Response {response.id} ended with status {response.status!r}{suffix}.")

    refusals: list[str] = []
    for item in response.output:
        if getattr(item, "type", None) != "message":
            continue
        for part in getattr(item, "content", []):
            if getattr(part, "type", None) == "refusal":
                refusals.append(getattr(part, "refusal", "Request was refused."))
    if refusals:
        raise ExampleError("Model refusal: " + "\n".join(refusals))

    return response


def completed_text(response: Response) -> str:
    """Return non-empty output text from a completed, non-refused response."""
    ensure_completed(response)
    text = response.output_text.strip()
    if not text:
        raise ExampleError(f"Response {response.id} completed without text output.")
    return text


def usage_stats(response: Response) -> UsageStats:
    """Read standard Responses usage, including cache read and write telemetry."""
    usage = response.usage
    if usage is None:
        return UsageStats(None, None, None, 0, 0)

    details = usage.input_tokens_details
    return UsageStats(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        total_tokens=usage.total_tokens,
        cached_tokens=getattr(details, "cached_tokens", 0) or 0,
        cache_write_tokens=getattr(details, "cache_write_tokens", 0) or 0,
    )


def print_usage(response: Response, *, label: str = "Usage") -> None:
    stats = usage_stats(response)
    if stats.input_tokens is None:
        print(f"{label}: not reported")
        return
    print(
        f"{label}: input={stats.input_tokens}, output={stats.output_tokens}, "
        f"total={stats.total_tokens}, cached={stats.cached_tokens}, "
        f"cache_write={stats.cache_write_tokens}"
    )


def print_response(response: Response, *, label: str = "Response") -> None:
    print(f"{label}: {completed_text(response)}")
    print(f"Status: {response.status}")
    print_usage(response)
