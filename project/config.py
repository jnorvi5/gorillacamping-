import os

class Config:
    """Flask configuration variables."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'gorilla-secret-2025')
    APPLICATIONINSIGHTS_CONNECTION_STRING = os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING')
    MONGODB_URI = os.environ.get('MONGODB_URI')

    # AI Provider settings
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://localhost:11434')
    AI_PROVIDER = os.environ.get('AI_PROVIDER', 'azure')  # 'azure', 'openai', 'gemini', 'ollama'

    # Azure specific variables
    AZURE_OPENAI_ENDPOINT = os.environ.get('AZURE_OPENAI_ENDPOINT', 'https://jnorv-md6rseps-eastus2.cognitiveservices.azure.com/')
    AZURE_OPENAI_KEY = os.environ.get('AZURE_OPENAI_KEY')
    AZURE_OPENAI_DEPLOYMENT_NAME = os.environ.get('AZURE_OPENAI_DEPLOYMENT_NAME', 'geurillathegorilla')

    # Other services
    STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY')
    STATIC_SITE_URL = os.environ.get('STATIC_SITE_URL', 'https://gorillacamping.site')
    ADMIN_API_KEY = os.environ.get('ADMIN_API_KEY')
    MAILERLITE_API_KEY = os.environ.get('MAILERLITE_API_KEY')
