import json
from pathlib import Path
import re
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as backend_app


def test_contract_endpoints_match_flask_routes():
    contract_path = Path(__file__).resolve().parents[2] / 'contracts' / 'http-api.json'
    contract = json.loads(contract_path.read_text(encoding='utf-8'))
    routes = {
        (re.sub(r'<(?:[^:<>]+:)?([^<>]+)>', r':\1', rule.rule), method)
        for rule in backend_app.app.url_map.iter_rules()
        for method in rule.methods - {'HEAD', 'OPTIONS'}
    }

    missing = [
        endpoint
        for endpoint in contract['endpoints']
        if (endpoint['path'], endpoint['method']) not in routes
    ]

    assert missing == []


def test_new_listed_cold_cache_returns_snapshot_without_waiting_for_upstream(monkeypatch):
    snapshot = [
        {
            'bond_code': '113708',
            'bond_name': '曙26转债',
            'list_date': '2026-08-06',
            'gain_since_listing': 46.72,
            'three_day_gain': 46.72,
            'three_day_stage': 1,
        }
    ]

    monkeypatch.setattr(backend_app.cache, 'get', lambda key: None)
    monkeypatch.setattr(
        'services.convertible_bond._read_new_listed_snapshot',
        lambda: snapshot,
    )
    monkeypatch.setattr(
        'services.cache._maybe_trigger_background_refresh',
        lambda *args: (_ for _ in ()).throw(
            AssertionError('已有快照时不应触发上游刷新')
        ),
    )

    def unexpected_sync(*args, **kwargs):
        raise AssertionError('冷缓存请求不应同步访问上游')

    monkeypatch.setattr(backend_app.factory, 'get_with_fallback', unexpected_sync)

    response = backend_app.app.test_client().get(
        '/api/v1/convertible/new-listed'
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['data'] == snapshot
    assert payload['meta']['source'] == 'snapshot'
    assert payload['meta']['cached'] is True


def test_heavy_endpoint_uses_persisted_snapshot_without_waiting_for_upstream(monkeypatch):
    snapshot = [{'代码': '161725', '溢价率': 1.2}]
    monkeypatch.setattr(backend_app.cache, 'get', lambda key: None)
    monkeypatch.setattr(backend_app.cache, 'get_snapshot', lambda key: snapshot)
    monkeypatch.setattr(
        'services.cache._maybe_trigger_background_refresh',
        lambda *args: None,
    )

    def unexpected_sync(*args, **kwargs):
        raise AssertionError('快照命中时不应同步访问上游')

    monkeypatch.setattr(backend_app.factory, 'get_with_fallback', unexpected_sync)

    response = backend_app.app.test_client().get('/api/v1/lof/list')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['data'] == snapshot
    assert payload['meta']['source'] == 'snapshot'
    assert payload['meta']['cached'] is True


def test_heavy_endpoint_returns_warming_payload_on_cold_start(monkeypatch):
    monkeypatch.setattr(backend_app.cache, 'get', lambda key: None)
    monkeypatch.setattr(backend_app.cache, 'get_snapshot', lambda key: None)
    monkeypatch.setattr(
        'services.cache._maybe_trigger_background_refresh',
        lambda *args: None,
    )
    monkeypatch.setattr(
        backend_app.factory,
        'get_with_fallback',
        lambda *args, **kwargs: (None, 'none'),
    )

    response = backend_app.app.test_client().get('/api/v1/convertible/signals')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['data'] == {
        'double_low': [],
        'force_redeem': [],
        'discount': [],
        'down_revised': [],
    }
    assert payload['meta']['source'] == 'warming'
    assert payload['meta']['cached'] is True


def test_heavy_endpoint_does_not_wait_for_background_refresh(monkeypatch):
    snapshot = [{'代码': '161725', '溢价率': 1.2}]
    monkeypatch.setattr(backend_app.cache, 'get', lambda key: None)
    monkeypatch.setattr(backend_app.cache, 'get_snapshot', lambda key: snapshot)
    monkeypatch.setattr(
        'services.cache._maybe_trigger_background_refresh',
        lambda *args: time.sleep(0.3),
    )

    started = time.monotonic()
    response = backend_app.app.test_client().get('/api/v1/lof/list')

    assert response.status_code == 200
    assert time.monotonic() - started < 0.15
