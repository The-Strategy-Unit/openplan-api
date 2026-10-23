targetScope = 'resourceGroup'

@description('Name of the existing storage account.')
param storageAccountName string

@description('Name of the existing blob container.')
param containerName string

@description('Principal ID (object ID) of the user-assigned managed identity.')
param principalId string

resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' existing = {
  name: '${storageAccountName}/default/${containerName}'
}

var blobDataReaderRole = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'
)

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(container.id, principalId, blobDataReaderRole)
  scope: container
  properties: {
    roleDefinitionId: blobDataReaderRole
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

output roleAssignmentId string = roleAssignment.id
