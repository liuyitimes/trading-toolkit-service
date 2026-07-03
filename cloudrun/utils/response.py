from flask import jsonify
from datetime import datetime, timezone, timedelta

# 中国标准时间时区
CST = timezone(timedelta(hours=8))

def api_response(data, cached=False, source='akshare', cache_expire_at=None):
    """统一成功响应"""
    return jsonify({
        'success': True,
        'data': data,
        'meta': {
            'cached': cached,
            'source': source,
            'cache_expire_at': cache_expire_at,
            'update_time': datetime.now(CST).isoformat()
        }
    })

def api_error(code, message, http_status=500):
    """统一错误响应"""
    response = jsonify({
        'success': False,
        'data': None,
        'error': {
            'code': code,
            'message': message
        }
    })
    response.status_code = http_status
    return response

# 错误码常量
class ErrorCode:
    INVALID_PARAMS = ('INVALID_PARAMS', 400)
    UNAUTHORIZED = ('UNAUTHORIZED', 401)
    RATE_LIMITED = ('RATE_LIMITED', 429)
    DATA_SOURCE_ERROR = ('DATA_SOURCE_ERROR', 502)
    DATA_SOURCE_TIMEOUT = ('DATA_SOURCE_TIMEOUT', 504)
    INTERNAL_ERROR = ('INTERNAL_ERROR', 500)
    NOT_FOUND = ('NOT_FOUND', 404)