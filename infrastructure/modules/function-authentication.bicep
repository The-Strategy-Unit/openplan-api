@description('Name of the Function App.')
param name string

@description('Application (client) ID of the existing Microsoft Entra app registration.')
param entraClientId string

var entraTenantId = tenant().tenantId

resource functionApp 'Microsoft.Web/sites@2022-09-01' existing = {
  name: name
}

resource authSettings 'Microsoft.Web/sites/config@2022-09-01' = {
  parent: functionApp
  name: 'authsettingsV2'
  properties: {
    platform: {
      enabled: true
    }
    globalValidation: {
      requireAuthentication: true
      unauthenticatedClientAction: 'RedirectToLoginPage'
      redirectToProvider: 'azureactivedirectory'
    }
    httpSettings: {
      requireHttps: true
    }
    login: {
      tokenStore: { enabled: true }
    }

    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          clientId: entraClientId
          openIdIssuer: '${environment().authentication.loginEndpoint}${entraTenantId}/v2.0'
        }
        validation: {
          allowedAudiences: [
            'api://${entraClientId}'
          ]
        }
      }
    }
  }
}
