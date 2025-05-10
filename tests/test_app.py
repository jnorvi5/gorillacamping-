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
