// ──────────────────────────────────────────────
// Based on: https://github.com/microsoft-foundry/foundry-samples/blob/main/infrastructure/infrastructure-setup-bicep/00-basic/main.bicep
// ──────────────────────────────────────────────

@description('Name of the Microsoft Foundry account (CognitiveServices/accounts).')
param aiFoundryName string

@description('Name of the Microsoft Foundry project.')
param aiProjectName string

@description('Location for all resources.')
param location string

@description('Tags for all resources.')
param tags object = {}

// ── Primary model deployment parameters ─────
@description('Name of the primary model to deploy.')
param modelName string

@description('Format of the primary model (e.g., "DeepSeek", "OpenAI", "Microsoft").')
param modelFormat string

@description('Version of the primary model.')
param modelVersion string = ''

@description('Name for the primary deployment.')
param deploymentName string

@description('SKU name for the primary deployment.')
param deploymentSkuName string = 'GlobalStandard'

@description('SKU capacity for the primary deployment.')
param deploymentSkuCapacity int = 10

// ── Secondary model deployment parameters ───
@description('Name of the secondary model to deploy. Leave empty to skip.')
param model2Name string = ''

@description('Format of the secondary model.')
param model2Format string = 'OpenAI'

@description('Version of the secondary model.')
param model2Version string = ''

@description('Name for the secondary deployment.')
param deployment2Name string = ''

@description('SKU name for the secondary deployment.')
param deployment2SkuName string = 'GlobalStandard'

@description('SKU capacity for the secondary deployment.')
param deployment2SkuCapacity int = 10

// ── Third model deployment parameters ───
@description('Name of the third model to deploy. Leave empty to skip.')
param model3Name string = ''

@description('Format of the third model.')
param model3Format string = 'OpenAI'

@description('Version of the third model.')
param model3Version string = ''

@description('Name for the third deployment.')
param deployment3Name string = ''

@description('SKU name for the third deployment.')
param deployment3SkuName string = 'GlobalStandard'

@description('SKU capacity for the third deployment.')
param deployment3SkuCapacity int = 10

// ──────────────────────────────────────────────
// Microsoft Foundry account
//   A CognitiveServices/account with kind 'AIServices'
//   and allowProjectManagement = true
// ──────────────────────────────────────────────

resource aiFoundry 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: aiFoundryName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'S0'
  }
  kind: 'AIServices'
  properties: {
    // Required to work in Microsoft Foundry
    allowProjectManagement: true
    // Defines developer API endpoint subdomain
    customSubDomainName: aiFoundryName
    disableLocalAuth: false
    publicNetworkAccess: 'Enabled'
  }
}

// ──────────────────────────────────────────────
// Microsoft Foundry project
//   Projects group in- and outputs for one use case.
//   Development teams can get started right away.
// ──────────────────────────────────────────────

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  name: aiProjectName
  parent: aiFoundry
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {}
}

// ──────────────────────────────────────────────
// Primary model deployment
// ──────────────────────────────────────────────

resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: aiFoundry
  name: deploymentName
  sku: {
    capacity: deploymentSkuCapacity
    name: deploymentSkuName
  }
  properties: {
    model: {
      name: modelName
      format: modelFormat
      version: !empty(modelVersion) ? modelVersion : null
    }
  }
  dependsOn: [
    aiProject
  ]
}

// ──────────────────────────────────────────────
// Secondary model deployment (optional)
// ──────────────────────────────────────────────

resource model2Deployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = if (!empty(model2Name)) {
  parent: aiFoundry
  name: !empty(deployment2Name) ? deployment2Name : model2Name
  sku: {
    capacity: deployment2SkuCapacity
    name: deployment2SkuName
  }
  properties: {
    model: {
      name: model2Name
      format: model2Format
      version: !empty(model2Version) ? model2Version : null
    }
  }
  dependsOn: [
    modelDeployment
  ]
}

// ──────────────────────────────────────────────
// Third model deployment (optional)
// ──────────────────────────────────────────────

resource model3Deployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = if (!empty(model3Name)) {
  parent: aiFoundry
  name: !empty(deployment3Name) ? deployment3Name : model3Name
  sku: {
    capacity: deployment3SkuCapacity
    name: deployment3SkuName
  }
  properties: {
    model: {
      name: model3Name
      format: model3Format
      version: !empty(model3Version) ? model3Version : null
    }
  }
  dependsOn: [
    model2Deployment
  ]
}

// ── Identity / RBAC ──────────────────────────

@description('Principal ID of the deploying user.')
param principalId string = ''

@description('Create Foundry User role assignments for the deploying user and project identity. Requires role assignment write permission.')
param createRoleAssignments bool = false

// Foundry User — keyless data-plane access for Foundry projects and models
var foundryUserRoleId = '53ca6127-db72-4b80-b1b0-d745d6d5456d'

resource deployingUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (createRoleAssignments && !empty(principalId)) {
  name: guid(aiFoundry.id, 'deploying-user', principalId, foundryUserRoleId)
  scope: aiFoundry
  properties: {
    principalId: principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryUserRoleId)
    principalType: 'User'
  }
}

resource projectIdentityRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (createRoleAssignments) {
  name: guid(aiFoundry.id, 'project-identity', aiProject.id, foundryUserRoleId)
  scope: aiFoundry
  properties: {
    principalId: aiProject.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryUserRoleId)
    principalType: 'ServicePrincipal'
  }
}

// ──────────────────────────────────────────────
// Outputs
// ──────────────────────────────────────────────

output aiFoundryName string = aiFoundry.name
output aiFoundryEndpoint string = aiFoundry.properties.endpoint
output aiFoundryId string = aiFoundry.id
output aiProjectName string = aiProject.name
output aiProjectEndpoint string = aiProject.properties.endpoints['AI Foundry API']
