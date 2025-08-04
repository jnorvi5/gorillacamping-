import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()

def test_home_get(client):
    rv = client.get('/')
    assert rv.status_code == 200

def test_blog_get(client):
    rv = client.get('/blog')
    assert rv.status_code == 200

def test_api_gear_get(client):
    """Test the /api/gear endpoint"""
    rv = client.get('/api/gear')
    assert rv.status_code == 200
    assert rv.is_json
    data = rv.get_json()
    assert isinstance(data, list)
    # Check for expected keys in the first item, if it exists
    if data:
        assert 'name' in data[0]
        assert 'affiliate_id' in data[0]

def test_api_guerilla_chat_post(client):
    """Test the /api/guerilla-chat endpoint"""
    rv = client.post('/api/guerilla-chat', json={'message': 'hello'})
    assert rv.status_code == 200
    assert rv.is_json
    data = rv.get_json()
    assert data['success'] is True
    assert 'response' in data
    assert isinstance(data['response'], str)

def test_api_subscribe_post(client):
    """Test the /api/subscribe endpoint"""
    # Test with a valid email
    rv = client.post('/api/subscribe', json={'email': 'test@example.com'})
    assert rv.status_code == 200
    data = rv.get_json()
    assert data['success'] is True

    # Test with an invalid email
    rv = client.post('/api/subscribe', json={'email': 'not-an-email'})
    assert rv.status_code == 400
    data = rv.get_json()
    assert data['success'] is False
    assert 'error' in data

    # Test subscribing with the same email again
    rv = client.post('/api/subscribe', json={'email': 'test@example.com'})
    assert rv.status_code == 200 # The app returns 200 but with an error message
    data = rv.get_json()
    assert data['success'] is False
    assert data.get('error') == 'Already subscribed'
