import pytest
import os
from unittest.mock import patch

@pytest.fixture
def client():
    # Mock the dependencies that require internet access
    with patch('app.knowledge_base', None), \
         patch('app.azure_cosmos', None), \
         patch('app.azure_openai', None), \
         patch('app.genai', None):
        from app import app
        app.config['TESTING'] = True
        return app.test_client()

def test_home_get(client):
    rv = client.get('/')
    assert rv.status_code == 200

def test_blog_get(client):
    rv = client.get('/blog')
    assert rv.status_code == 200

def test_health_endpoint(client):
    """Test the new Azure health check endpoint"""
    rv = client.get('/health')
    assert rv.status_code == 200
    data = rv.get_json()
    assert 'status' in data
    assert 'services' in data
    assert data['status'] == 'healthy'

def test_azure_config_endpoint(client):
    """Test the Azure configuration status endpoint"""
    rv = client.get('/azure/config')
    assert rv.status_code == 200
    data = rv.get_json()
    assert 'azure_services_available' in data
    assert 'environment_variables_configured' in data
