# Azure Integration for Gorilla Camping

This document explains how to connect the Gorilla Camping application to Azure services.

## Overview

The application now supports Azure services as primary options with fallback to existing services:

- **Azure Cosmos DB** (with MongoDB API) → Falls back to MongoDB
- **Azure OpenAI** → Falls back to Google Gemini AI
- **Azure Key Vault** → Falls back to environment variables
- **Azure Storage** → For file storage (optional)
- **Azure Application Insights** → For monitoring (optional)

## Quick Setup

### Option 1: Automated Setup (Recommended)

1. **Install Azure CLI**:
   ```bash
   # macOS
   brew install azure-cli
   
   # Windows
   winget install Microsoft.AzureCLI
   
   # Linux
   curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
   ```

2. **Run the setup script**:
   ```bash
   ./azure_setup.sh
   ```
   
   This will:
   - Create all necessary Azure resources
   - Configure environment variables in your App Service
   - Display connection strings and endpoints

### Option 2: Manual Setup

#### 1. Create Azure Resources

```bash
# Login to Azure
az login

# Create resource group
az group create --name gorillacamping-rg --location eastus

# Create Cosmos DB with MongoDB API
az cosmosdb create \
    --name gorillacamping-cosmos \
    --resource-group gorillacamping-rg \
    --locations regionName=eastus \
    --kind MongoDB

# Create Azure OpenAI service
az cognitiveservices account create \
    --name gorillacamping-openai \
    --resource-group gorillacamping-rg \
    --location eastus \
    --kind OpenAI \
    --sku S0

# Create Key Vault
az keyvault create \
    --name gorillacamping-kv \
    --resource-group gorillacamping-rg \
    --location eastus

# Create Storage Account
az storage account create \
    --name gorillacampingstorage \
    --resource-group gorillacamping-rg \
    --location eastus \
    --sku Standard_LRS

# Create Application Insights
az monitor app-insights component create \
    --app gorillacamping-insights \
    --location eastus \
    --resource-group gorillacamping-rg
```

#### 2. Configure Environment Variables

Set these in your Azure App Service Configuration or `.env` file:

```env
# Azure Cosmos DB
AZURE_COSMOS_ENDPOINT=https://your-cosmos.documents.azure.com:443/
AZURE_COSMOS_KEY=your-cosmos-key
AZURE_COSMOS_DATABASE=gorillacamping

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
AZURE_OPENAI_API_KEY=your-openai-key
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_OPENAI_DEPLOYMENT=gpt-35-turbo

# Azure Key Vault
AZURE_KEYVAULT_URL=https://your-keyvault.vault.azure.net/

# Azure Storage
AZURE_STORAGE_CONNECTION_STRING=your-storage-connection-string

# Application Insights
APPLICATIONINSIGHTS_CONNECTION_STRING=your-insights-connection-string
```

## Health Monitoring

The application provides two new endpoints for monitoring Azure connectivity:

### Health Check Endpoint
```
GET /health
```

Returns overall application health and service status:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00.000000",
  "services": {
    "database": "azure_cosmos_db",
    "ai": "azure_openai",
    "knowledge_base": "available",
    "azure_keyvault": "available",
    "azure_storage": "available",
    "azure_monitoring": "available"
  }
}
```

### Azure Configuration Status
```
GET /azure/config
```

Returns detailed Azure service configuration:
```json
{
  "azure_services_available": {
    "cosmos_db": true,
    "openai": true,
    "keyvault": true,
    "storage": true,
    "monitoring": true
  },
  "environment_variables_configured": {
    "azure_cosmos_endpoint": true,
    "azure_openai_endpoint": true,
    "azure_keyvault_url": true,
    "azure_storage_connection": true,
    "application_insights": true
  }
}
```

## Deployment

The existing GitHub Actions workflow (`.github/workflows/main_gorillacamping.yml`) already deploys to Azure App Service. After setting up Azure services:

1. Configure the environment variables in your Azure App Service
2. Push your code to trigger deployment
3. Check the `/health` endpoint to verify services are connected

## Service Fallback Behavior

The application gracefully falls back to existing services if Azure services are not available:

| Azure Service | Fallback | Behavior |
|---------------|----------|----------|
| Cosmos DB | MongoDB | Uses existing MongoDB connection |
| Azure OpenAI | Google Gemini | Uses existing Gemini AI API |
| Key Vault | Environment Variables | Reads directly from env vars |
| Storage | Local Storage | Continues with local file storage |
| App Insights | Basic Logging | Uses Python logging |

## Security Best Practices

1. **Use Managed Identity**: When possible, configure your App Service to use Managed Identity instead of API keys
2. **Store Secrets in Key Vault**: Move sensitive configuration to Azure Key Vault
3. **Enable HTTPS Only**: Ensure your App Service only accepts HTTPS traffic
4. **Configure Access Restrictions**: Limit access to your App Service if needed

## Troubleshooting

### Common Issues

1. **Azure SDK not installed**: Install required packages with `pip install -r requirements.txt`
2. **Authentication errors**: Verify API keys and endpoints are correctly configured
3. **Network connectivity**: Check that your App Service can reach Azure services
4. **Quotas exceeded**: Monitor your Azure service quotas and usage

### Debug Commands

```bash
# Test Azure connectivity
curl https://your-app.azurewebsites.net/health

# Check configuration
curl https://your-app.azurewebsites.net/azure/config

# View App Service logs
az webapp log tail --name your-app --resource-group your-rg
```

## Cost Optimization

- **Cosmos DB**: Start with provisioned throughput (400 RU/s) for development
- **Azure OpenAI**: Monitor token usage and set spending limits
- **App Service**: Use B1 tier for development, scale up for production
- **Storage**: Use locally redundant storage (LRS) unless high availability is needed

## Next Steps

1. Deploy a GPT model to your Azure OpenAI service
2. Set up custom domains and SSL certificates
3. Configure monitoring and alerting in Application Insights
4. Implement Azure Active Directory authentication if needed
5. Set up backup and disaster recovery procedures