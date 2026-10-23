targetScope = 'resourceGroup'

@description('Name of the data storage account. Must be globally unique.')
param name string

@description('Azure region for the storage account.')
param location string

resource dataStorage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
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

output id string = dataStorage.id
output name string = dataStorage.name
