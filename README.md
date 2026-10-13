<!--
---
page_type: sample
languages:
- python
- typescript
- go
- csharp
- java
products:
- azure-openai
- azure
- microsoft-foundry
urlFragment: ai-model-start
name: The AI Model Starter Kit
description: Call one selected Microsoft Foundry model deployment using standard OpenAI SDKs, the Responses API, and EntraID keyless authentication. Includes quickstarts in Python, TypeScript, C#, Java, and Go plus explicit Python feature examples.
---
-->
# The AI Model Starter Kit

The fastest way to call a selected Microsoft Foundry model deployment from your application.

Use a **standard OpenAI SDK**, the **Responses API**, and **EntraID keyless authentication** — no API keys or secrets to manage. The normal path deploys one model and every language quickstart makes one request to its deployment alias.

Includes working quickstarts in **Python, TypeScript, C#, Java, and Go**. Python also includes explicitly selected examples for streaming, local function calls, structured output, reasoning, prompt caching, image input, and stored conversation state.

![Architecture: Standard OpenAI SDKs in 5 languages connect to any Foundry model via the GA Responses API with keyless auth](images/ai-model-start-arch.png)

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Next Steps](#next-steps)
- [What This Template Includes](#what-this-template-includes)
- [What You Get](#what-you-get)
- [Template Structure](#template-structure)
- [Language-specific SDK dependencies](#language-specific-sdk-dependencies)
- [Configuration](#configuration)
- [Outputs](#outputs)
- [Common Commands](#common-commands)
- [Alternative Regions](#alternative-regions)
- [How Do I Find Which Foundry Models Support Responses and Where?](#how-do-i-find-which-foundry-models-support-responses-and-where)
- [Known Issues](#known-issues)
- [Troubleshooting](#troubleshooting)
- [Why This Template?](#why-this-template)
- [Foundry Models with Responses API Support](#foundry-models-with-responses-api-support)

## Prerequisites

- [Azure Subscription](https://azure.microsoft.com/pricing/purchase-options/azure-account)
- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli)
- One or more of: Python 3.10+, Node.js 18+, .NET 8+, Java 21+, Go 1.23+

## Quick Start

```bash
# 1. Login to Azure
az login
azd auth login

# 2. Deploy one model (DeepSeek-V3.2 by default) to Microsoft Foundry
azd up
```

That's it! You now have a Microsoft Foundry account, project, and one model deployment ready to use.

## Next Steps

### Set up your environment

After `azd up`, the project root `.env` is updated with the Foundry project endpoint and primary deployment alias. The hook fails instead of writing incomplete configuration when either output is blank, preserves unrelated lines, removes duplicate managed keys, and avoids rewriting an unchanged file. Role assignments are disabled by default, so the deployment reuses permissions already granted to the deploying user and project identity. Source the `.env` file before running examples:

**Bash / macOS / Linux**
```bash
set -a; source .env; set +a
```

**PowerShell / Windows**
```powershell
Get-Content .env | ForEach-Object { if ($_ -match '^([^#=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2]) } }
```

> **Note:** If an authorized administrator opts in to role creation, role assignments can take up to 5 minutes to propagate.

### Run an example

Each language quickstart reads `AZURE_MODEL_DEPLOYMENT_NAME` and makes exactly one request. Deployment aliases are passed through unchanged; the examples do not infer a provider or model family from the alias.

**Python**
```bash
cd src/python
pip install -r requirements.txt
python responses_example.py
```

The default command runs only the basic example. Select a Python feature explicitly:

```bash
python responses_example.py --example streaming
python responses_example.py --example function-call
python responses_example.py --example parallel-functions --max-concurrency 4
python responses_example.py --example structured-output
python responses_example.py --example reasoning --reasoning-effort high
python responses_example.py --example prompt-caching
python responses_example.py --example image-input --image path/to/local-image.png
python responses_example.py --example conversation-state

# Call another deployment alias without changing the environment
python responses_example.py --model my-deployment-alias
```

Some explicitly selected features require a follow-up request by design: function calling submits local tool output, prompt caching checks a second request for a cache hit, and conversation state sends a second turn. See [Responses API feature guidance](docs/responses-api-features.md) for exact request shapes and success signals.

The Python CLI defaults `--max-output-tokens` to `4096`. This limit includes visible output and reasoning tokens; an explicit lower value is preserved, and incomplete responses remain visible errors.

**TypeScript**
```bash
cd src/typescript
npm install
npx tsx responses_example.ts
```

**C#**
```bash
cd src/csharp
dotnet run
```

**Java** (requires Maven)
```bash
cd src/java
mvn -q compile exec:java
```

**Go**
```bash
cd src/go
go run .
```

### The pattern (every language)

All five examples follow the same pattern:

1. **Get an EntraID token** via `DefaultAzureCredential` (scoped to `https://ai.azure.com/.default`)
2. **Create a standard OpenAI client** with `base_url` = project endpoint + `/openai/v1`
3. **Call the Responses API** once with the selected deployment alias

**Why the standard OpenAI SDK?**

The Foundry endpoint is OpenAI-compatible. By appending `/openai/v1`, you can use the standard `openai` library in any language — no `azure-ai-projects`, `AzureOpenAI`, or `Azure.AI.OpenAI` wrapper needed. No `api-version` query parameter is required.

> **Feature compatibility:** A common SDK and API shape does not mean every deployment supports every optional Responses feature. Unsupported parameters remain visible API errors; the examples do not remove parameters, switch APIs, or retry with a weaker request.

### Python code sample

```python
import os
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import OpenAI

credential = DefaultAzureCredential()
endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
model = os.environ.get("AZURE_MODEL_DEPLOYMENT_NAME", "DeepSeek-V3.2")
client = OpenAI(
    base_url=endpoint.rstrip("/") + "/openai/v1",
    api_key=get_bearer_token_provider(credential, "https://ai.azure.com/.default"),
    max_retries=0,
)

response = client.responses.create(
    model=model,
    input="Explain quantum computing in simple terms",
    max_output_tokens=500,
)
print(response.output_text)
```

## What This Template Includes

- **Core Infrastructure**: Microsoft Foundry account + project with one primary model deployment
- **Optional Deployments**: Secondary and third deployment slots remain available but are empty by default
- **Optimal Configuration**: GlobalStandard SKU, flexible region and model selection
- **Secure Authentication**: EntraID (keyless) via `DefaultAzureCredential` — no API keys or secrets to manage
- **Multi-language quickstarts**: Python, TypeScript, C#, Java, and Go — one request each
- **Python feature examples**: Explicitly selected Responses API examples with offline tests
- **Complete Documentation**: Setup guide with troubleshooting tips

## What You Get

- **DeepSeek-V3.2** (default) — Non-OpenAI model for efficient reasoning and agentic workloads
- **Flexible model deployment** — Deploy any Foundry model (OpenAI, DeepSeek, Meta, xAI, Microsoft, and more)
- **Microsoft Foundry project** — Full project workspace for your development team
- **Standard OpenAI SDKs** — Use each language's `openai` library directly, no Azure-specific wrappers
- **GA Responses API** — Production-ready API, cleaner than Chat Completions
- **Keyless authentication** — Secure EntraID auth, no API keys to manage
- **Unique resource naming** — No conflicts with existing resources

## Template Structure

```
├── azure.yaml                 # azd configuration
├── infra/
│   ├── main.bicep             # Main deployment template (subscription-scoped)
│   ├── main.parameters.json   # Deployment parameters
│   └── foundry.bicep          # Microsoft Foundry account, project, and model deployments
├── scripts/
│   ├── list_models_with_responses_api_support.py  # Utility: list models supporting the Responses API
│   └── requirements.txt       # Dependencies for scripts (control plane)
├── src/
│   ├── python/
│   │   ├── responses_example.py         # Python CLI (basic by default)
│   │   ├── responses_common.py          # Auth, client, completion, and usage helpers
│   │   ├── responses_features.py        # Explicit Responses feature examples
│   │   ├── responses_weather.py         # Validated local tool fixture
│   │   ├── tests/                       # Offline SDK + mock transport tests
│   │   ├── requirements.txt
│   │   └── requirements-dev.txt
│   ├── typescript/
│   │   ├── responses_example.ts         # TypeScript example
│   │   ├── package.json
│   │   └── tsconfig.json
│   ├── csharp/
│   │   ├── Program.cs                   # C# example
│   │   └── FoundryModelsExample.csproj
│   ├── java/
│   │   ├── src/main/java/ResponsesExample.java  # Java example
│   │   └── pom.xml
│   └── go/
│       ├── main.go                      # Go example
│       └── go.mod
├── docs/
│   └── responses-api-features.md
└── README.md
```

## Language-specific SDK dependencies

| Language | OpenAI SDK | Azure Identity |
|---|---|---|
| Python | `openai` | `azure-identity` |
| TypeScript | `openai` | `@azure/identity` |
| C# | `OpenAI` (NuGet) | `Azure.Identity` |
| Java | `com.openai:openai-java` | `com.azure:azure-identity` |
| Go | `github.com/openai/openai-go` | `github.com/Azure/azure-sdk-for-go/sdk/azidentity` |

The Python feature examples also use Pydantic for strict schemas/local validation and `python-dotenv` for local environment loading.

## Configuration

The primary model deployment is defined in Bicep and created during `azd up`. Secondary and third deployments are opt-in. Configure deployment tuples via `azd env set` before running `azd up`:

| Variable | Default | Description |
|---|---|---|
| `AZURE_MODEL_NAME` | `DeepSeek-V3.2` | Primary model to deploy |
| `AZURE_MODEL_FORMAT` | `DeepSeek` | Primary model format (`DeepSeek`, `Microsoft`, `OpenAI`, etc.) |
| `AZURE_MODEL_VERSION` | `1` | Primary model version |
| `AZURE_MODEL_DEPLOYMENT_NAME` | Same as model name | Custom deployment name for primary model |
| `AZURE_MODEL_SKU_NAME` | `GlobalStandard` | Primary model SKU tier |
| `AZURE_MODEL_SKU_CAPACITY` | `10` | Primary model capacity (tokens-per-minute in thousands) |
| `AZURE_MODEL_2_NAME` | Empty | Second model to deploy (empty string skips it) |
| `AZURE_MODEL_2_FORMAT` | `OpenAI` | Second model format |
| `AZURE_MODEL_2_VERSION` | `2025-04-14` | Second model version |
| `AZURE_MODEL_2_DEPLOYMENT_NAME` | Same as model name | Custom deployment name for second model |
| `AZURE_MODEL_2_SKU_NAME` | `GlobalStandard` | Second model SKU tier |
| `AZURE_MODEL_2_SKU_CAPACITY` | `10` | Second model capacity |
| `AZURE_MODEL_3_NAME` | Empty | Third model to deploy (empty string skips it) |
| `AZURE_MODEL_3_FORMAT` | `OpenAI-OSS` | Third model format |
| `AZURE_MODEL_3_VERSION` | `1` | Third model version |
| `AZURE_MODEL_3_DEPLOYMENT_NAME` | Same as model name | Custom deployment name for third model |
| `AZURE_MODEL_3_SKU_NAME` | `GlobalStandard` | Third model SKU tier |
| `AZURE_MODEL_3_SKU_CAPACITY` | `10` | Third model capacity |
| `AZURE_CREATE_ROLE_ASSIGNMENTS` | `false` | Create account-scoped Foundry User assignments for the deploying user and project identity. Requires `Microsoft.Authorization/roleAssignments/write`. |

### Optional: create Foundry role assignments

By default, `azd up` creates no role assignments and relies on existing inherited access. If the deploying user and project identity need account-scoped access, an authorized administrator can opt in:

```bash
azd env set AZURE_CREATE_ROLE_ASSIGNMENTS true
azd up
```

This creates the **Foundry User** role for the deploying user and the Foundry project's system-assigned identity at the new Foundry account scope. The caller running `azd up` must be allowed to perform `Microsoft.Authorization/roleAssignments/write`.

### Example: DeepSeek-V3.2 (Default)

```bash
azd up
```

### Example: gpt-4.1-mini (OpenAI)

```bash
azd env set AZURE_MODEL_NAME "gpt-4.1-mini"
azd env set AZURE_MODEL_FORMAT "OpenAI"
azd env set AZURE_MODEL_VERSION "2025-04-14"
azd up
```

### Opt in to a secondary deployment

```bash
azd env set AZURE_MODEL_2_NAME "gpt-4.1-mini"
azd env set AZURE_MODEL_2_FORMAT "OpenAI"
azd env set AZURE_MODEL_2_VERSION "2025-04-14"
azd up
```

### Example: MAI-DS-R1

```bash
azd env set AZURE_MODEL_NAME "MAI-DS-R1"
azd env set AZURE_MODEL_FORMAT "Microsoft"
azd up
```

## Outputs

After `azd up`, available via `azd env get-values`:

| Output | Description |
|---|---|
| `AZURE_RESOURCE_GROUP` | Resource group name |
| `AZURE_AI_FOUNDRY_NAME` | Microsoft Foundry account name |
| `AZURE_AI_PROJECT_NAME` | Foundry project name |
| `AZURE_AI_PROJECT_ENDPOINT` | Project endpoint URL (use as `base_url` with `/openai/v1` suffix) |
| `AZURE_MODEL_DEPLOYMENT_NAME` | Primary model deployment name |
| `AZURE_MODEL_2_DEPLOYMENT_NAME` | Optional second deployment name (empty when skipped) |
| `AZURE_MODEL_3_DEPLOYMENT_NAME` | Optional third deployment name (empty when skipped) |

## Common Commands

```bash
# Redeploy with changes
azd up

# Preview what would be deployed
azd provision --preview

# Debug deployment issues
azd up --debug

# Clean up everything
azd down --purge
```

## Alternative Regions

```bash
azd env set AZURE_LOCATION eastus2
azd up
```

## How Do I Find Which Foundry Models Support Responses and Where?

The `scripts/list_models_with_responses_api_support.py` utility queries the ARM control plane to discover which models support the Responses API in your subscription, along with their available regions. See the [full list of supported models](#foundry-models-with-responses-api-support) at the bottom of this page.

```bash
cd scripts
pip install -r requirements.txt

# List all models with Responses API support (OpenAI + non-OpenAI)
python list_models_with_responses_api_support.py

# Show per-region breakdown for models not available everywhere
python list_models_with_responses_api_support.py --locations

# List only non-OpenAI models (DeepSeek, Meta, xAI, etc.)
python list_models_with_responses_api_support.py --non-openai

# Show active model deployments across all Foundry accounts
python list_models_with_responses_api_support.py --deployments

# Combine flags
python list_models_with_responses_api_support.py --non-openai --locations
```

> **Note:** The ARM control plane tags OpenAI-format models with `capabilities.responses`. For non-OpenAI models, `capabilities.agentsV2` is used as a proxy — models with this capability support the Responses API at runtime. The default run combines both into a single unified list.

## Known Issues

| Issue | Summary | Workaround |
|---|---|---|
| ~~[ARM validation rejects non-OpenAI models](https://github.com/Azure-Samples/ai-model-start/issues/4)~~ | ~~Bicep/ARM template deployment previously failed for non-OpenAI model formats.~~ | **Resolved** — Model deployments now work natively in Bicep with API version `2025-06-01`. |
| ~~[Preview API version required](https://github.com/Azure-Samples/ai-model-start/issues/2)~~ | ~~`/openai/v1` endpoint previously only accepted `api-version=2025-11-15-preview`.~~ | **Resolved** — The `/openai/v1` path is now GA and doesn't require an `api-version` parameter at all. |
| ~~[Java SDK `putQueryParam` bug](https://github.com/Azure-Samples/ai-model-start/issues/3)~~ | ~~`openai-java` `putQueryParam("api-version", ...)` silently drops the query parameter, causing `400: API version not supported` errors with EntraID auth.~~ | **Resolved** — All examples now use `/openai/v1` base URL which doesn't need `api-version`. |
| [API key endpoint limitation](https://github.com/Azure-Samples/ai-model-start/issues/5) | The account-level API key endpoint (`/openai/v1`) does not support the Responses API for non-OpenAI models. | This template uses **EntraID authentication** with the project endpoint, which supports all models. |
| [o4-mini reasoning summary text](https://github.com/Azure-Samples/ai-model-start/issues/13) | Setting `reasoning={"summary":"auto"\|"concise"\|"detailed"}` returns HTTP 400 with an upstream OpenAI organization-verification error. Without that parameter, the `reasoning` item is emitted but `summary[].text` is empty. | Use `reasoning={"effort":"low"\|"medium"\|"high"}` to control reasoning compute — this is accepted without verification and `reasoning_tokens` reflects the chosen effort. Recovering human-readable summary text requires OpenAI org verification, which Foundry customers may not have access to. |

## Troubleshooting

**401 / 403 "Permission denied"** — Role assignments are off by default. Confirm that the caller already has the **Foundry User** role at the Foundry account scope, or ask an authorized administrator to opt in before provisioning:
```bash
azd env set AZURE_CREATE_ROLE_ASSIGNMENTS true
azd up
```
The opt-in path assigns Foundry User to both the deploying user and project identity and requires `Microsoft.Authorization/roleAssignments/write`. Allow time for newly created assignments to propagate before invoking a model.

**"DeploymentModelNotSupported" during `azd up`** — Ensure the model format matches the model name (e.g., `DeepSeek` format for DeepSeek models, `OpenAI` for GPT models). Check available models with `az cognitiveservices model list -l <location> --query "[?model.format=='YourFormat']"`. See `scripts/list_models_with_responses_api_support.py` for discovery.

**"Quota exceeded"** — Check your subscription's quota for the selected model in the target region. Try a different region or model.

**429 Rate limited** — Increase `AZURE_MODEL_SKU_CAPACITY` or try a different model with more available capacity.

**"api-version is required"** / **"Missing required query string parameter 'api-version'"** — You're using the `/openai` path without passing `api-version`. Switch to `/openai/v1` instead, which doesn't require an `api-version` parameter. All examples use this approach.

**"UnsupportedApiVersion"** — The SDK or your code is sending an api-version that isn't supported. Switch to `/openai/v1` which doesn't require an `api-version` parameter.

**Java `400: API version not supported`** — This is a [known SDK bug](https://github.com/Azure-Samples/ai-model-start/issues/3) where `putQueryParam` doesn't work correctly. All examples (including Java) now use `/openai/v1` which avoids this issue entirely.

**"FlagMustBeSetForRestore" during `azd up`** — A previously deleted Foundry account with the same name still exists in soft-deleted state. Purge it first:
```bash
az cognitiveservices account purge --location <location> --resource-group <rg-name> --name <foundry-name>
```
To avoid this, always use `azd down --purge` instead of `azd down` when tearing down resources.

Need debug info? Run `azd up --debug` for detailed logs.

## Why This Template?

- **Minimal setup** — 2 commands instead of 20+
- **Any Foundry model** — Access OpenAI, DeepSeek, Meta, xAI, Microsoft, and more
- **Any language** — Python, TypeScript, C#, Java, and Go examples included
- **GA Responses API** — Uses the production-ready Responses API, not legacy Chat Completions
- **Standard SDKs** — Uses each language's OpenAI SDK directly, no Azure-specific wrappers
- **Production-ready** — GlobalStandard SKU, EntraID auth, proper naming
- **Secure by default** — Keyless EntraID authentication with Azure Identity
- **Easy cleanup** — Remove everything with `azd down --purge`

## Foundry Models with Responses API Support

All models currently available on Microsoft Foundry that support the [Responses API](https://platform.openai.com/docs/api-reference/responses), queried via the ARM control plane. Last updated: **February 2026**.

### OpenAI

| Model | Version(s) | Availability |
|---|---|---|
| codex-mini | 2025-05-16 | eastus2, swedencentral |
| gpt-4 | 0613 | All except southeastasia |
| gpt-4-32k | 0613 | 20/23 regions |
| gpt-4.1 | 2025-04-14 | All regions |
| gpt-4.1-mini | 2025-04-14 | All regions |
| gpt-4.1-nano | 2025-04-14 | All regions |
| gpt-4o | 2024-05-13, 2024-08-06, 2024-11-20 | All regions |
| gpt-4o-mini | 2024-07-18 | All regions |
| gpt-4o-mini-realtime-preview | 2024-12-17 | eastus2, swedencentral |
| gpt-5-chat | 2025-08-07, 2025-10-03 | eastus2, swedencentral |
| gpt-5-mini | 2025-08-07 | All regions |
| gpt-5-nano | 2025-08-07 | All except canadacentral |
| gpt-5.1-chat | 2025-11-13 | 8/23 regions |
| gpt-5.1-codex-mini | 2025-11-13 | 8/23 regions |
| gpt-5.2-chat | 2025-12-11 | eastus2, swedencentral |
| o1 | 2024-12-17 | All regions |
| o3-deep-research | 2025-06-26 | norwayeast, westus |
| o3-mini | 2025-01-31 | All regions |
| o4-mini | 2025-04-16 | All regions |

### Anthropic

| Model | Version(s) | Availability |
|---|---|---|
| claude-haiku-4-5 | 20251001 | eastus2, swedencentral |
| claude-opus-4-1 | 20250805 | eastus2, swedencentral |
| claude-opus-4-5 | 20251101 | eastus2, swedencentral |
| claude-opus-4-6 | 1 | eastus2, swedencentral |
| claude-sonnet-4-5 | 20250929 | eastus2, swedencentral |
| claude-sonnet-4-6 | 1 | eastus2, swedencentral |

### DeepSeek

| Model | Version(s) | Availability |
|---|---|---|
| DeepSeek-V3-0324 | 1 | All except southeastasia |
| DeepSeek-V3.1 | 1 | All except southeastasia |
| DeepSeek-V3.2 | 1 | All except southeastasia |
| DeepSeek-V3.2-Speciale | 1 | All except southeastasia |

### Meta

| Model | Version(s) | Availability |
|---|---|---|
| Llama-3.3-70B-Instruct | 1, 2, 3, 4, 5 | All except southeastasia |
| Llama-4-Maverick-17B-128E-Instruct-FP8 | 1 | All except southeastasia |

### Microsoft

| Model | Version(s) | Availability |
|---|---|---|
| MAI-DS-R1 | 1 | All except southeastasia |

### OpenAI-OSS

| Model | Version(s) | Availability |
|---|---|---|
| gpt-oss-120b | 1 | All except southeastasia |

### xAI

| Model | Version(s) | Availability |
|---|---|---|
| grok-3 | 1 | All except southeastasia |
| grok-3-mini | 1 | All except southeastasia |
| grok-4-fast-non-reasoning | 1 | All except southeastasia |
| grok-4-fast-reasoning | 1 | All except southeastasia |

**Region availability notes:**
- **20/23 regions** — `gpt-4-32k` is not available in `japaneast`, `southeastasia`, `westeurope`
- **8/23 regions** — `gpt-5.1-chat` and `gpt-5.1-codex-mini` are available in `australiaeast`, `canadaeast`, `eastus2`, `japaneast`, `koreacentral`, `swedencentral`, `switzerlandnorth`, `uksouth`

> Run `python scripts/list_models_with_responses_api_support.py` for the latest data from your own subscription.

---

Powered by [Azure Developer CLI](https://aka.ms/azd) | Deploy any model on [Microsoft Foundry](https://ai.azure.com)
