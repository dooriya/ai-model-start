from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from responses_common import DEFAULT_MODEL

REPO_ROOT = Path(__file__).resolve().parents[3]
EXPECTED_MODEL_NAME = "DeepSeek-V3.2"
EXPECTED_MODEL_FORMAT = "DeepSeek"
EXPECTED_MODEL_VERSION = "1"
EXPECTED_SKU_NAME = "GlobalStandard"
EXPECTED_SKU_CAPACITY = 10
FOUNDRY_USER_ROLE_ID = "53ca6127-db72-4b80-b1b0-d745d6d5456d"


def read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def compiled_template() -> dict[str, object]:
    az_command = shutil.which("az")
    if az_command is None:
        pytest.skip("Azure CLI is not available for Bicep compilation.")
    command: list[str] | str = [
        az_command,
        "bicep",
        "build",
        "--file",
        "infra/main.bicep",
        "--stdout",
    ]
    use_shell = False
    if os.name == "nt":
        command = f'"{az_command}" bicep build --file infra/main.bicep --stdout'
        use_shell = True
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        shell=use_shell,
        text=True,
    )
    return json.loads(result.stdout)


def compiled_role_assignments() -> tuple[dict[str, object], list[dict[str, object]]]:
    template = compiled_template()
    foundry_deployment = next(
        resource
        for resource in template["resources"]
        if resource["type"] == "Microsoft.Resources/deployments" and resource["name"] == "foundry"
    )
    nested_template = foundry_deployment["properties"]["template"]
    assignments = [
        resource
        for resource in nested_template["resources"]
        if resource["type"] == "Microsoft.Authorization/roleAssignments"
    ]
    return nested_template, assignments


def windows_postprovision_script() -> str:
    azure_yaml = read("azure.yaml")
    match = re.search(
        r"(?ms)^    windows:\r?\n      shell: pwsh\r?\n      run: \|\r?\n"
        r"(?P<script>.*?)(?=^    posix:)",
        azure_yaml,
    )
    assert match is not None
    return "\n".join(
        line[8:] if line.startswith("        ") else line
        for line in match.group("script").splitlines()
    )


def test_primary_model_tuple_and_optional_models_are_consistent() -> None:
    main_bicep = read("infra/main.bicep")
    assert f"param modelName string = '{EXPECTED_MODEL_NAME}'" in main_bicep
    assert f"param modelFormat string = '{EXPECTED_MODEL_FORMAT}'" in main_bicep
    assert f"param modelVersion string = '{EXPECTED_MODEL_VERSION}'" in main_bicep
    assert f"param deploymentSkuName string = '{EXPECTED_SKU_NAME}'" in main_bicep
    assert f"param deploymentSkuCapacity int = {EXPECTED_SKU_CAPACITY}" in main_bicep
    assert "param model2Name string = ''" in main_bicep
    assert "param model3Name string = ''" in main_bicep

    parameters = json.loads(read("infra/main.parameters.json"))["parameters"]
    assert parameters["modelName"]["value"] == f"${{AZURE_MODEL_NAME={EXPECTED_MODEL_NAME}}}"
    assert parameters["modelFormat"]["value"] == (
        f"${{AZURE_MODEL_FORMAT={EXPECTED_MODEL_FORMAT}}}"
    )
    assert parameters["modelVersion"]["value"] == (
        f"${{AZURE_MODEL_VERSION={EXPECTED_MODEL_VERSION}}}"
    )
    assert parameters["model2Name"]["value"] == "${AZURE_MODEL_2_NAME=}"
    assert parameters["model3Name"]["value"] == "${AZURE_MODEL_3_NAME=}"
    assert parameters["createRoleAssignments"]["value"] == (
        "${AZURE_CREATE_ROLE_ASSIGNMENTS=false}"
    )
    assert DEFAULT_MODEL == EXPECTED_MODEL_NAME


