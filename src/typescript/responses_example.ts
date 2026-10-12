/**
 * Microsoft Foundry Responses API quickstart using the standard OpenAI SDK.
 * Makes one request to the deployment alias in AZURE_MODEL_DEPLOYMENT_NAME.
 */

import OpenAI from "openai";
import { DefaultAzureCredential } from "@azure/identity";

async function getToken(): Promise<string> {
  const credential = new DefaultAzureCredential();
  const tokenResponse = await credential.getToken(
    "https://ai.azure.com/.default"
  );
  if (!tokenResponse) {
    throw new Error("DefaultAzureCredential did not return an access token.");
  }
  return tokenResponse.token;
}

async function main() {
  const endpoint = process.env.AZURE_AI_PROJECT_ENDPOINT;
  if (!endpoint) {
    throw new Error("AZURE_AI_PROJECT_ENDPOINT must be set.");
  }

  const model =
    process.env.AZURE_MODEL_DEPLOYMENT_NAME ?? "DeepSeek-R1-0528";
  const baseURL = endpoint.replace(/\/+$/, "") + "/openai/v1";
  const token = await getToken();

  const client = new OpenAI({
    baseURL,
    apiKey: token,
  });

  const response = await client.responses.create({
    model,
    input: "Explain quantum computing in three sentences.",
    max_output_tokens: 500,
  });

  console.log(response.output_text);
  console.log(`\nStatus: ${response.status}`);
  console.log(`Model deployment: ${model}`);
}

main().catch((error: unknown) => {
  console.error(error);
  process.exitCode = 1;
});
