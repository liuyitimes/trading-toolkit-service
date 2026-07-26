from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as backend_app


def test_healthz_exposes_only_minimal_status():
    response = backend_app.app.test_client().get('/healthz')

    assert response.status_code == 200
    assert response.get_json()['data'] == {'status': 'ok'}


def test_admin_operations_are_disabled_by_default():
    response = backend_app.app.test_client().post('/api/v1/admin/cache/clear')

    assert response.status_code == 404
    assert response.get_json()['error']['code'] == 'NOT_FOUND'


def test_cors_allows_only_configured_local_origins():
    client = backend_app.app.test_client()

    allowed = client.get('/healthz', headers={'Origin': 'http://localhost:5173'})
    blocked = client.get('/healthz', headers={'Origin': 'https://untrusted.example'})

    assert allowed.headers['Access-Control-Allow-Origin'] == 'http://localhost:5173'
    assert 'Access-Control-Allow-Origin' not in blocked.headers


def test_legacy_health_endpoint_uses_minimal_public_response():
    response = backend_app.app.test_client().get('/api/health')

    assert response.status_code == 200
    assert response.get_json()['data'] == {'status': 'ok'}
