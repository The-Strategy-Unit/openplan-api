#!/usr/bin/env bash

set -euo pipefail

# Allowed environments
ENVIRONMENTS=("dev" "prod")

# variables that might need to be reconfigured if anything changes in the future
location="uksouth"

# validate environment argument ------------------------------------------------

# Check the number of arguments
if [[ $# -gt 1 ]]; then
    echo "Error: Too many arguments." >&2
    echo "Usage: $0 [${ENVIRONMENTS[*]}]" >&2
    exit 1
fi

# Use the supplied argument, or prompt the user
if [[ $# -eq 1 ]]; then
    ENVIRONMENT="$1"
else
    echo "Choose an environment:"
    select ENVIRONMENT in "${ENVIRONMENTS[@]}"; do
        if [[ -n "$ENVIRONMENT" ]]; then
            break
        fi
        echo "Invalid choice. Please try again."
    done
fi

# Validate the selected environment
if [[ ! " ${ENVIRONMENTS[*]} " =~ " ${ENVIRONMENT} " ]]; then
    echo "Error: Invalid environment '${ENVIRONMENT}'." >&2
    echo "Allowed values: ${ENVIRONMENTS[*]}" >&2
    exit 1
fi

resourceGroup="openplan-api-$ENVIRONMENT"
applicationName="su-nhp-${ENVIRONMENT}"

# Dataset storage must be explicit and is separate from Functions host storage.
storageAccountName="${OPENPLAN_STORAGE_ACCOUNT_NAME:?Set OPENPLAN_STORAGE_ACCOUNT_NAME}"
storageAccountContainer="${OPENPLAN_STORAGE_CONTAINER_NAME:?Set OPENPLAN_STORAGE_CONTAINER_NAME}"
storageAccountResourceGroup="${OPENPLAN_STORAGE_RESOURCE_GROUP:?Set OPENPLAN_STORAGE_RESOURCE_GROUP}"

cacheTtlSeconds="${OPENPLAN_CACHE_TTL_SECONDS-300}"
cacheMaxBytes="${OPENPLAN_CACHE_MAX_BYTES-134217728}"
if [[ ! "$cacheTtlSeconds" =~ ^[0-9]+$ ]]; then
    echo "Error: OPENPLAN_CACHE_TTL_SECONDS must be a non-negative integer." >&2
    exit 1
fi
if [[ ! "$cacheMaxBytes" =~ ^[0-9]+$ ]]; then
    echo "Error: OPENPLAN_CACHE_MAX_BYTES must be a non-negative integer." >&2
    exit 1
fi

# create the resources ---------------------------------------------------------
echo "Creating resource group $resourceGroup"

az group create \
  --name "$resourceGroup" \
  --location "$location" \
  --only-show-errors 1>/dev/null

# fetch Entra client ID for the application ------------------------------------
echo "Fetching Entra client ID for $applicationName"

entraClientId=$(az ad app list \
  --display-name "$applicationName" \
  --query "[].{ClientId:appId}" \
  --output tsv)

# deploy main template ---------------------------------------------------------
echo "Deploying function app"

mainOutputs=$(az deployment group create \
  --resource-group "$resourceGroup" \
  --template-file "infrastructure/main.bicep" \
  --output json \
  --parameters \
    entraClientId="$entraClientId" \
    dataStorageAccountName="$storageAccountName" \
    dataStorageContainerName="$storageAccountContainer" \
    cacheTtlSeconds="$cacheTtlSeconds" \
    cacheMaxBytes="$cacheMaxBytes")

# grant data access to the storage account -------------------------------------
echo "Granting data access to the storage account $storageAccountName"

principalId=$(jq -r '.properties.outputs.userAssignedIdentityPrincipalId.value' <<< "$mainOutputs")
az deployment group create \
  --resource-group "$storageAccountResourceGroup" \
  --template-file "infrastructure/grant-data-access.bicep" \
  --parameters \
    storageAccountName="$storageAccountName" \
    containerName="$storageAccountContainer" \
    principalId="$principalId" \
  --only-show-errors 1>/dev/null

# deploy the function app ------------------------------------------------------
functionAppName=$(jq -r '.properties.outputs.functionAppName.value' <<< "$mainOutputs")
echo "Deploying the function app '$functionAppName' (waiting 5s for resources to be ready)"

sleep 5
func azure functionapp publish "$functionAppName" --python
