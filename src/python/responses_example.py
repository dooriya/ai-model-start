#!/usr/bin/env python3
"""Microsoft Foundry Responses API examples using the standard OpenAI SDK."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from azure.core.exceptions import AzureError
from openai import OpenAIError
from openai.types.shared.reasoning_effort import ReasoningEffort
from pydantic import ValidationError

from responses_common import ExampleError, foundry_client, load_config
from responses_features import (
    DEFAULT_CACHE_KEY,
    DEFAULT_PROMPT,
    SUPPORTED_REASONING_EFFORTS,
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

EXAMPLES = (
    "basic",
    "streaming",
    "function-call",
    "parallel-functions",
    "structured-output",
    "reasoning",
    "prompt-caching",
    "image-input",
    "conversation-state",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run one Microsoft Foundry Responses API example. "
            "The default basic example makes exactly one model request."
        )
    )
    parser.add_argument("--example", choices=EXAMPLES, default="basic")
    parser.add_argument(
        "--model",
        help=(
            "Deployment alias to call. Defaults to AZURE_MODEL_DEPLOYMENT_NAME, then DeepSeek-V3.2."
        ),
    )
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="Prompt for basic/streaming.")
    parser.add_argument("--timeout", type=float, default=60.0, help="Request timeout in seconds.")
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=4096,
        help="Maximum output tokens per request, including reasoning tokens.",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=4,
        help="Local worker bound for --example parallel-functions (1-16).",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=SUPPORTED_REASONING_EFFORTS,
        default="medium",
        help="SDK-supported effort passed unchanged to the request.",
    )
    parser.add_argument(
        "--cache-key",
        default=DEFAULT_CACHE_KEY,
        help="Stable key for --example prompt-caching.",
    )
    parser.add_argument(
        "--image",
        type=Path,
        help="Local image path required by --example image-input.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(
            model=args.model,
            timeout_seconds=args.timeout,
            max_output_tokens=args.max_output_tokens,
        )
        with foundry_client(config) as client:
            if args.example == "basic":
                run_basic(client, config, prompt=args.prompt)
            elif args.example == "streaming":
                run_streaming(client, config, prompt=args.prompt)
            elif args.example == "function-call":
                run_function_call(client, config)
            elif args.example == "parallel-functions":
                run_parallel_function_calls(
                    client,
                    config,
                    max_concurrency=args.max_concurrency,
                )
            elif args.example == "structured-output":
                run_structured_output(client, config)
            elif args.example == "reasoning":
                run_reasoning(
                    client,
                    config,
                    effort=cast(ReasoningEffort, args.reasoning_effort),
                )
            elif args.example == "prompt-caching":
                run_prompt_caching(client, config, cache_key=args.cache_key)
            elif args.example == "image-input":
                if args.image is None:
                    raise ExampleError("--image is required for --example image-input.")
                run_image_input(client, config, image_path=args.image)
            elif args.example == "conversation-state":
                run_conversation_state(client, config)
    except (AzureError, ExampleError, OpenAIError, OSError, ValidationError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
