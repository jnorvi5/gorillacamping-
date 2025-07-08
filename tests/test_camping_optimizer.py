import pytest
import json
from app_fixed import app, calculate_camping_score, get_bluetooth_device_recommendations

@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()

def test_camping_optimizer_page(client):
    """Test that the camping optimizer page loads correctly"""
    rv = client.get('/optimizer')
    assert rv.status_code == 200
    assert b'Gorilla Camping Optimizer' in rv.data

def test_calculate_camping_score():
    """Test the camping score calculation algorithm"""
    test_preferences = {
        'setup_type': 'van',
        'power_type': 'solar',
        'available_amps': 30,
        'location_type': 'boondocking',
        'budget_range': 'medium'
    }
    
    result = calculate_camping_score(test_preferences)
    
    assert 'score' in result
    assert 'recommendations' in result
    assert 'optimization_tips' in result
    assert isinstance(result['score'], int)
    assert result['score'] >= 0 and result['score'] <= 100
    assert len(result['recommendations']) > 0
    assert len(result['optimization_tips']) > 0

def test_bluetooth_device_recommendations():
    """Test Bluetooth device recommendation system"""
    devices = get_bluetooth_device_recommendations('van', 'solar')
    
    assert isinstance(devices, list)
    assert len(devices) > 0
    
    # Check that each device has required fields
    for device in devices:
        assert 'device' in device
        assert 'reason' in device
        assert 'compatibility' in device

def test_preferences_api(client):
    """Test saving and retrieving user preferences"""
    test_preferences = {
        'setup_type': 'tent',
        'power_type': 'generator',
        'available_amps': 15,
        'location_type': 'campground',
        'budget_range': 'low'
    }
    
    # Test saving preferences
    rv = client.post('/api/preferences', 
                     data=json.dumps(test_preferences),
                     content_type='application/json')
    
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert data['success'] == True
    assert 'camping_score' in data

def test_pro_upgrade_api(client):
    """Test Pro upgrade functionality"""
    # Test with valid upgrade code
    rv = client.post('/api/pro-upgrade',
                     data=json.dumps({'upgrade_code': 'DEMO123'}),
                     content_type='application/json')
    
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert data['success'] == True
    assert 'features' in data
    
    # Test with invalid upgrade code
    rv = client.post('/api/pro-upgrade',
                     data=json.dumps({'upgrade_code': 'INVALID'}),
                     content_type='application/json')
    
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert data['success'] == False

def test_bluetooth_scan_api(client):
    """Test Bluetooth scanning simulation"""
    rv = client.post('/api/bluetooth-scan',
                     content_type='application/json')
    
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert data['success'] == True
    assert 'devices' in data
    assert isinstance(data['devices'], list)

def test_optimize_api_with_preferences(client):
    """Test the enhanced AI optimization with preferences"""
    test_data = {
        'query': 'What solar panel should I get for my van?',
        'preferences': {
            'setup_type': 'van',
            'power_type': 'solar',
            'available_amps': 30,
            'budget_range': 'medium'
        }
    }
    
    rv = client.post('/api/optimize',
                     data=json.dumps(test_data),
                     content_type='application/json')
    
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert data['success'] == True
    assert 'response' in data
    assert 'ai_model' in data

def test_different_setup_types():
    """Test scoring for different setup types"""
    setups = ['van', 'tent', 'rv', 'fifth_wheel']
    
    for setup in setups:
        preferences = {
            'setup_type': setup,
            'power_type': 'solar',
            'available_amps': 30,
            'location_type': 'mixed',
            'budget_range': 'medium'
        }
        
        result = calculate_camping_score(preferences)
        assert result['score'] > 0
        assert len(result['recommendations']) > 0

def test_power_type_variations():
    """Test different power configurations"""
    power_types = ['solar', 'generator', 'shore_power', 'battery', 'hybrid']
    
    for power_type in power_types:
        preferences = {
            'setup_type': 'van',
            'power_type': power_type,
            'available_amps': 30,
            'location_type': 'boondocking',
            'budget_range': 'medium'
        }
        
        result = calculate_camping_score(preferences)
        assert result['score'] > 0
        
        # Test Bluetooth recommendations for this power type
        devices = get_bluetooth_device_recommendations('van', power_type)
        assert len(devices) > 0