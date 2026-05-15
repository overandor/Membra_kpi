from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get('/api/health')
    assert response.status_code == 200
    data = response.json()
    assert data['ok'] is True


def test_ready_endpoint():
    response = client.get('/api/ready')
    assert response.status_code == 200
    data = response.json()
    assert 'counts' in data


def test_dashboard_endpoint():
    response = client.get('/api/dashboard')
    assert response.status_code == 200
    data = response.json()
    assert 'counts' in data
