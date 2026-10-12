from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_optional_model_parameters_default_to_empty() -> None:
    main_bicep = read("infra/main.bicep")
    assert "param model2Name string = ''" in main_bicep
    assert "param model3Name string = ''" in main_bicep

    parameters = json.loads(read("infra/main.parameters.json"))["parameters"]
    assert parameters["model2Name"]["value"] == "${AZURE_MODEL_2_NAME=}"
    assert parameters["model3Name"]["value"] == "${AZURE_MODEL_3_NAME=}"


def test_postprovision_env_manages_only_primary_model() -> None:
    azure_yaml = read("azure.yaml")
    assert "AZURE_AI_PROJECT_ENDPOINT" in azure_yaml
    assert "AZURE_MODEL_DEPLOYMENT_NAME" in azure_yaml
    assert "AZURE_MODEL_2_DEPLOYMENT_NAME" not in azure_yaml
    assert "AZURE_MODEL_3_DEPLOYMENT_NAME" not in azure_yaml


def test_non_python_quickstarts_make_one_primary_model_call() -> None:
    quickstarts = {
        "src/typescript/responses_example.ts": "client.responses.create(",
        "src/csharp/Program.cs": "CreateResponseAsync(",
        "src/java/src/main/java/ResponsesExample.java": "client.responses().create(",
        "src/go/main.go": "client.Responses.New(",
    }
    for path, call_expression in quickstarts.items():
        source = read(path)
        assert source.count(call_expression) == 1, path
        assert "AZURE_MODEL_DEPLOYMENT_NAME" in source, path
        assert "AZURE_MODEL_2_DEPLOYMENT_NAME" not in source, path
        assert "AZURE_MODEL_3_DEPLOYMENT_NAME" not in source, path
