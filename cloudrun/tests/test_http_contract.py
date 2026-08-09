import json
from pathlib import Path
import re
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as backend_app

CST = timezone(timedelta(hours=8))


def _seed_lof_execution_db():
    """In-memory registry: SH generic rules, one stale-status fund, one SZ gap."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from models.database import Base
    from models.lof_execution import (
        LofExecutionEvidence,
        LofExecutionFund,
        LofExecutionRule,
    )

    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()
    evidence = LofExecutionEvidence(
        source_kind='manager_announcement',
        source_identifier='prospectus-2026',
        source_title='上证 LOF 招募说明书（2026 修订）',
        source_url='https://example.test/prospectus',
        applies_to='sh_all_listed_lof',
        effective_from=datetime(2026, 1, 1).date(),
        verified_at=datetime(2026, 8, 7, 9, 30),
        excerpt='场内申购确认 T+1，最低申购金额 1000 元。',
    )
    db.add(evidence)
    db.flush()
    db.add_all([
        LofExecutionRule(
            exchange='sh', share_class='listed',
            field_key='subscription_confirmation', value_text='T+1',
            status='verified', source_priority=10, evidence_id=evidence.id,
            effective_from=datetime(2026, 1, 1).date(),
        ),
        LofExecutionRule(
            exchange='sh', share_class='listed',
            field_key='subscription_minimum', value_text='1000 元',
            numeric_value=1000, unit='元',
            status='verified', source_priority=10, evidence_id=evidence.id,
            effective_from=datetime(2026, 1, 1).date(),
        ),
    ])
    db.add_all([
        LofExecutionFund(
            fund_code='501001', exchange='sh', share_class='listed',
            discovery_status='partial',
            discovery_reason='已应用上交所通用场内规则；基金专项规则待公告增量补充',
            subscription_status='open', redemption_status='open',
            status_checked_at=datetime(2026, 8, 7, 16, 0),
            status_source_url='https://example.test/status',
        ),
        LofExecutionFund(
            fund_code='501003', exchange='sh', share_class='listed',
            discovery_status='partial',
            discovery_reason='已应用上交所通用场内规则；基金专项规则待公告增量补充',
            subscription_status='open', redemption_status='open',
            status_checked_at=datetime(2026, 8, 6, 16, 0),
            status_source_url='https://example.test/status',
        ),
        LofExecutionFund(
            fund_code='161001', exchange='sz', share_class='listed',
            discovery_status='unavailable',
            discovery_reason='尚未取得满足口径的深市或基金专项场内规则证据',
        ),
    ])
    db.commit()
    return session_factory


def _lof_quote(name, price, valuation):
    values = [''] * 82
    values[1] = name
    values[3] = str(price)
    values[30] = '20260807150000'
    values[32] = '1'
    values[36] = '1000'
    values[37] = '100'
    values[61] = 'LOF'
    values[81] = str(valuation)
    return values


def _patch_lof_list_upstream(monkeypatch, session_factory, tmp_path):
    monkeypatch.setenv('LOF_DETAIL_DATA_DIR', str(tmp_path))
    monkeypatch.setattr(
        'services.lof_fund._now',
        lambda: datetime(2026, 8, 7, 15, 30, tzinfo=CST),
    )
    monkeypatch.setattr(
        'services.lof_fund._fetch_em_lof_rows',
        lambda: [
            {'f12': '501001', 'f13': '1', 'f14': '上证 LOF'},
            {'f12': '501003', 'f13': '1', 'f14': '陈旧状态 LOF'},
            {'f12': '161001', 'f13': '0', 'f14': '深证 LOF'},
        ],
    )
    monkeypatch.setattr(
        'services.lof_fund._fetch_tencent_quotes',
        lambda rows: {
            '501001': _lof_quote('上证 LOF', 1.1, 1.0),
            '501003': _lof_quote('陈旧状态 LOF', 1.09, 1.0),
            '161001': _lof_quote('深证 LOF', 1.08, 1.0),
        },
    )
    monkeypatch.setattr('services.lof_fund._load_execution_rules', lambda: {})
    monkeypatch.setattr(
        'services.lof_fund._five_day_average_turnover',
        lambda code: None,
    )
    monkeypatch.setattr('models.database.SessionLocal', session_factory)


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


def test_lof_list_http_contract_exposes_execution_rules(monkeypatch, tmp_path):
    session_factory = _seed_lof_execution_db()
    _patch_lof_list_upstream(monkeypatch, session_factory, tmp_path)

    response = backend_app.app.test_client().get('/api/v1/lof/list?refresh=true')

    assert response.status_code == 200
    payload = response.get_json()
    items = {item['code']: item for item in payload['data']}
    verified = items['501001']
    stale = items['501003']
    gap = items['161001']

    timing = verified['execution']['settlement_timing']
    assert timing['subscription_confirmation']['status'] == 'verified'
    assert timing['subscription_confirmation']['timing_text'] == 'T+1'
    assert timing['subscription_confirmation']['source']['url'].endswith(
        '/prospectus'
    )
    assert timing['redemption_payment']['status'] == 'unavailable'
    minimum = verified['execution']['minimum_order']
    assert minimum['subscription']['status'] == 'verified'
    assert minimum['subscription']['display_text'] == '1000 元'
    assert minimum['subscription']['unit'] == '元'
    assert verified['subscription_open'] is True

    assert stale['subscription_open'] is False
    assert stale['limit_status'] == '待核验'
    assert (
        stale['execution']['settlement_timing']['subscription_confirmation'][
            'status'
        ]
        == 'verified'
    )

    assert gap['execution']['settlement_timing']['subscription_confirmation'][
        'status'
    ] == 'unavailable'
    assert gap['execution']['minimum_order']['subscription']['status'] == (
        'unavailable'
    )


def test_lof_detail_http_contract_preserves_execution_rule_sources(
    monkeypatch, tmp_path
):
    session_factory = _seed_lof_execution_db()
    _patch_lof_list_upstream(monkeypatch, session_factory, tmp_path)
    monkeypatch.setattr(
        'services.lof_detail.get_observations', lambda code: []
    )
    monkeypatch.setattr(
        'services.lof_detail._holdings_for',
        lambda code, today=None: {
            'available': False,
            'status': 'unavailable',
            'reason': 'test fixture',
            'top_holdings': [],
        },
    )

    response = backend_app.app.test_client().get(
        '/api/v1/lof/501001/detail'
    )

    assert response.status_code == 200
    execution = response.get_json()['data']['execution']
    assert (
        execution['settlement_timing']['subscription_confirmation']['status']
        == 'verified'
    )
    assert (
        execution['settlement_timing']['subscription_confirmation'][
            'timing_text'
        ]
        == 'T+1'
    )
    assert execution['minimum_order']['subscription']['display_text'] == (
        '1000 元'
    )
    assert execution['minimum_order']['redemption']['status'] == 'unavailable'
    assert (
        execution['settlement_timing']['redemption_payment']['reason']
        == '已应用上交所通用场内规则；基金专项规则待公告增量补充'
    )
