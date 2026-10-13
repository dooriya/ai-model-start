/**
 * Microsoft Foundry Responses API quickstart using the standard OpenAI SDK.
 * Makes one request to the deployment alias in AZURE_MODEL_DEPLOYMENT_NAME.
 */

import com.azure.core.credential.TokenRequestContext;
import com.azure.identity.DefaultAzureCredentialBuilder;
import com.openai.client.OpenAIClient;
import com.openai.client.okhttp.OpenAIOkHttpClient;
import com.openai.models.responses.Response;
import com.openai.models.responses.ResponseCreateParams;

public class ResponsesExample {

    /** Return the final assistant message text from a Responses API result. */
    static String getOutputText(Response response) {
        var sb = new StringBuilder();
        response.output().stream()
                .flatMap(item -> item.message().stream())
                .flatMap(message -> message.content().stream())
                .flatMap(content -> content.outputText().stream())
                .forEach(outputText -> sb.append(outputText.text()));
        return sb.toString();
    }

    public static void main(String[] args) {
        String endpoint = System.getenv("AZURE_AI_PROJECT_ENDPOINT");
        if (endpoint == null || endpoint.isEmpty()) {
            System.err.println("Error: AZURE_AI_PROJECT_ENDPOINT must be set.");
            System.exit(1);
        }

        // Get EntraID token for keyless auth
        var credential = new DefaultAzureCredentialBuilder().build();
        var context = new TokenRequestContext().addScopes("https://ai.azure.com/.default");
        String token = credential.getToken(context).block().getToken();

        // Standard OpenAI client — no Azure wrapper
        // Java SDK uses /openai/v1 path (no api-version needed; SDK manages versioning internally)
        String baseUrl = endpoint.replaceAll("/+$", "") + "/openai/v1";
        OpenAIClient client = OpenAIOkHttpClient.builder()
                .baseUrl(baseUrl)
                .apiKey(token)
                .build();

        String model = System.getenv().getOrDefault(
                "AZURE_MODEL_DEPLOYMENT_NAME",
                "DeepSeek-V3.2"
        );
        var response = client.responses().create(
                ResponseCreateParams.builder()
                        .model(model)
                        .input("Explain quantum computing in three sentences.")
                        .maxOutputTokens(500)
                        .build()
        );

        System.out.println(getOutputText(response));
        System.out.printf("%nStatus: %s%n", response.status());
        System.out.printf("Model deployment: %s%n", model);
    }
}
