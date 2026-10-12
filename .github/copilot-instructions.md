# Copilot Instructions — Foundry Models Starter Kit

## Architecture

This is an **Azure Developer CLI (azd) template** that deploys a Microsoft Foundry account with one primary model (DeepSeek-R1-0528 by default) and provides working examples in **Python, TypeScript, C#, Java, and Go**. Secondary and third deployments are opt-in.

- **Infra layer** (`infra/`): Subscription-scoped Bicep. [main.bicep](../infra/main.bicep) creates the resource group and delegates to [foundry.bicep](../infra/foundry.bicep), which provisions `Microsoft.CognitiveServices/accounts` (kind `AIServices`), a project sub-resource, and model deployments (primary + optional secondary + optional third).
- **App layer** (`src/`): Each language has a one-request **Responses API** quickstart using its standard **OpenAI SDK** (not Azure-specific SDK wrappers). Python is the canonical feature implementation with an explicit `--example` CLI and small local modules. There is no web app, API server, or deployment target.
- **Glue**: [azure.yaml](../azure.yaml) wires azd to the Bicep infra. Environment variables flow from Bicep outputs → azd env → app code via `os.environ` (or equivalent).

## Key Conventions

### The universal pattern (all languages)

Every example follows the same three steps:

1. **Get an EntraID token** via `DefaultAzureCredential` scoped to `https://ai.azure.com/.default`
2. **Create a standard OpenAI client** with `base_url` = project endpoint + `/openai/v1`, passing the token as `api_key`
3. **Call the Responses API** — no `api-version` query parameter needed

Do **not** use `azure-ai-projects` (`AIProjectClient`), `openai.AzureOpenAI`, `Azure.AI.OpenAI`, or any Azure-specific OpenAI wrapper. Use each language's standard `openai` library only.

### Python SDK pattern

```python
import os
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import OpenAI

credential = DefaultAzureCredential()
endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
client = OpenAI(
    base_url=endpoint.rstrip("/") + "/openai/v1",
    api_key=get_bearer_token_provider(credential, "https://ai.azure.com/.default"),
)
model = os.environ.get("AZURE_MODEL_DEPLOYMENT_NAME", "DeepSeek-R1-0528")
response = client.responses.create(model=model, input="...", max_output_tokens=500)
```

### TypeScript SDK pattern

```typescript
import OpenAI from "openai";
import { DefaultAzureCredential } from "@azure/identity";

const credential = new DefaultAzureCredential();
const token = await credential.getToken("https://ai.azure.com/.default");

const client = new OpenAI({
  baseURL: process.env.AZURE_AI_PROJECT_ENDPOINT!.replace(/\/+$/, "") + "/openai/v1",
  apiKey: token.token,
});
const model = process.env.AZURE_MODEL_DEPLOYMENT_NAME ?? "DeepSeek-R1-0528";
const response = await client.responses.create({ model, input: "...", max_output_tokens: 500 });
```

### C# SDK pattern

```csharp
var credential = new DefaultAzureCredential();
var token = credential.GetToken(new TokenRequestContext(["https://ai.azure.com/.default"]));

var client = new OpenAIClient(
    new ApiKeyCredential(token.Token),
    new OpenAIClientOptions { Endpoint = new Uri(endpoint.TrimEnd('/') + "/openai/v1") });
var model = Environment.GetEnvironmentVariable("AZURE_MODEL_DEPLOYMENT_NAME") ?? "DeepSeek-R1-0528";
var responsesClient = client.GetResponsesClient(model);
var response = await responsesClient.CreateResponseAsync(new CreateResponseOptions(
    [ResponseItem.CreateUserMessageItem("...")])
    { MaxOutputTokenCount = 500 }
);
Console.WriteLine(response.Value.GetOutputText());
```

### Java SDK pattern

The Java OpenAI SDK sends its own internal API version header, which conflicts with the `api-version` query parameter on the `/openai` path. Use `/openai/v1` instead — no `api-version` query parameter is needed.

```java
DefaultAzureCredential credential = new DefaultAzureCredentialBuilder().build();
AccessToken token = credential.getTokenSync(new TokenRequestContext().addScopes("https://ai.azure.com/.default"));

OpenAIClient client = OpenAIOkHttpClient.builder()
    .baseUrl(endpoint.replaceAll("/+$", "") + "/openai/v1")
    .apiKey(token.getToken())
    .build();
```

Note: The Java SDK's `Response` object does not have an `outputText()` convenience method. Iterate `response.output()` items and cast to `ResponseOutputMessage` → `ContentOutputText` to extract text.

### Go SDK pattern

```go
credential, _ := azidentity.NewDefaultAzureCredential(nil)
token, _ := credential.GetToken(context.Background(), policy.TokenRequestOptions{
    Scopes: []string{"https://ai.azure.com/.default"},
})

client := openai.NewClient(
    option.WithBaseURL(strings.TrimRight(endpoint, "/") + "/openai/v1"),
    option.WithAPIKey(token.Token),
)
```

