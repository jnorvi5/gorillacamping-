"""
Azure Services Integration Module
Provides Azure service connections for Gorilla Camping app
"""
import os
import logging
from typing import Optional, Any, Dict

# Optional Azure imports - graceful fallback if not available
try:
    from azure.cosmos import CosmosClient, DatabaseProxy, ContainerProxy
    from azure.cosmos.exceptions import CosmosResourceNotFoundError
    AZURE_COSMOS_AVAILABLE = True
except ImportError:
    print("⚠️ Azure Cosmos DB SDK not available")
    AZURE_COSMOS_AVAILABLE = False

try:
    from azure.openai import OpenAIClient
    from azure.identity import DefaultAzureCredential, EnvironmentCredential
    AZURE_OPENAI_AVAILABLE = True
except ImportError:
    print("⚠️ Azure OpenAI SDK not available")
    AZURE_OPENAI_AVAILABLE = False

try:
    from azure.keyvault.secrets import SecretClient
    AZURE_KEYVAULT_AVAILABLE = True
except ImportError:
    print("⚠️ Azure Key Vault SDK not available")
    AZURE_KEYVAULT_AVAILABLE = False

try:
    from azure.storage.blob import BlobServiceClient
    AZURE_STORAGE_AVAILABLE = True
except ImportError:
    print("⚠️ Azure Storage SDK not available")
    AZURE_STORAGE_AVAILABLE = False

try:
    from azure.monitor.opentelemetry import configure_azure_monitor
    AZURE_MONITOR_AVAILABLE = True
except ImportError:
    print("⚠️ Azure Monitor SDK not available")
    AZURE_MONITOR_AVAILABLE = False


class AzureCosmosDB:
    """Azure Cosmos DB wrapper with MongoDB API compatibility"""
    
    def __init__(self):
        self.client: Optional[CosmosClient] = None
        self.database: Optional[DatabaseProxy] = None
        self.containers: Dict[str, ContainerProxy] = {}
        self._initialize()
    
    def _initialize(self):
        """Initialize Azure Cosmos DB connection"""
        if not AZURE_COSMOS_AVAILABLE:
            return
            
        try:
            endpoint = os.environ.get('AZURE_COSMOS_ENDPOINT')
            key = os.environ.get('AZURE_COSMOS_KEY')
            database_name = os.environ.get('AZURE_COSMOS_DATABASE', 'gorillacamping')
            
            if endpoint and key:
                self.client = CosmosClient(endpoint, key)
                self.database = self.client.get_database_client(database_name)
                print("✅ Azure Cosmos DB initialized")
                return True
            else:
                print("⚠️ Azure Cosmos DB credentials not found")
                return False
                
        except Exception as e:
            print(f"❌ Azure Cosmos DB initialization failed: {e}")
            return False
    
    def get_container(self, container_name: str):
        """Get or create a container"""
        if not self.database:
            return None
            
        if container_name not in self.containers:
            try:
                self.containers[container_name] = self.database.get_container_client(container_name)
            except CosmosResourceNotFoundError:
                # Create container if it doesn't exist
                self.containers[container_name] = self.database.create_container(
                    id=container_name,
                    partition_key={"kind": "Hash", "paths": ["/id"]}
                )
        
        return self.containers[container_name]
    
    def is_available(self) -> bool:
        return self.client is not None


class AzureOpenAI:
    """Azure OpenAI service wrapper"""
    
    def __init__(self):
        self.client: Optional[OpenAIClient] = None
        self.deployment_name: str = ""
        self._initialize()
    
    def _initialize(self):
        """Initialize Azure OpenAI connection"""
        if not AZURE_OPENAI_AVAILABLE:
            return False
            
        try:
            endpoint = os.environ.get('AZURE_OPENAI_ENDPOINT')
            api_key = os.environ.get('AZURE_OPENAI_API_KEY')
            api_version = os.environ.get('AZURE_OPENAI_API_VERSION', '2024-02-01')
            self.deployment_name = os.environ.get('AZURE_OPENAI_DEPLOYMENT', 'gpt-35-turbo')
            
            if endpoint and api_key:
                # Use API key authentication
                self.client = OpenAIClient(
                    azure_endpoint=endpoint,
                    api_key=api_key,
                    api_version=api_version
                )
                print("✅ Azure OpenAI initialized")
                return True
            elif endpoint:
                # Try managed identity authentication
                credential = DefaultAzureCredential()
                self.client = OpenAIClient(
                    azure_endpoint=endpoint,
                    credential=credential,
                    api_version=api_version
                )
                print("✅ Azure OpenAI initialized with managed identity")
                return True
            else:
                print("⚠️ Azure OpenAI credentials not found")
                return False
                
        except Exception as e:
            print(f"❌ Azure OpenAI initialization failed: {e}")
            return False
    
    def generate_response(self, user_query: str, context: str = "") -> str:
        """Generate AI response using Azure OpenAI"""
        if not self.client:
            return "Azure OpenAI service is not available."
        
        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": "You are a helpful camping and outdoor gear assistant."},
                    {"role": "user", "content": f"{context}\n\n{user_query}"}
                ],
                max_tokens=500,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"❌ Azure OpenAI error: {e}")
            return "Sorry, I'm having trouble connecting to the AI service."
    
    def is_available(self) -> bool:
        return self.client is not None


