from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get('/api/health')
    assert response.status_code == 200
    data = response.json()
    assert data['ok'] is True
    assert 'MEMBRA' in data['app']


def test_dashboard_endpoint():
    response = client.get('/api/dashboard')
    assert response.status_code == 200
    data = response.json()
    assert 'counts' in data


def test_proofbook_endpoint():
    response = client.get('/api/proofbook')
    assert response.status_code == 200
    data = response.json()
    assert 'proofbook_entries' in data or isinstance(data, dict)


def test_marketplace_page_loads():
    response = client.get('/marketplace')
    assert response.status_code == 200
    assert 'Marketplace' in response.text


def test_inventory_page_loads():
    response = client.get('/inventory')
    assert response.status_code == 200
    assert 'Inventory' in response.text or 'Picture' in response.text
