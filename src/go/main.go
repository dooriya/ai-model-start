// Microsoft Foundry Responses API quickstart using the standard OpenAI SDK.
// Makes one request to the deployment alias in AZURE_MODEL_DEPLOYMENT_NAME.
package main

import (
	"context"
	"fmt"
	"os"
	"strings"

	"github.com/Azure/azure-sdk-for-go/sdk/azcore/policy"
	"github.com/Azure/azure-sdk-for-go/sdk/azidentity"
	"github.com/openai/openai-go/v3"
	"github.com/openai/openai-go/v3/option"
	"github.com/openai/openai-go/v3/responses"
)

func main() {
	endpoint := os.Getenv("AZURE_AI_PROJECT_ENDPOINT")
	if endpoint == "" {
		fmt.Fprintln(os.Stderr, "Error: AZURE_AI_PROJECT_ENDPOINT must be set.")
		os.Exit(1)
	}

	ctx := context.Background()

	// Get EntraID token for keyless auth
	credential, err := azidentity.NewDefaultAzureCredential(nil)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create credential: %v\n", err)
		os.Exit(1)
	}
	token, err := credential.GetToken(ctx, policy.TokenRequestOptions{
		Scopes: []string{"https://ai.azure.com/.default"},
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to get token: %v\n", err)
		os.Exit(1)
	}

	// Standard OpenAI client — no Azure wrapper (no api-version needed with /v1 path)
	baseURL := strings.TrimRight(endpoint, "/") + "/openai/v1"
	client := openai.NewClient(
		option.WithBaseURL(baseURL),
		option.WithAPIKey(token.Token),
	)

	model := os.Getenv("AZURE_MODEL_DEPLOYMENT_NAME")
	if model == "" {
		model = "DeepSeek-R1-0528"
	}
	resp, err := client.Responses.New(ctx, responses.ResponseNewParams{
		Model: model,
		Input: responses.ResponseNewParamsInputUnion{
			OfString: openai.String("Explain quantum computing in three sentences."),
		},
		MaxOutputTokens: openai.Int(500),
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	fmt.Println(resp.OutputText())
	fmt.Printf("\nStatus: %s\n", resp.Status)
	fmt.Printf("Model deployment: %s\n", model)
}
