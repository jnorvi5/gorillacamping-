import pytest
from app import app, db
from unittest.mock import patch, MagicMock
import json

import stripe

@pytest.fixture
def client():
    app.config['TESTING'] = True
    stripe.api_key = "sk_test_123" # Set a dummy key for testing
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
    assert data.get('error') == 'Email already in use.'

def test_free_tier_rate_limiting(client):
    """Test that a free user gets cut off after the limit."""
    # In-memory db is a list, so we can check it
    if isinstance(db, dict):
        db['users'] = [] # Reset users for this test

    # Simulate 5 interactions
    for i in range(5):
        rv = client.post('/api/guerilla-chat', json={'message': f'hello {i}'})
        assert rv.status_code == 200
        data = rv.get_json()
        assert data.get('upgrade_required') is not True

    # The 6th interaction should trigger the upgrade message
    rv = client.post('/api/guerilla-chat', json={'message': 'hello 6'})
    assert rv.status_code == 200
    data = rv.get_json()
    assert data.get('upgrade_required') is True
    assert "upgrade" in data['response'].lower() or "inner circle" in data['response'].lower()

@patch('app.stripe.checkout.Session.create')
@patch('app.stripe.Customer.create')
def test_create_checkout_session(mock_customer_create, mock_session_create, client):
    """Test the Stripe checkout session creation endpoint."""
    mock_customer_create.return_value = MagicMock(id='cus_123')
    mock_session_create.return_value = MagicMock(id='cs_test_123')

    # Set a cookie to simulate a visitor
    client.set_cookie('visitor_id', 'test_visitor_123')
    rv = client.post('/api/create-checkout-session')

    assert rv.status_code == 200
    data = rv.get_json()
    assert data['id'] == 'cs_test_123'

@patch('app.stripe.Webhook.construct_event')
def test_stripe_webhook_upgrades_tier(mock_construct_event, client):
    """Test that the webhook correctly upgrades a user to premium."""
    if isinstance(db, dict):
        db['users'] = [] # Reset users

    # Create a user to be upgraded
    client.post('/api/guerilla-chat', json={'message': 'create user'})
    user = db['users'][0]
    assert user['tier'] == 'free'

    # Mock the Stripe event payload
    mock_event = {
        'type': 'checkout.session.completed',
        'data': {
            'object': {
                'metadata': {
                    'user_id': user['_id']
                }
            }
        }
    }
    mock_construct_event.return_value = mock_event

    # Send the mock event to the webhook
    rv = client.post('/api/stripe-webhook',
                     data=json.dumps(mock_event),
                     headers={'Stripe-Signature': 'mock_sig'})

    assert rv.status_code == 200

    # Check that the user was upgraded
    upgraded_user = db['users'][0]
    assert upgraded_user['tier'] == 'premium'