def test_role_assignments_are_opt_in_and_least_privilege() -> None:
    main_bicep = read("infra/main.bicep")
    foundry_bicep = read("infra/foundry.bicep")

    assert "param createRoleAssignments bool = false" in main_bicep
    assert "createRoleAssignments: createRoleAssignments" in main_bicep
    assert "param createRoleAssignments bool = false" in foundry_bicep
    assert foundry_bicep.count("Microsoft.Authorization/roleAssignments@2022-04-01") == 2
    assert FOUNDRY_USER_ROLE_ID in foundry_bicep
    assert "a97b65f3-24c7-4388-baec-2e87135dc908" not in foundry_bicep
    assert "if (createRoleAssignments && !empty(principalId))" in foundry_bicep
    assert "if (createRoleAssignments)" in foundry_bicep
    assert "principalType: 'User'" in foundry_bicep
    assert "principalType: 'ServicePrincipal'" in foundry_bicep
    assert foundry_bicep.count("scope: aiFoundry") == 2
    assert "'deploying-user'" in foundry_bicep
    assert "'project-identity'" in foundry_bicep
    assert "principalId: aiProject.identity.principalId" in foundry_bicep


def test_compiled_role_assignments_are_disabled_by_default_and_exact_when_enabled() -> None:
    template, assignments = compiled_role_assignments()

    assert template["parameters"]["createRoleAssignments"]["defaultValue"] is False
    assert len(assignments) == 2
    assert assignments[0]["condition"] == (
        "[and(parameters('createRoleAssignments'), not(empty(parameters('principalId'))))]"
    )
    assert assignments[1]["condition"] == "[parameters('createRoleAssignments')]"
    assert {assignment["properties"]["principalType"] for assignment in assignments} == {
        "User",
        "ServicePrincipal",
    }
    assert all(
        assignment["scope"]
        == "[resourceId('Microsoft.CognitiveServices/accounts', parameters('aiFoundryName'))]"
        for assignment in assignments
    )
    assert all(
        "variables('foundryUserRoleId')" in assignment["properties"]["roleDefinitionId"]
        for assignment in assignments
    )
    assert template["variables"]["foundryUserRoleId"] == FOUNDRY_USER_ROLE_ID
    assert "'deploying-user'" in assignments[0]["name"]
    assert "'project-identity'" in assignments[1]["name"]
    assert any(
        "Microsoft.CognitiveServices/accounts/projects" in dependency
        for dependency in assignments[1]["dependsOn"]
    )


def test_compiled_outputs_use_project_endpoint_and_distinct_hook_alias() -> None:
    template = compiled_template()
    foundry_deployment = next(
        resource
        for resource in template["resources"]
        if resource["type"] == "Microsoft.Resources/deployments" and resource["name"] == "foundry"
    )
    nested_outputs = foundry_deployment["properties"]["template"]["outputs"]
    top_outputs = template["outputs"]

    project_endpoint = nested_outputs["aiProjectEndpoint"]["value"]
    assert "Microsoft.CognitiveServices/accounts/projects" in project_endpoint
    assert ".endpoints['AI Foundry API']" in project_endpoint
    assert "properties.endpoint" not in project_endpoint
    assert "concat(" not in top_outputs["AZURE_AI_PROJECT_ENDPOINT"]["value"]
    assert top_outputs["AZURE_PRIMARY_MODEL_DEPLOYMENT_NAME"]["value"] == (
        "[variables('effectiveDeploymentName')]"
    )
    assert top_outputs["AZURE_MODEL_DEPLOYMENT_NAME"]["value"] == (
        "[variables('effectiveDeploymentName')]"
    )


def test_postprovision_env_manages_only_public_keys_and_fails_on_blank_outputs() -> None:
    azure_yaml = read("azure.yaml")
    assert "azd env get-value AZURE_AI_PROJECT_ENDPOINT" in azure_yaml
    assert "azd env get-value AZURE_PRIMARY_MODEL_DEPLOYMENT_NAME" in azure_yaml
    assert "AZURE_AI_PROJECT_ENDPOINT is blank after provisioning." in azure_yaml
    assert "AZURE_PRIMARY_MODEL_DEPLOYMENT_NAME is blank after provisioning." in azure_yaml
    assert azure_yaml.count("AZURE_AI_PROJECT_ENDPOINT = $endpoint") == 1
    assert azure_yaml.count("AZURE_MODEL_DEPLOYMENT_NAME = $model") == 1
    assert "AZURE_PRIMARY_MODEL_DEPLOYMENT_NAME =" not in azure_yaml
    assert "AZURE_MODEL_2_DEPLOYMENT_NAME" not in azure_yaml
    assert "AZURE_MODEL_3_DEPLOYMENT_NAME" not in azure_yaml


