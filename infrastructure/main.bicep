targetScope = 'resourceGroup'

@description('Base used for resource names. Defaults to the resource group name.')
param nameBase string = resourceGroup().name

@description('Name of the Function App.')
param functionAppName string = resourceGroup().name

@description('Azure region for resources.')
param location string = resourceGroup().location

@description('Client ID of the existing Entra app registration used by Easy Auth.')
param entraClientId string

@description('Maximum number of Flex Consumption instances.')
@minValue(1)
param maximumInstanceCount int = 100

@description('Memory per Flex Consumption instance, in MB.')
@allowed([2048, 4096])
param instanceMemoryMB int = 4096

@description('Python version for the Function App.')
@allowed(['3.12', '3.13', '3.14'])
param pythonVersion string = '3.14'

// Storage account names must be 3-24 characters and contain only lowercase
// letters and numbers. Keep the unique suffix even when nameBase is long.
var storageSuffix = uniqueString(resourceGroup().id)
var cleanBase = toLower(replace(replace(nameBase, '-', ''), '_', ''))
var hostStorageName = '${take(cleanBase, 11)}${storageSuffix}'

var identityName = '${nameBase}-identity'
var planName = '${nameBase}-plan'
var workspaceName = '${nameBase}-logs'
var insightsName = '${nameBase}-insights'
var deploymentContainerName = 'function-deployments'

module identity 'modules/identity.bicep' = {
  name: 'identity'
  params: {
    name: identityName
    location: location
  }
}

module hostStorage 'modules/host-storage.bicep' = {
  name: 'host-storage'
  params: {
    name: hostStorageName
    location: location
    deploymentContainerName: deploymentContainerName
    identityPrincipalId: identity.outputs.principalId
  }
}

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    workspaceName: workspaceName
    insightsName: insightsName
    location: location
  }
}

module functionApp 'modules/function-app.bicep' = {
  name: 'function-app'
  params: {
    name: functionAppName
    planName: planName
    location: location

    identityId: identity.outputs.id
    identityClientId: identity.outputs.clientId

    hostStorageName: hostStorage.outputs.name
    deploymentContainerName: hostStorage.outputs.containerName

    appInsightsConnectionString: monitoring.outputs.connectionString

    pythonVersion: pythonVersion
    maximumInstanceCount: maximumInstanceCount
    instanceMemoryMB: instanceMemoryMB
  }
}

module functionAuthentication 'modules/function-authentication.bicep' = {
  name: 'function-authentication'
  params: {
    name: functionAppName
    entraClientId: entraClientId
  }
  dependsOn: [
    functionApp
  ]
}

output functionAppName string = functionAppName
output functionAppUrl string = functionApp.outputs.url
output userAssignedIdentityPrincipalId string = identity.outputs.principalId
output hostStorageAccountName string = hostStorage.outputs.name
output applicationInsightsName string = monitoring.outputs.insightsName
