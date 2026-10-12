// Microsoft Foundry Responses API quickstart using the standard OpenAI SDK.
// Makes one request to the deployment alias in AZURE_MODEL_DEPLOYMENT_NAME.

using System.ClientModel;
using Azure.Identity;
using OpenAI;
using OpenAI.Responses;

var endpoint = Environment.GetEnvironmentVariable("AZURE_AI_PROJECT_ENDPOINT");
if (string.IsNullOrEmpty(endpoint))
{
    Console.Error.WriteLine("Error: AZURE_AI_PROJECT_ENDPOINT must be set.");
    return 1;
}

var credential = new DefaultAzureCredential();
var token = await credential.GetTokenAsync(
    new Azure.Core.TokenRequestContext(["https://ai.azure.com/.default"])
);

var baseUrl = endpoint.TrimEnd('/') + "/openai/v1";
var client = new OpenAIClient(
    new ApiKeyCredential(token.Token),
    new OpenAIClientOptions { Endpoint = new Uri(baseUrl) });

var model = Environment.GetEnvironmentVariable("AZURE_MODEL_DEPLOYMENT_NAME") ?? "DeepSeek-R1-0528";
var responsesClient = client.GetResponsesClient(model);
var result = await responsesClient.CreateResponseAsync(new CreateResponseOptions(
    [ResponseItem.CreateUserMessageItem("Explain quantum computing in three sentences.")])
    { MaxOutputTokenCount = 500 }
);

Console.WriteLine(result.Value.GetOutputText());
Console.WriteLine($"\nStatus: {result.Value.Status}");
Console.WriteLine($"Model deployment: {model}");

return 0;
