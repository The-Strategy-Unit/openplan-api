targetScope = 'resourceGroup'

@description('Name of the Function host storage account. Must be globally unique.')
param name string

@description('Azure region for the storage account.')
param location string

@description('Name of the private blob container used for Flex Consumption deployments.')
param deploymentContainerName string = 'function-deployments'

@description('Principal ID of the user-assigned identity used by the Function App.')
param identityPrincipalId string

resource hostStorage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: name
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    allowSharedKeyAccess: false
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: hostStorage
  name: 'default'
}

resource deploymentContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: deploymentContainerName
  properties: {
    publicAccess: 'None'
  }
}

var blobDataOwnerRole = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
)
var queueDataContributorRole = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
)
var tableDataContributorRole = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'
)

resource hostBlobRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(hostStorage.id, identityPrincipalId, blobDataOwnerRole)
  scope: hostStorage
  properties: {
    roleDefinitionId: blobDataOwnerRole
    principalId: identityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource hostQueueRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(hostStorage.id, identityPrincipalId, queueDataContributorRole)
  scope: hostStorage
  properties: {
    roleDefinitionId: queueDataContributorRole
    principalId: identityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource hostTableRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(hostStorage.id, identityPrincipalId, tableDataContributorRole)
  scope: hostStorage
  properties: {
    roleDefinitionId: tableDataContributorRole
    principalId: identityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output id string = hostStorage.id
output name string = hostStorage.name
output containerName string = deploymentContainer.name
