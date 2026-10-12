# Responses API feature guidance

The Python CLI in `src/python/responses_example.py` is the canonical feature implementation. With no arguments it runs `basic`, which sends one request to the opaque deployment alias in `AZURE_MODEL_DEPLOYMENT_NAME`. Use `--model` to select another alias for the current run.

The examples send the documented request unchanged and surface unsupported-feature errors. Before adopting an optional feature, confirm that the selected deployment supports it and that its quota, content limits, and data-handling policy fit your application.

## Common setup and controls

Every example uses:

- `DefaultAzureCredential` with scope `https://ai.azure.com/.default`
- the standard `OpenAI` client
- the Foundry project endpoint plus `/openai/v1`
- `max_retries=0`, so an example does not create hidden retry traffic
- `--timeout` and `--max-output-tokens` for request bounds

`--max-output-tokens` defaults to `4096` and includes visible output plus reasoning tokens. An explicit lower override is sent unchanged, and a response that exhausts the limit remains an `incomplete` error.

Run commands from `src/python` after installing `requirements.txt`.

```bash
python responses_example.py
python responses_example.py --model my-deployment-alias
python responses_example.py --timeout 90 --max-output-tokens 800
```

Completion is not inferred from HTTP 200. Non-streaming examples require `response.status == "completed"`, reject refusal content, and require text where text is the documented result.

## Feature reference

### Basic response

```bash
python responses_example.py
```

**Request shape:** `model`, string `input`, and `max_output_tokens`.

**Success signal:** one completed, non-refused response with non-empty `output_text`.

**Adaptation:** replace the prompt and consume `response.output_text`. Keep the deployment alias separate from provider or catalog model metadata.

**Prerequisite:** Responses API support.

### Streaming

```bash
python responses_example.py --example streaming
```

**Request shape:** the basic request plus `stream=True`.

**Success signal:** text deltas may be displayed as they arrive, but the example succeeds only after a `response.completed` event containing a completed response. `response.failed`, `response.incomplete`, `error`, and a stream that ends without a terminal event are failures.

**Adaptation:** persist or publish deltas only if your application can also represent terminal failure. A partial stream is not a completed answer.

**Prerequisite:** streaming support for the selected deployment.

### Single local function call

```bash
python responses_example.py --example function-call
```

**Request shape:** a strict `get_weather` function tool, forced function `tool_choice`, and `parallel_tool_calls=False`. The tool JSON Schema is generated from `WeatherArguments`, the same Pydantic model used to validate returned arguments.

**Success signal:** exactly one completed `function_call` with the expected tool name, a non-empty unique `call_id`, and arguments accepted by Pydantic. A second request includes the original response output and one `function_call_output` with the matching `call_id`.

**Adaptation:** replace the fictional fixture with application code only after authentication, authorization, idempotency, and side-effect rules are defined. Never dispatch solely by trusting the model-provided name or arguments.

**Prerequisite:** function-calling and strict tool-schema support.

### Parallel local function calls

```bash
python responses_example.py --example parallel-functions --max-concurrency 4
```

**Request shape:** one response request with `parallel_tool_calls=True`, `tool_choice="auto"`, and a parallel-specific `get_weather` definition with `strict=False`. The prompt supplies all three known city/unit pairs and requires the calls together before any tool result. Returned arguments are still validated locally with Pydantic.

**Success signal:** exactly three validated function calls must occur in that single response: one each for London, Sydney, and Tokyo in Celsius. No local work starts until the complete batch is validated. Work then runs through a `ThreadPoolExecutor` bounded to `1..16` workers, and one follow-up request returns every result with its original `call_id`.

**Adaptation:** set the worker bound from local resource and downstream service limits. Preserve input/result association rather than relying on completion order.

**Prerequisite:** parallel function-call support. An incomplete or duplicate batch fails without retry or fallback.

### Strict structured output

```bash
python responses_example.py --example structured-output
```

**Request shape:** `text.format.type="json_schema"`, a schema generated from `SupportTicket`, and `strict=True`.

**Success signal:** the completed output text must pass `SupportTicket.model_validate_json`. Invalid output raises a Pydantic validation error; it is not repaired or retried.

**Adaptation:** replace the Pydantic model and format name. Keep server-side strict schema enforcement and local validation because they protect different boundaries.

**Prerequisite:** strict structured-output support for the deployment and schema keywords used.

### Reasoning effort

```bash
python responses_example.py --example reasoning --reasoning-effort high
```

Supported SDK values are `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, and `max`. The selected value is sent unchanged as `reasoning.effort`.

**Success signal:** a normal completed response. The example does not reinterpret the deployment alias or substitute a different effort.

**Adaptation:** expose only values appropriate to your application's latency and cost budget, but allow unsupported values to fail visibly for the selected deployment.

**Prerequisite:** reasoning-effort support and support for the chosen value.

### Prompt caching

```bash
python responses_example.py --example prompt-caching
python responses_example.py --example prompt-caching --cache-key my-stable-key
```

**Request shape:** two requests use the same `prompt_cache_key`, the same developer-message prefix, `prompt_cache_options={"mode":"explicit","ttl":"30m"}`, and an explicit `prompt_cache_breakpoint` at the end of the stable prefix. Only the later user content changes.

**Telemetry:** both requests print `cached_tokens` and `cache_write_tokens`.

**Success signal:** the second response must report `usage.input_tokens_details.cached_tokens > 0`. Positive `cache_write_tokens` with zero cached reads is not a cache hit.

**Adaptation:** put stable, reusable content first; version the key when that content changes; and keep user-specific or volatile content after the breakpoint. Treat cache retention as service-managed and do not use the cache as durable storage.

**Prerequisite:** explicit prompt-cache options, breakpoints, and usage telemetry. Cache population and hits can also depend on deployment-specific token thresholds and service conditions.

### Local base64 image input

```bash
python responses_example.py --example image-input --image path/to/local-image.png
```

**Request shape:** a user message containing `input_text` and `input_image`; the local bytes are encoded as a `data:image/...;base64,...` URL.

**Success signal:** a completed response with text. Missing, empty, or non-image paths fail before a request is sent.

**Adaptation:** validate file size, media type, and content according to your trust boundary before encoding. Base64 increases request size and transmits the image to the model service.

**Prerequisite:** image-input support and a supported image media type/size.

### Stored conversation state

```bash
python responses_example.py --example conversation-state
```

**Request shape:** the first request sets `store=True`; the second also sets `store=True` and supplies the first response's ID as `previous_response_id`.

**Success signal:** both requests complete. The example does not silently fall back to replaying client-managed history.

**State implications:** response data is retained by the service according to its storage and retention behavior. Review organizational data-handling requirements before enabling it.

**Adaptation:** if server-side storage is not appropriate, design a separate client-managed-history flow explicitly. That is a different state model and should not be hidden behind automatic fallback.

**Prerequisite:** stored Responses and `previous_response_id` support.

## Offline validation

The tests use the actual OpenAI SDK with `httpx2.MockTransport`; an autouse fixture blocks socket connections. They assert serialized request bodies and observable success conditions rather than accepting HTTP 200 alone.

```bash
pip install -r requirements-dev.txt
python -m pytest
ruff check .
mypy
```
