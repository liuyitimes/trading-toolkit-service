# -*- coding: utf-8 -*-
"""接口日志功能边界测试

测试场景：
1. 正常请求 → 日志被记录
2. 空响应 → 不崩溃
3. 超大响应 → 被截断
4. 非 JSON 响应 → 原样记录
5. api-logs 接口本身 → 不被记录
6. api-logs 查询参数异常 → 防御性处理
7. 日志列表上限 → 自动淘汰

用法: python cloudrun/scripts/test_api_logs.py
"""
import sys
import os
import json

# 让脚本能 import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 在导入 app 前清空已有日志，确保测试干净
os.environ.setdefault('FLASK_APP', 'app')

from app import app, API_LOGS
from utils.response import api_response

# 模块级注册测试路由（Flask 首次请求后不允许再注册路由）
app.config['TESTING'] = True


@app.route('/__test_ping__')
def __test_ping():
    return api_response({'ok': True})


@app.route('/__test_empty__')
def __test_empty():
    return '', 204


@app.route('/__test_huge__')
def __test_huge():
    return api_response({'big': 'x' * 20000})


@app.route('/__test_html__')
def __test_html():
    return '<html><body>not json</body></html>', 200, {'Content-Type': 'text/html'}


_client = None


def make_client():
    global _client
    if _client is None:
        _client = app.test_client()
    return _client


def reset_logs():
    API_LOGS.clear()


def assert_true(cond, msg):
    status = 'PASS' if cond else 'FAIL'
    print(f'  [{status}] {msg}')
    if not cond:
        assert_true._failed = getattr(assert_true, '_failed', 0) + 1
    return cond


def test_normal_request_recorded():
    print('\n=== 1. 正常请求应被记录 ===')
    reset_logs()
    c = make_client()
    r = c.get('/__test_ping__')
    assert_true(r.status_code == 200, 'ping 返回 200')
    # 再请求 api-logs 查询
    r2 = c.get('/api/v1/admin/api-logs?page=1&page_size=10')
    body = r2.get_json()
    assert_true(body and body.get('success'), 'api-logs 返回成功')
    logs = body['data']['logs']
    assert_true(len(logs) == 1, f'记录了 1 条日志 (实际 {len(logs)})')
    if logs:
        l = logs[0]
        assert_true(l['method'] == 'GET', 'method = GET')
        assert_true(l['path'] == '/__test_ping__', 'path 正确')
        assert_true(l['status'] == 200, 'status = 200')
        assert_true(isinstance(l['duration'], (int, float)) and l['duration'] >= 0, 'duration 非负')
        assert_true(isinstance(l['response_body'], str), 'response_body 是字符串')
        assert_true('"ok"' in l['response_body'] or 'true' in l['response_body'], 'response_body 含正常内容')
        assert_true(l.get('truncated') is False, 'truncated = False')


def test_api_logs_not_recorded():
    print('\n=== 2. api-logs 查询本身不应被记录 ===')
    reset_logs()
    c = make_client()
    c.get('/__test_ping__')
    c.get('/api/v1/admin/api-logs?page=1')
    c.get('/api/v1/admin/api-logs/clear', method='POST')
    r = c.get('/api/v1/admin/api-logs?page=1&page_size=50')
    body = r.get_json()
    logs = body['data']['logs']
    paths = [l['path'] for l in logs]
    assert_true('/api/v1/admin/api-logs' not in paths, 'api-logs 查询未被记录')
    assert_true('/api/v1/admin/api-logs/clear' not in paths, 'api-logs/clear 未被记录')
    assert_true(len(logs) == 1, f'仅记录了 ping 这 1 条 (实际 {len(logs)})')


def test_large_response_truncated():
    print('\n=== 3. 超大响应应被截断 ===')
    reset_logs()
    c = make_client()
    c.get('/__test_huge__')
    r = c.get('/api/v1/admin/api-logs?page=1&page_size=10')
    body = r.get_json()
    logs = body['data']['logs']
    assert_true(len(logs) >= 1, '有日志')
    if logs:
        l = logs[0]
        assert_true(l.get('truncated') is True, 'truncated = True')
        assert_true('已截断' in (l['response_body'] or ''), 'response_body 含截断提示')
        assert_true(len(l['response_body']) < 20000, 'response_body 被截断到合理大小')


