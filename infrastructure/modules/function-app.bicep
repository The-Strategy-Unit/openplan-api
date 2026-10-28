targetScope = 'resourceGroup'

@description('Name of the Function App.')
param name string

@description('Name of the Flex Consumption hosting plan.')
param planName string

@description('Azure region for the Function App and hosting plan.')
param location string

@description('Resource ID of the user-assigned managed identity.')
param identityId string

@description('Client ID of the user-assigned managed identity.')
param identityClientId string

@description('Name of the Function host storage account.')
param hostStorageName string

@description('Name of the private deployment container in host storage.')
param deploymentContainerName string

@description('Application Insights connection string.')
@secure()
param appInsightsConnectionString string

@description('Python runtime version.')
@allowed(['3.12', '3.13', '3.14'])
param pythonVersion string = '3.14'

@description('Maximum number of Flex Consumption instances.')
@minValue(1)
param maximumInstanceCount int = 100

@description('Memory per Flex Consumption instance, in MB.')
@allowed([2048, 4096])
param instanceMemoryMB int = 4096

resource plan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: planName
  location: location
  kind: 'functionapp,linux'
  sku: {
    name: 'FC1'
    tier: 'FlexConsumption'
  }
  properties: {
    reserved: true
  }
}

resource functionApp 'Microsoft.Web/sites@2025-03-01' = {
  name: name
  location: location
  kind: 'functionapp,linux'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityId}': {}
    }
  }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      appSettings: [
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'AzureWebJobsStorage__accountName'
          value: hostStorageName
        }
        {
          name: 'AzureWebJobsStorage__credential'
          value: 'managedidentity'
        }
        {
          name: 'AzureWebJobsStorage__clientId'
          value: identityClientId
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsightsConnectionString
        }
        {
          name: 'AZURE_CLIENT_ID'
          value: identityClientId
        }
      ]
    }
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: 'https://${hostStorageName}.blob.${environment().suffixes.storage}/${deploymentContainerName}'
          authentication: {
            type: 'UserAssignedIdentity'
            userAssignedIdentityResourceId: identityId
          }
        }
      }
      runtime: {
        name: 'python'
        version: pythonVersion
      }
      scaleAndConcurrency: {
        maximumInstanceCount: maximumInstanceCount
        instanceMemoryMB: instanceMemoryMB
      }
    }
  }
}

output url string = 'https://${functionApp.properties.defaultHostName}'
output id string = functionApp.id
