// Optix on Azure Container Apps. Build and lint only from this repo; deploying is a manual step
// (infra/deploy.md). No secrets: the app calls Azure OpenAI with its system-assigned managed
// identity, which gets one least-privilege role on one existing Azure OpenAI / Foundry resource.
targetScope = 'resourceGroup'

@description('Short prefix for resource names (lowercase letters and digits).')
@minLength(3)
@maxLength(12)
param namePrefix string = 'optix'

@description('Region for every resource.')
param location string = resourceGroup().location

@description('Container image to run, e.g. <registry>.azurecr.io/optix:<tag>.')
param image string

@description('Name of an existing Azure OpenAI / Azure AI Foundry (Cognitive Services) account in this resource group.')
param openAiAccountName string

@description('Chat model deployment name on that account (used by the guarded phraser).')
param openAiDeployment string

@description('Azure OpenAI API version for the chat client.')
param openAiApiVersion string = '2024-10-21'

@description('Optional: a user-assigned identity with AcrPull on a private registry (empty = public image).')
param registryServer string = ''
param registryIdentityId string = ''

var suffix = uniqueString(resourceGroup().id, namePrefix)
// Cognitive Services OpenAI User: read models and deployments, call completions. Nothing else.
var openAiUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${namePrefix}-logs-${suffix}'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${namePrefix}-ai-${suffix}'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
  }
}

resource env 'Microsoft.App/managedEnvironments@2026-07-01' = {
  name: '${namePrefix}-env-${suffix}'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

resource openAi 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: openAiAccountName
}

resource app 'Microsoft.App/containerApps@2026-07-01' = {
  name: '${namePrefix}-app'
  location: location
  identity: empty(registryIdentityId) ? {
    type: 'SystemAssigned'
  } : {
    type: 'SystemAssigned,UserAssigned'
    userAssignedIdentities: { '${registryIdentityId}': {} }
  }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
      registries: empty(registryServer) ? [] : [
        {
          server: registryServer
          identity: registryIdentityId
        }
      ]
      // the connection string is not a credential for data access, but it is kept out of plain
      // env values anyway: a Container Apps secret, referenced below
      secrets: [
        {
          name: 'appinsights-connection'
          value: appInsights.properties.ConnectionString
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'optix'
          image: image
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'AZURE_OPENAI_ENDPOINT', value: openAi.properties.endpoint }
            { name: 'AZURE_OPENAI_DEPLOYMENT', value: openAiDeployment }
            { name: 'AZURE_OPENAI_API_VERSION', value: openAiApiVersion }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'appinsights-connection' }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/healthz', port: 8000 }
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: { path: '/healthz', port: 8000 }
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 2
      }
    }
  }
}

// Least privilege: the app's own identity, one role, scoped to the one Azure OpenAI account.
resource openAiUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAi.id, app.id, openAiUserRoleId)
  scope: openAi
  properties: {
    principalId: app.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', openAiUserRoleId)
  }
}

output appUrl string = 'https://${app.properties.configuration.ingress.fqdn}'
output appPrincipalId string = app.identity.principalId
output appInsightsName string = appInsights.name
