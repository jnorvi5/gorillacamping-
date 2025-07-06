import pytest
import os
from unittest.mock import patch, MagicMock

def test_azure_cosmos_initialization_without_credentials():
    """Test that Azure Cosmos DB initializes gracefully without credentials"""
    from azure_services import AzureCosmosDB
    cosmos = AzureCosmosDB()
    assert not cosmos.is_available()

def test_azure_openai_initialization_without_credentials():
    """Test that Azure OpenAI initializes gracefully without credentials"""
    from azure_services import AzureOpenAI
    openai_client = AzureOpenAI()
    assert not openai_client.is_available()

def test_get_config_value_fallback():
    """Test that get_config_value falls back to environment variables"""
    from azure_services import get_config_value
    
    with patch.dict(os.environ, {'TEST_KEY': 'test_value'}):
        value = get_config_value('TEST_KEY', 'default')
        assert value == 'test_value'
    
    # Test with default value
    value = get_config_value('NON_EXISTENT_KEY', 'default_value')
    assert value == 'default_value'

@patch('azure_services.AZURE_COSMOS_AVAILABLE', True)
def test_azure_cosmos_with_mocked_client():
    """Test Azure Cosmos DB with mocked client"""
    mock_client = MagicMock()
    mock_database = MagicMock()
    mock_client.get_database_client.return_value = mock_database
    
    with patch.dict(os.environ, {
        'AZURE_COSMOS_ENDPOINT': 'https://test.documents.azure.com',
        'AZURE_COSMOS_KEY': 'test_key'
    }), patch('azure_services.CosmosClient', return_value=mock_client):
        from azure_services import AzureCosmosDB
        cosmos = AzureCosmosDB()
        assert cosmos.is_available()
        assert cosmos.client == mock_client

@patch('azure_services.AZURE_OPENAI_AVAILABLE', True)
def test_azure_openai_with_mocked_client():
    """Test Azure OpenAI with mocked client"""
    mock_client = MagicMock()
    
    with patch.dict(os.environ, {
        'AZURE_OPENAI_ENDPOINT': 'https://test.openai.azure.com',
        'AZURE_OPENAI_API_KEY': 'test_key'
    }), patch('azure_services.OpenAIClient', return_value=mock_client):
        from azure_services import AzureOpenAI
        openai_client = AzureOpenAI()
        assert openai_client.is_available()
        assert openai_client.client == mock_client

@patch('azure_services.AZURE_OPENAI_AVAILABLE', True)
def test_azure_openai_generate_response():
    """Test Azure OpenAI response generation"""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Test response"
    mock_client.chat.completions.create.return_value = mock_response
    
    with patch.dict(os.environ, {
        'AZURE_OPENAI_ENDPOINT': 'https://test.openai.azure.com',
        'AZURE_OPENAI_API_KEY': 'test_key'
    }), patch('azure_services.OpenAIClient', return_value=mock_client):
        from azure_services import AzureOpenAI
        openai_client = AzureOpenAI()
        response = openai_client.generate_response("Test query", "Test context")
        assert response == "Test response"
        
        # Verify the API was called correctly
        mock_client.chat.completions.create.assert_called_once()
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args[1]['messages']
        assert len(messages) == 2
        assert messages[0]['role'] == 'system'
        assert messages[1]['role'] == 'user'
        assert 'Test query' in messages[1]['content']