@pytest.mark.skipif(
    os.name != "nt" or shutil.which("pwsh") is None,
    reason="The embedded Windows postprovision hook requires PowerShell on Windows.",
)
def test_windows_postprovision_hook_preserves_unrelated_lines_and_is_idempotent(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "azd.cmd").write_text(
        "@echo off\r\n"
        'if "%3"=="AZURE_AI_PROJECT_ENDPOINT" (\r\n'
        "  echo https://example.services.ai.azure.com/api/projects/example\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        'if "%3"=="AZURE_PRIMARY_MODEL_DEPLOYMENT_NAME" (\r\n'
        "  echo DeepSeek-V3.2\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        "exit /b 1\r\n",
        encoding="utf-8",
    )
    script_path = tmp_path / "postprovision.ps1"
    script_path.write_text(windows_postprovision_script(), encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# keep\n"
        "CUSTOM_SETTING=preserved\n"
        "AZURE_AI_PROJECT_ENDPOINT=old\n"
        "AZURE_AI_PROJECT_ENDPOINT=duplicate\n"
        "AZURE_MODEL_DEPLOYMENT_NAME=old\n"
        "AZURE_MODEL_DEPLOYMENT_NAME=duplicate\n",
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"
    environment["PROJECT_DIR"] = str(tmp_path)

    subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(script_path)],
        check=True,
        capture_output=True,
        env=environment,
        text=True,
    )
    expected = (
        "# keep\n"
        "CUSTOM_SETTING=preserved\n"
        "AZURE_AI_PROJECT_ENDPOINT=https://example.services.ai.azure.com/api/projects/example\n"
        "AZURE_MODEL_DEPLOYMENT_NAME=DeepSeek-V3.2\n"
    )
    assert env_file.read_text(encoding="utf-8-sig") == expected

    modified_at = env_file.stat().st_mtime_ns
    content = env_file.read_bytes()
    time.sleep(0.02)
    subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(script_path)],
        check=True,
        capture_output=True,
        env=environment,
        text=True,
    )
    assert env_file.read_text(encoding="utf-8-sig") == expected
    assert env_file.read_bytes() == content
    assert env_file.stat().st_mtime_ns == modified_at


@pytest.mark.skipif(
    os.name != "nt" or shutil.which("pwsh") is None,
    reason="The embedded Windows postprovision hook requires PowerShell on Windows.",
)
def test_windows_postprovision_hook_rejects_blank_managed_output(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "azd.cmd").write_text(
        "@echo off\r\n"
        'if "%3"=="AZURE_AI_PROJECT_ENDPOINT" (\r\n'
        "  echo https://example.services.ai.azure.com/api/projects/example\r\n"
        "  exit /b 0\r\n"
        ")\r\n"
        'if "%3"=="AZURE_PRIMARY_MODEL_DEPLOYMENT_NAME" exit /b 0\r\n'
        "exit /b 1\r\n",
        encoding="utf-8",
    )
    script_path = tmp_path / "postprovision.ps1"
    script_path.write_text(windows_postprovision_script(), encoding="utf-8")
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"
    environment["PROJECT_DIR"] = str(tmp_path)

    result = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(script_path)],
        capture_output=True,
        env=environment,
        text=True,
    )
    assert result.returncode != 0
    assert "AZURE_PRIMARY_MODEL_DEPLOYMENT_NAME is blank after provisioning." in (
        result.stdout + result.stderr
    )
    assert not (tmp_path / ".env").exists()


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
        assert EXPECTED_MODEL_NAME in source, path
        assert "DeepSeek-R1-0528" not in source, path
        assert "AZURE_MODEL_2_DEPLOYMENT_NAME" not in source, path
        assert "AZURE_MODEL_3_DEPLOYMENT_NAME" not in source, path


def test_python_cli_preserves_opaque_model_override() -> None:
    source = read("src/python/responses_example.py")
    common = read("src/python/responses_common.py")
    assert "--model" in source
    assert "model=args.model" in source
    assert 'os.environ.get("AZURE_MODEL_DEPLOYMENT_NAME")' in common
    assert "DeepSeek-R1-0528" not in source
    assert "DeepSeek-R1-0528" not in common


def test_role_assignment_docs_match_opt_in_contract() -> None:
    readme = read("README.md")
    instructions = read(".github/copilot-instructions.md")
    for document in (readme, instructions):
        assert "AZURE_CREATE_ROLE_ASSIGNMENTS" in document
        assert "Foundry User" in document
        assert "roleAssignments/write" in document
        assert "Cognitive Services User" not in document
    assert "Role assignments are disabled by default" in readme
    assert "defaults to `false`" in instructions