class AzureKeyVault:
    """Azure Key Vault service wrapper"""
    
    def __init__(self):
        self.client: Optional[SecretClient] = None
        self._initialize()
    
    def _initialize(self):
        """Initialize Azure Key Vault connection"""
        if not AZURE_KEYVAULT_AVAILABLE:
            return False
            
        try:
            vault_url = os.environ.get('AZURE_KEYVAULT_URL')
            
            if vault_url:
                credential = DefaultAzureCredential()
                self.client = SecretClient(vault_url=vault_url, credential=credential)
                print("✅ Azure Key Vault initialized")
                return True
            else:
                print("⚠️ Azure Key Vault URL not found")
                return False
                
        except Exception as e:
            print(f"❌ Azure Key Vault initialization failed: {e}")
            return False
    
    def get_secret(self, secret_name: str) -> Optional[str]:
        """Get secret from Azure Key Vault"""
        if not self.client:
            return None
            
        try:
            secret = self.client.get_secret(secret_name)
            return secret.value
        except Exception as e:
            print(f"❌ Error retrieving secret '{secret_name}': {e}")
            return None
    
    def is_available(self) -> bool:
        return self.client is not None


class AzureStorage:
    """Azure Blob Storage service wrapper"""
    
    def __init__(self):
        self.client: Optional[BlobServiceClient] = None
        self._initialize()
    
    def _initialize(self):
        """Initialize Azure Storage connection"""
        if not AZURE_STORAGE_AVAILABLE:
            return False
            
        try:
            connection_string = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
            account_url = os.environ.get('AZURE_STORAGE_ACCOUNT_URL')
            
            if connection_string:
                self.client = BlobServiceClient.from_connection_string(connection_string)
                print("✅ Azure Storage initialized with connection string")
                return True
            elif account_url:
                credential = DefaultAzureCredential()
                self.client = BlobServiceClient(account_url=account_url, credential=credential)
                print("✅ Azure Storage initialized with managed identity")
                return True
            else:
                print("⚠️ Azure Storage credentials not found")
                return False
                
        except Exception as e:
            print(f"❌ Azure Storage initialization failed: {e}")
            return False
    
    def is_available(self) -> bool:
        return self.client is not None


class AzureMonitoring:
    """Azure Application Insights monitoring"""
    
    def __init__(self):
        self.enabled = self._initialize()
    
    def _initialize(self):
        """Initialize Azure Application Insights"""
        if not AZURE_MONITOR_AVAILABLE:
            return False
            
        try:
            connection_string = os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING')
            
            if connection_string:
                configure_azure_monitor(connection_string=connection_string)
                print("✅ Azure Application Insights initialized")
                return True
            else:
                print("⚠️ Application Insights connection string not found")
                return False
                
        except Exception as e:
            print(f"❌ Azure Application Insights initialization failed: {e}")
            return False
    
    def is_available(self) -> bool:
        return self.enabled


# Global Azure service instances
azure_cosmos = AzureCosmosDB()
azure_openai = AzureOpenAI()
azure_keyvault = AzureKeyVault()
azure_storage = AzureStorage()
azure_monitoring = AzureMonitoring()


def get_config_value(key: str, default: Any = None) -> Any:
    """Get configuration value from Azure Key Vault or environment variables"""
    # Try Key Vault first
    if azure_keyvault.is_available():
        secret_value = azure_keyvault.get_secret(key.replace('_', '-').lower())
        if secret_value:
            return secret_value
    
    # Fallback to environment variables
    return os.environ.get(key, default)


def get_database_client():
    """Get database client - Azure Cosmos DB or MongoDB fallback"""
    if azure_cosmos.is_available():
        return azure_cosmos
    return None


def get_ai_client():
    """Get AI client - Azure OpenAI or Google Gemini fallback"""
    if azure_openai.is_available():
        return azure_openai
    return None