def test_non_json_response():
    print('\n=== 4. 非 JSON 响应应原样记录 ===')
    reset_logs()
    c = make_client()
    c.get('/__test_html__')
    r = c.get('/api/v1/admin/api-logs?page=1&page_size=10')
    body = r.get_json()
    logs = body['data']['logs']
    assert_true(len(logs) >= 1, '有日志')
    if logs:
        l = logs[0]
        assert_true(isinstance(l['response_body'], str), 'response_body 是字符串')
        # HTML 文本被原样保留
        assert_true('html' in l['response_body'].lower() or 'not json' in l['response_body'], 'HTML 内容被保留')


def test_invalid_query_params():
    print('\n=== 5. 异常查询参数应被防御性处理 ===')
    reset_logs()
    c = make_client()
    c.get('/__test_ping__')
    # page 为负数、page_size 超大、search 为 None
    r = c.get('/api/v1/admin/api-logs?page=-1&page_size=99999&search=')
    assert_true(r.status_code == 200, '异常参数返回 200 不崩溃')
    body = r.get_json()
    assert_true(body and body.get('success'), '返回 success=True')
    assert_true(body['data']['page'] >= 1, 'page 被修正为 >=1')
    assert_true(body['data']['page_size'] <= 200, 'page_size 被限制为 <=200')


def test_log_capacity_limit():
    print('\n=== 6. 日志列表上限应自动淘汰 ===')
    from app import MAX_API_LOGS
    print(f'  MAX_API_LOGS = {MAX_API_LOGS}')
    reset_logs()
    c = make_client()
    # 注入 220 条
    for i in range(MAX_API_LOGS + 20):
        c.get('/__test_ping__')
    assert_true(len(API_LOGS) == MAX_API_LOGS, f'列表稳定在上限 {MAX_API_LOGS} (实际 {len(API_LOGS)})')
    r = c.get('/api/v1/admin/api-logs?page=1&page_size=5')
    body = r.get_json()
    assert_true(body['data']['total'] == MAX_API_LOGS, f'total = {MAX_API_LOGS}')


def test_clear_endpoint():
    print('\n=== 7. 清空接口应清空日志 ===')
    reset_logs()
    c = make_client()
    c.get('/__test_ping__')
    c.get('/__test_ping__')
    assert_true(len(API_LOGS) == 2, f'清空前有 2 条 (实际 {len(API_LOGS)})')
    r = c.post('/api/v1/admin/api-logs/clear')
    assert_true(r.status_code == 200, '清空接口返回 200')
    assert_true(len(API_LOGS) == 0, '清空后日志列表为空')


def test_after_request_exception_safety():
    """模拟 after_request 内部异常不影响响应"""
    print('\n=== 8. after_request 内部异常不应影响响应 ===')
    reset_logs()
    c = make_client()
    # 正常请求验证响应不受日志逻辑影响
    r = c.get('/__test_ping__')
    assert_true(r.status_code == 200, 'ping 仍返回 200')
    body = r.get_json()
    assert_true(body and body.get('success'), '响应体正常')


if __name__ == '__main__':
    failed = 0
    assert_true._failed = 0
    tests = [
        test_normal_request_recorded,
        test_api_logs_not_recorded,
        test_large_response_truncated,
        test_non_json_response,
        test_invalid_query_params,
        test_log_capacity_limit,
        test_clear_endpoint,
        test_after_request_exception_safety,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f'  [ERROR] {t.__name__} 抛出异常: {e}')
            assert_true._failed += 1

    print(f'\n{"="*40}')
    total = len(tests)
    failed = getattr(assert_true, '_failed', 0)
    if failed == 0:
        print(f'全部通过 ({total} 个测试场景)')
        sys.exit(0)
    else:
        print(f'失败 {failed} 项')
        sys.exit(1)