### Authentication
Use **keyless** via `DefaultAzureCredential` (EntraID). Users need the `Cognitive Services User` role on the Microsoft Foundry account. Token audience is always `https://ai.azure.com/.default`.

### Environment variables
Set from `azd env get-values` after provisioning:
- `AZURE_AI_PROJECT_ENDPOINT` — the project endpoint; used as `base_url` with `/openai/v1` suffix
- `AZURE_MODEL_DEPLOYMENT_NAME` — primary model deployment alias (default: `DeepSeek-R1-0528`); read by every quickstart
- `AZURE_MODEL_2_DEPLOYMENT_NAME` — optional second deployment alias; empty when skipped
- `AZURE_MODEL_3_DEPLOYMENT_NAME` — optional third deployment alias; empty when skipped

Normal sample code reads only `AZURE_MODEL_DEPLOYMENT_NAME`, falling back to `DeepSeek-R1-0528`. Treat deployment aliases as opaque: do not infer providers or capabilities from their values.

### Bicep conventions
- Target scope is `subscription` in `main.bicep`; resource-group-scoped resources go in `foundry.bicep` module.
- API version: `2025-06-01` for all `Microsoft.CognitiveServices` resources.
- Resource naming uses `uniqueString(subscription().id, environmentName, location)` for uniqueness.
- **Model deployments are in Bicep** — defined in `foundry.bicep` as `Microsoft.CognitiveServices/accounts/deployments` resources with `@2025-06-01` API version. Primary deployment is unconditional; secondary and third use `if (!empty(modelNName))` conditional.
- The second and third model deployments are optional and empty by default. Set `AZURE_MODEL_2_NAME` or `AZURE_MODEL_3_NAME` to opt in.

## Developer Workflow

```powershell
# Deploy / redeploy infrastructure
azd up

# Change model before deploying
azd env set AZURE_MODEL_NAME "gpt-4.1-mini"
azd env set AZURE_MODEL_FORMAT "OpenAI"
azd env set AZURE_MODEL_VERSION "2025-04-14"
azd up

# Set environment variables
$env:AZURE_AI_PROJECT_ENDPOINT = azd env get-value 'AZURE_AI_PROJECT_ENDPOINT'

# Run any example
cd src/python   && pip install -r requirements.txt && python responses_example.py
# Explicit Python feature example:
python responses_example.py --example structured-output
cd src/typescript && npm install && npx tsx responses_example.ts
cd src/csharp   && dotnet run
cd src/java     && mvn -q compile exec:java
cd src/go       && go run .

# Tear down all resources
azd down --purge
```

## When Adding New Examples

### Any language
- Place new scripts in `src/<language>/`.
- Follow the universal pattern: get EntraID token (audience `https://ai.azure.com/.default`), create standard OpenAI client with `base_url` = project endpoint + `/openai/v1`, call the Responses API.
- Use the `responses` API, not `chat.completions`.
- Do not add Azure-specific OpenAI wrappers (`azure-ai-projects`, `AzureOpenAI`, `Azure.AI.OpenAI`, etc.).
- Keep non-Python quickstarts self-contained. Python features share `responses_common.py` and `responses_weather.py`.
- The default invocation must call only `AZURE_MODEL_DEPLOYMENT_NAME` once. Advanced Python examples may make documented follow-up requests only when explicitly selected.
- Do not inspect deployment aliases, remove unsupported parameters, switch APIs, or retry with a weaker request.

### Language-specific notes
- **Python**: Runtime dependencies go in `src/python/requirements.txt`; offline test/lint/type dependencies go in `requirements-dev.txt`. Use Pydantic for shared tool/structured-output validation.
- **TypeScript**: Dependencies go in `src/typescript/package.json`. Only `openai` + `@azure/identity`.
- **C#**: NuGet packages in `src/csharp/*.csproj`. Use `OpenAI` (≥2.8.0) + `Azure.Identity`. Suppress `OPENAI001` warning for experimental Responses API. Key types: `ResponsesClient` (via `client.GetResponsesClient(model)`), `CreateResponseOptions` (with `InputItems` for input and `MaxOutputTokenCount`), `ResponseResult` (with `GetOutputText()`).
- **Java**: Maven dependencies in `src/java/pom.xml`. Use `com.openai:openai-java` + `com.azure:azure-identity`. Use `/openai/v1` base URL (no `api-version` needed — the SDK manages versioning internally). Must manually iterate output items (no `outputText()` convenience).
- **Go**: Go modules in `src/go/go.mod`. Use `github.com/openai/openai-go` + `github.com/Azure/azure-sdk-for-go/sdk/azidentity`. Token options from `azcore/policy`, not `azidentity`.

## When Modifying Infrastructure

- Add new Foundry-related resources to `foundry.bicep`, not `main.bicep`.
- Expose any values needed by app code as `output` in both `foundry.bicep` and `main.bicep`, then map them in `main.parameters.json` so azd captures them.
- Use `azd env set VAR=default` syntax in `main.parameters.json` for new configurable parameters.
