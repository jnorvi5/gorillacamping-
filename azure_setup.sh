#!/bin/bash

# Azure Deployment Setup Script for Gorilla Camping

echo "🐵 Gorilla Camping Azure Setup"
echo "================================"

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI not found. Please install it first:"
    echo "   https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Check if user is logged in
if ! az account show &> /dev/null; then
    echo "🔐 Please log in to Azure:"
    az login
fi

# Get configuration from user
echo ""
echo "📝 Configuration Setup"
echo "----------------------"
read -p "Resource Group Name [gorillacamping-rg]: " RESOURCE_GROUP
RESOURCE_GROUP=${RESOURCE_GROUP:-gorillacamping-rg}

read -p "Location [East US]: " LOCATION
LOCATION=${LOCATION:-eastus}

read -p "App Service Name [gorillacamping]: " APP_NAME
APP_NAME=${APP_NAME:-gorillacamping}

echo ""
echo "🏗️  Creating Azure Resources..."
echo "Resource Group: $RESOURCE_GROUP"
echo "Location: $LOCATION"
echo "App Service: $APP_NAME"
echo ""

# Create resource group
echo "Creating resource group..."
az group create --name $RESOURCE_GROUP --location "$LOCATION"

# Create App Service Plan
echo "Creating App Service Plan..."
az appservice plan create \
    --name ${APP_NAME}-plan \
    --resource-group $RESOURCE_GROUP \
    --location "$LOCATION" \
    --sku B1 \
    --is-linux

# Create Web App
echo "Creating Web App..."
az webapp create \
    --name $APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --plan ${APP_NAME}-plan \
    --runtime "PYTHON|3.10"

# Create Cosmos DB Account (MongoDB API)
echo "Creating Cosmos DB with MongoDB API..."
az cosmosdb create \
    --name ${APP_NAME}-cosmos \
    --resource-group $RESOURCE_GROUP \
    --locations regionName="$LOCATION" \
    --kind MongoDB \
    --default-consistency-level Eventual

# Create Cosmos DB Database
az cosmosdb mongodb database create \
    --account-name ${APP_NAME}-cosmos \
    --resource-group $RESOURCE_GROUP \
    --name gorillacamping

# Create OpenAI Service
echo "Creating Azure OpenAI Service..."
az cognitiveservices account create \
    --name ${APP_NAME}-openai \
    --resource-group $RESOURCE_GROUP \
    --location "$LOCATION" \
    --kind OpenAI \
    --sku S0

# Create Key Vault
echo "Creating Key Vault..."
az keyvault create \
    --name ${APP_NAME}-kv \
    --resource-group $RESOURCE_GROUP \
    --location "$LOCATION"

# Create Storage Account
echo "Creating Storage Account..."
az storage account create \
    --name ${APP_NAME}storage \
    --resource-group $RESOURCE_GROUP \
    --location "$LOCATION" \
    --sku Standard_LRS

# Create Application Insights
echo "Creating Application Insights..."
az extension add --name application-insights
az monitor app-insights component create \
    --app ${APP_NAME}-insights \
    --location "$LOCATION" \
    --resource-group $RESOURCE_GROUP

echo ""
echo "✅ Azure Resources Created!"
echo ""
echo "🔧 Getting Configuration Values..."
echo ""

# Get Cosmos DB connection details
COSMOS_ENDPOINT=$(az cosmosdb show --name ${APP_NAME}-cosmos --resource-group $RESOURCE_GROUP --query documentEndpoint -o tsv)
COSMOS_KEY=$(az cosmosdb keys list --name ${APP_NAME}-cosmos --resource-group $RESOURCE_GROUP --query primaryMasterKey -o tsv)

# Get OpenAI endpoint and key
OPENAI_ENDPOINT=$(az cognitiveservices account show --name ${APP_NAME}-openai --resource-group $RESOURCE_GROUP --query properties.endpoint -o tsv)
OPENAI_KEY=$(az cognitiveservices account keys list --name ${APP_NAME}-openai --resource-group $RESOURCE_GROUP --query key1 -o tsv)

# Get Key Vault URL
KEYVAULT_URL=$(az keyvault show --name ${APP_NAME}-kv --resource-group $RESOURCE_GROUP --query properties.vaultUri -o tsv)

# Get Storage connection string
STORAGE_CONNECTION=$(az storage account show-connection-string --name ${APP_NAME}storage --resource-group $RESOURCE_GROUP --query connectionString -o tsv)

# Get Application Insights connection string
APPINSIGHTS_CONNECTION=$(az monitor app-insights component show --app ${APP_NAME}-insights --resource-group $RESOURCE_GROUP --query connectionString -o tsv)

echo "📱 Configure these environment variables in your Azure App Service:"
echo ""
echo "AZURE_COSMOS_ENDPOINT=$COSMOS_ENDPOINT"
echo "AZURE_COSMOS_KEY=$COSMOS_KEY"
echo "AZURE_COSMOS_DATABASE=gorillacamping"
echo ""
echo "AZURE_OPENAI_ENDPOINT=$OPENAI_ENDPOINT"
echo "AZURE_OPENAI_API_KEY=$OPENAI_KEY"
echo "AZURE_OPENAI_API_VERSION=2024-02-01"
echo "AZURE_OPENAI_DEPLOYMENT=gpt-35-turbo"
echo ""
echo "AZURE_KEYVAULT_URL=$KEYVAULT_URL"
echo "AZURE_STORAGE_CONNECTION_STRING=$STORAGE_CONNECTION"
echo "APPLICATIONINSIGHTS_CONNECTION_STRING=$APPINSIGHTS_CONNECTION"
echo ""

# Set environment variables in App Service
echo "⚙️  Setting environment variables in App Service..."
az webapp config appsettings set \
    --name $APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --settings \
        AZURE_COSMOS_ENDPOINT="$COSMOS_ENDPOINT" \
        AZURE_COSMOS_KEY="$COSMOS_KEY" \
        AZURE_COSMOS_DATABASE="gorillacamping" \
        AZURE_OPENAI_ENDPOINT="$OPENAI_ENDPOINT" \
        AZURE_OPENAI_API_KEY="$OPENAI_KEY" \
        AZURE_OPENAI_API_VERSION="2024-02-01" \
        AZURE_OPENAI_DEPLOYMENT="gpt-35-turbo" \
        AZURE_KEYVAULT_URL="$KEYVAULT_URL" \
        AZURE_STORAGE_CONNECTION_STRING="$STORAGE_CONNECTION" \
        APPLICATIONINSIGHTS_CONNECTION_STRING="$APPINSIGHTS_CONNECTION"

echo ""
echo "🎉 Azure setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Deploy your GPT model to Azure OpenAI service"
echo "2. Enable managed identity for your App Service"
echo "3. Grant permissions to Key Vault and other services"
echo "4. Deploy your application using GitHub Actions"
echo ""
echo "🌐 Your app will be available at: https://${APP_NAME}.azurewebsites.net"
echo ""