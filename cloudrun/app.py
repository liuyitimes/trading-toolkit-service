# -*- coding: utf-8 -*-
"""旺财百宝箱 — Flask 后端 API

统一响应格式、分级缓存、多数据源降级、接口限流、结构化日志。
"""

import logging
import os
import time
import traceback
from functools import wraps

from flask import Flask, request
from flask_cors import CORS
from datetime import datetime, timezone, timedelta

from services.factory import create_default_factory
from services.cache import (
    get_cache_manager,
    get_cache_ttl,
    build_cache_key,
    get_with_cache_lock,
    get_with_swr,
    warmup_cache,
)
from services.lof_arbitrage import get_arbitrage_prediction as _get_lof_arbitrage_prediction
from services.lof_detail import get_lof_detail
from services.hk_ipo import refresh_hk_ipo_cache
from utils.response import api_response, api_error, ErrorCode
from utils.limiting import limit
from utils.logging import setup_logging


def init_sentry():
    dsn = os.environ.get('SENTRY_DSN', '').strip()
    if not dsn:
        return
    import sentry_sdk
    sentry_sdk.init(dsn=dsn, traces_sample_rate=0.0)

# ==================== 初始化 ====================

app = Flask(__name__)
init_sentry()


def _cors_origins():
    configured = os.environ.get(
        'CORS_ALLOWED_ORIGINS',
        'http://localhost:5173,http://127.0.0.1:5173',
    )
    return [origin.strip() for origin in configured.split(',') if origin.strip()]


CORS(app, origins=_cors_origins(), supports_credentials=False)

# 结构化日志
logger = setup_logging(app)

# 数据源工厂（直连单源模式）
factory = create_default_factory()

# 缓存管理器
cache = get_cache_manager()

logger.info(f'后端启动完成，主数据源: {factory._primary_name}，缓存后端: {cache.backend_type}')

# ==================== 请求日志 ====================

CST = timezone(timedelta(hours=8))
API_LOGS = []
MAX_API_LOGS = 200


@app.before_request
def log_request_start():
    """记录请求开始时间到 request 上下文（任何异常都不应影响请求本身）"""
    try:
        if not request.path.startswith('/api/v1/admin/api-logs'):
            request._start_time = time.time()
    except Exception:
        pass


@app.after_request
def log_request_end(response):
    """记录请求日志（任何异常都不应影响响应本身）"""
    try:
        if not hasattr(request, '_start_time'):
            return response
        if request.path.startswith('/api/v1/admin/api-logs'):
            return response

        start = getattr(request, '_start_time', None) or time.time()
        duration = round((time.time() - start) * 1000, 1)

        log_entry = {
            'id': len(API_LOGS) + 1,
            'time': datetime.now(CST).strftime('%H:%M:%S.%f')[:-3],
            'method': request.method,
            'path': request.full_path if request.query_string else request.path,
            'status': response.status_code,
            'duration': duration,
        }

        API_LOGS.append(log_entry)
        if len(API_LOGS) > MAX_API_LOGS:
            API_LOGS.pop(0)
    except Exception as e:
        # 日志记录失败绝不影响响应
        try:
            logger.warning(f'请求日志记录失败: {e}')
        except Exception:
            pass
    return response


# ==================== 通用数据获取 ====================

def fetch_with_cache(data_type: str, method_name: str, force_refresh=False, use_swr=True, **kwargs):
    """通用数据获取：缓存 → 数据源降级

    Args:
        data_type: 缓存类型（如 convertible_list、lof_list）
        method_name: 数据源方法名
        force_refresh: 是否强制刷新
        use_swr: 是否使用 stale-while-revalidate 模式（有缓存时立即返回，后台异步刷新）
        **kwargs: 传递给数据源方法的参数

    Returns:
        (data, source, cached) 元组
    """
    cache_key = build_cache_key(data_type.replace('_', ':'), 'data',
                                 **{k: str(v) for k, v in kwargs.items() if v is not None})
    ttl = get_cache_ttl(data_type)

    def _fetch():
        data, source = factory.get_with_fallback(method_name, **kwargs)
        return data

    # 强制刷新
    if force_refresh:
        data, source = factory.get_with_fallback(method_name, **kwargs)
        if data is not None:
            cache.set(cache_key, data, ttl)
        return data, source or 'unknown', False

    # SWR 模式：有缓存立即返回，后台异步刷新
    if use_swr:
        cached = cache.get(cache_key)
        if cached is not None:
            # 有缓存，后台异步刷新
            from services.cache import _maybe_trigger_background_refresh
            _maybe_trigger_background_refresh(cache_key, _fetch, ttl, 0.7)
            return cached, 'cache', True

    # 普通模式：先查缓存，未命中则同步获取
    cached = cache.get(cache_key)
    if cached is not None:
        return cached, 'cache', True

    data, source = factory.get_with_fallback(method_name, **kwargs)
    if data is not None:
        cache.set(cache_key, data, ttl)
        return data, source or 'unknown', False

    return None, 'none', False


# ==================== 市场概览 API ====================

@app.route('/api/v1/market/overview')
@limit(60)
def market_overview():
    """综合市场概览"""
    try:
        result = {}

        # 可转债温度
        data, source, cached = fetch_with_cache(
            'convertible_temperature', 'get_convertible_temperature')
        result['convertible_bond'] = data or {}

        # LOF 概览
        data, _, _ = fetch_with_cache('lof_summary', 'get_lof_summary')
        result['lof_fund'] = data or {}

        # 市场情绪
        data, _, _ = fetch_with_cache('market_sentiment', 'get_market_sentiment')
        result['market_sentiment'] = data or {}

        # 资金流向
        data, _, _ = fetch_with_cache('fund_flow', 'get_fund_flow')
        result['fund_flow'] = data or {}

        return api_response(result, source=source, cached=cached)
    except Exception as e:
        logger.error(f'市场概览异常: {e}')
        return api_error(*ErrorCode.DATA_SOURCE_ERROR)


@app.route('/api/v1/market/sentiment')
@limit(60)
def market_sentiment():
    """市场情绪"""
    force = request.args.get('refresh', '').lower() == 'true'
    data, source, cached = fetch_with_cache(
        'market_sentiment', 'get_market_sentiment', force_refresh=force)
    if data is None:
        return api_error(*ErrorCode.DATA_SOURCE_ERROR)
    return api_response(data, source=source, cached=cached)


@app.route('/api/v1/market/fund-flow')
@limit(60)
def fund_flow():
    """资金流向"""
    force = request.args.get('refresh', '').lower() == 'true'
    data, source, cached = fetch_with_cache(
        'fund_flow', 'get_fund_flow', force_refresh=force)
    if data is None:
        return api_error(*ErrorCode.DATA_SOURCE_ERROR)
    return api_response(data, source=source, cached=cached)


# ==================== 可转债 API ====================

@app.route('/api/v1/convertible/list')
@limit(60)
def convertible_list():
    """可转债列表"""
    force = request.args.get('refresh', '').lower() == 'true'
    kwargs = {
        'exchange': request.args.get('exchange'),
        'sort': request.args.get('sort', 'double_low'),
        'min_price': request.args.get('min_price', type=float),
        'max_price': request.args.get('max_price', type=float),
        'max_premium': request.args.get('max_premium', type=float),
        'page': request.args.get('page', 1, type=int),
        'page_size': request.args.get('page_size', 100, type=int),
    }
    # 过滤 None 值
    kwargs = {k: v for k, v in kwargs.items() if v is not None}

    data, source, cached = fetch_with_cache(
        'convertible_list', 'get_convertible_list', force_refresh=force, **kwargs)

    if data is None:
        return api_error(*ErrorCode.DATA_SOURCE_ERROR)
    return api_response(data, source=source, cached=cached)


@app.route('/api/v1/convertible/signals')
@limit(60)
def convertible_signals():
    """可转债信号"""
    force = request.args.get('refresh', '').lower() == 'true'
    data, source, cached = fetch_with_cache(
        'convertible_signals', 'get_convertible_signals', force_refresh=force)
    if data is None:
        return api_error(*ErrorCode.DATA_SOURCE_ERROR)
    return api_response(data, source=source, cached=cached)


@app.route('/api/v1/convertible/temperature')
@limit(60)
def convertible_temperature():
    """可转债市场温度"""
    force = request.args.get('refresh', '').lower() == 'true'
    data, source, cached = fetch_with_cache(
        'convertible_temperature', 'get_convertible_temperature', force_refresh=force)
    if data is None:
        return api_error(*ErrorCode.DATA_SOURCE_ERROR)
    return api_response(data, source=source, cached=cached)


@app.route('/api/v1/convertible/detail/<code>')
@limit(60)
def convertible_detail(code):
    """可转债详情"""
    force = request.args.get('refresh', '').lower() == 'true'
    data, source, cached = fetch_with_cache(
        'convertible_detail', 'get_convertible_detail', force_refresh=force, code=code)
    if data is None:
        return api_error(*ErrorCode.NOT_FOUND, f'可转债 {code} 不存在', 404)
    return api_response(data, source=source, cached=cached)


@app.route('/api/v1/convertible/pending')
@limit(30)
def convertible_pending():
    """待发/配售可转债列表"""
    force = request.args.get('refresh', '').lower() == 'true'
    data, source, cached = fetch_with_cache(
        'convertible_pending', 'get_convertible_pending', force_refresh=force)
    if data is None:
        return api_response([], source='none', cached=False)
    from services.convertible_bond import schedule_pending_enrichment
    schedule_pending_enrichment(data)
    return api_response(data, source=source, cached=cached)


@app.route('/api/v1/convertible/new-listed')
@limit(30)
def convertible_new_listed():
    """今年上市新债表现列表"""
    force = request.args.get('refresh', '').lower() == 'true'
    data, source, cached = fetch_with_cache(
        'convertible_new_listed', 'get_convertible_new_listed', force_refresh=force)
    if data is None:
        return api_response([], source='none', cached=False)
    return api_response(data, source=source, cached=cached)


# ==================== 配售公告 API ====================

@app.route('/api/v1/placement/sync', methods=['POST'])
@limit(5)
def placement_sync():
    """触发公告同步（从巨潮资讯抓取发行结果公告）"""
    days_back = int(request.args.get('days', 30))
    result = factory._primary.sync_placement_announcements(days_back=days_back)
    if 'error' in result:
        return api_error('DATA_SOURCE_ERROR', result['error'], 502)
    return api_response(result, source='cninfo', cached=False)


@app.route('/api/v1/placement/list')
@limit(60)
def placement_list():
    """查询已入库的配售结果"""
    asset_type = request.args.get('type', '')  # bond / stock / 空=全部
    from services.announcement_parser import get_all_placements
    data = get_all_placements(asset_type=asset_type or None)
    return api_response(data, source='local', cached=False)


# ==================== LOF 基金 API ====================

@app.route('/api/v1/lof/list')
@limit(60)
def lof_list():
    """LOF 基金列表"""
    force = request.args.get('refresh', '').lower() == 'true'
    data, source, cached = fetch_with_cache(
        'lof_list', 'get_lof_list', force_refresh=force)
    if data is None:
        return api_error(*ErrorCode.DATA_SOURCE_ERROR)
    return api_response(data, source=source, cached=cached)


@app.route('/api/v1/lof/opportunities')
@limit(60)
def lof_opportunities():
    """LOF 套利机会"""
    force = request.args.get('refresh', '').lower() == 'true'
    data, source, cached = fetch_with_cache(
        'lof_opportunities', 'get_lof_opportunities', force_refresh=force)
    if data is None:
        return api_error(*ErrorCode.DATA_SOURCE_ERROR)
    return api_response(data, source=source, cached=cached)


@app.route('/api/v1/lof/summary')
@limit(60)
def lof_summary():
    """LOF 市场概览"""
    force = request.args.get('refresh', '').lower() == 'true'
    data, source, cached = fetch_with_cache(
        'lof_summary', 'get_lof_summary', force_refresh=force)
    if data is None:
        return api_error(*ErrorCode.DATA_SOURCE_ERROR)
    return api_response(data, source=source, cached=cached)


@app.route('/api/v1/lof/<code>/detail')
@limit(60)
def lof_detail(code):
    """LOF arbitrage-research detail with dated evidence metadata."""
    try:
        data = get_lof_detail(code)
    except Exception as exc:
        logger.error('LOF detail failed for %s: %s', code, exc)
        return api_error(*ErrorCode.DATA_SOURCE_ERROR)
    if data is None:
        return api_error('NOT_FOUND', f'LOF {code} not found', 404)
    return api_response(data, source='direct', cached=False)


@app.route('/api/v1/lof/<code>/share-history')
@limit(60)
def lof_share_history(code):
    """LOF 基金场内份额历史（7 日）"""
    from services.lof_arbitrage import fetch_share_history
    current_amount = request.args.get('amount', 0, type=float)
    current_premium = request.args.get('premium', 0, type=float)
    try:
        result = fetch_share_history(code, current_amount, current_premium)
        if not result or not result.get('history'):
            return api_error('NOT_FOUND', f'LOF {code} 份额历史数据为空', 404)
        return api_response(result, source=result.get('source', 'unknown'), cached=False)
    except Exception as e:
        logger.error(f'LOF {code} 份额历史异常: {e}')
        return api_error(*ErrorCode.DATA_SOURCE_ERROR)


@app.route('/api/v1/lof/<code>/arbitrage-predict')
@limit(60)
def lof_arbitrage_predict(code):
    """LOF 套利资金预测（7 日数据 + 明日预测 + 出逃风险）"""
    current_amount = request.args.get('amount', 0, type=float)
    current_premium = request.args.get('premium', 0, type=float)
    limit_status = request.args.get('limit_status', '不限')
    limit_amount = request.args.get('limit_amount', 0, type=float)
    try:
        result = _get_lof_arbitrage_prediction(
            code=code,
            current_amount=current_amount,
            current_premium=current_premium,
            limit_status=limit_status,
            limit_amount=limit_amount,
        )
        return api_response(result, source=result.get('data_source', 'unknown'), cached=False)
    except Exception as e:
        logger.error(f'LOF {code} 套利预测异常: {e}')
        return api_error(*ErrorCode.DATA_SOURCE_ERROR)


# ==================== 港股 IPO API ====================

@app.route('/api/v1/hkipo/list')
@limit(60)
def hkipo_list():
    """港股 IPO 列表"""
    force = request.args.get('refresh', '').lower() == 'true'
    if force:
        refresh_hk_ipo_cache(force=True)
    data, source, cached = fetch_with_cache(
        'hk_ipo_list', 'get_hk_ipo_list', force_refresh=force)
    if data is None:
        return api_error(*ErrorCode.DATA_SOURCE_ERROR)
    return api_response(data, source=source, cached=cached)


@app.route('/api/v1/hkipo/upcoming')
@limit(60)
def hkipo_upcoming():
    """申购中/即将上市的港股 IPO"""
    force = request.args.get('refresh', '').lower() == 'true'
    if force:
        refresh_hk_ipo_cache(force=True)
    data, source, cached = fetch_with_cache(
        'hk_ipo_upcoming', 'get_hk_ipo_upcoming', force_refresh=force)
    if data is None:
        return api_error(*ErrorCode.DATA_SOURCE_ERROR)
    return api_response(data, source=source, cached=cached)


@app.route('/api/v1/hkipo/summary')
@limit(60)
def hkipo_summary():
    """港股打新市场概览"""
    force = request.args.get('refresh', '').lower() == 'true'
    if force:
        refresh_hk_ipo_cache(force=True)
    data, source, cached = fetch_with_cache(
        'hk_ipo_summary', 'get_hk_ipo_summary', force_refresh=force)
    if data is None:
        return api_error(*ErrorCode.DATA_SOURCE_ERROR)
    return api_response(data, source=source, cached=cached)


@app.route('/api/v1/hkipo/detail/<code>')
@limit(60)
def hkipo_detail(code):
    """港股 IPO 详情"""
    force = request.args.get('refresh', '').lower() == 'true'
    if force:
        refresh_hk_ipo_cache(force=True)
    data, source, cached = fetch_with_cache(
        'hk_ipo_detail', 'get_hk_ipo_detail', code=code, force_refresh=force)
    if data is None:
        return api_error('NOT_FOUND', '未找到该新股信息', 404)
    return api_response(data, source=source, cached=cached)


@app.route('/api/v1/hkipo/sync', methods=['POST'])
@limit(10)
def hkipo_sync():
    """Refresh the local IPO disclosure manifest and new PDFs."""
    items = refresh_hk_ipo_cache(force=True)
    cache.clear_pattern('hk:ipo:*')
    return api_response({'total': len(items), 'synced': True}, source='local')


# ==================== 封闭式基金 API ====================

@app.route('/api/v1/closed-end/list')
@limit(60)
def closed_end_list():
    """封闭式基金列表"""
    force = request.args.get('refresh', '').lower() == 'true'
    data, source, cached = fetch_with_cache(
        'closed_end_list', 'get_closed_end_list', force_refresh=force)
    if data is None:
        return api_error(*ErrorCode.DATA_SOURCE_ERROR)
    return api_response(data, source=source, cached=cached)


@app.route('/api/v1/closed-end/summary')
@limit(60)
def closed_end_summary():
    """封闭式基金市场概览"""
    force = request.args.get('refresh', '').lower() == 'true'
    data, source, cached = fetch_with_cache(
        'closed_end_summary', 'get_closed_end_summary', force_refresh=force)
    if data is None:
        return api_error(*ErrorCode.DATA_SOURCE_ERROR)
    return api_response(data, source=source, cached=cached)


# ==================== 管理接口 ====================

def admin_api_enabled():
    return os.environ.get('ENABLE_ADMIN_API', '').lower() in ('1', 'true', 'yes')


def require_admin_api(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not admin_api_enabled():
            return api_error('NOT_FOUND', '未找到接口', 404)
        return f(*args, **kwargs)
    return decorated


@app.route('/healthz')
def healthz():
    return api_response({'status': 'ok'}, source='local', cached=False)

@app.route('/api/v1/admin/health')
@require_admin_api
def admin_health():
    """详细健康检查"""
    sources_status = {}
    for name in factory._sources:
        source = factory.get_source(name)
        try:
            health = source.health_check()
            sources_status[name] = health
        except Exception as e:
            sources_status[name] = {
                'status': 'error',
                'error': str(e),
            }

    from models.database import DATABASE_URL
    return api_response({
        'status': 'ok',
        'primary_source': factory._primary_name,
        'cache_backend': cache.backend_type,
        'sources': sources_status,
        'database': {
            'type': 'sqlite' if 'sqlite' in DATABASE_URL else 'mysql',
            'url': DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL,
        },
    })


@app.route('/api/v1/admin/switch-source', methods=['POST'])
@require_admin_api
def admin_switch_source():
    """切换数据源"""
    source_name = request.json.get('source') if request.is_json else None
    if not source_name:
        return api_error(*ErrorCode.INVALID_PARAMS)
    try:
        factory.switch_source(source_name)
        return api_response({'source': source_name, 'message': f'已切换到 {source_name}'})
    except ValueError as e:
        return api_error(*ErrorCode.NOT_FOUND, str(e), 404)


@app.route('/api/v1/admin/cache/clear', methods=['POST'])
@require_admin_api
def admin_cache_clear():
    """清除缓存"""
    module = request.json.get('module') if request.is_json else None
    if module:
        cache.clear_pattern(f'{module}:*')
        return api_response({'cleared': module, 'message': f'已清除 {module} 模块缓存'})
    else:
        cache.clear_pattern('*')
        return api_response({'cleared': 'all', 'message': '已清除全部缓存'})


@app.route('/api/v1/admin/api-logs')
@require_admin_api
def admin_api_logs():
    """查询接口日志"""
    try:
        page = max(1, request.args.get('page', 1, type=int) or 1)
        page_size = min(200, max(1, request.args.get('page_size', 50, type=int) or 50))
        search = (request.args.get('search', '') or '').strip()

        logs = list(API_LOGS)
        if search:
            s = search.lower()
            logs = [l for l in logs if s in str(l.get('path', '')).lower()]
        logs.reverse()
        total = len(logs)
        start = (page - 1) * page_size
        end = start + page_size
        page_logs = logs[start:end]

        return api_response({
            'total': total,
            'page': page,
            'page_size': page_size,
            'has_more': end < total,
            'logs': page_logs,
        })
    except Exception as e:
        logger.error(f'查询接口日志异常: {e}')
        return api_error(*ErrorCode.INTERNAL_ERROR, f'查询日志失败: {e}')


@app.route('/api/v1/admin/api-logs/clear', methods=['POST'])
@require_admin_api
def admin_api_logs_clear():
    """清空接口日志"""
    try:
        API_LOGS.clear()
        return api_response({'message': '日志已清空'})
    except Exception as e:
        logger.error(f'清空接口日志异常: {e}')
        return api_error(*ErrorCode.INTERNAL_ERROR, f'清空日志失败: {e}')


# ==================== 向后兼容：旧路径重定向 ====================

@app.route('/api/market/overview')
def compat_market_overview():
    return market_overview()

@app.route('/api/convertible/list')
def compat_convertible_list():
    return convertible_list()

@app.route('/api/convertible/signals')
def compat_convertible_signals():
    return convertible_signals()

@app.route('/api/convertible/temperature')
def compat_convertible_temperature():
    return convertible_temperature()

@app.route('/api/convertible/detail/<code>')
def compat_convertible_detail(code):
    return convertible_detail(code)

@app.route('/api/lof/list')
def compat_lof_list():
    return lof_list()

@app.route('/api/lof/opportunities')
def compat_lof_opportunities():
    return lof_opportunities()

@app.route('/api/lof/summary')
def compat_lof_summary():
    return lof_summary()

@app.route('/api/hkipo/list')
def compat_hkipo_list():
    return hkipo_list()

@app.route('/api/hkipo/upcoming')
def compat_hkipo_upcoming():
    return hkipo_upcoming()

@app.route('/api/hkipo/summary')
def compat_hkipo_summary():
    return hkipo_summary()

@app.route('/api/health')
def compat_health():
    return healthz()


# ==================== 用户 API ====================

from models.database import init_db, get_db_session
from models.user import UserFavorite, UserReminder, UserSetting
from models.placement import PlacementResult
from models.convertible_timeline import ConvertibleTimeline
from services.auth import code_to_openid, require_auth

# 初始化数据库
init_db()


@app.route('/api/v1/user/login', methods=['POST'])
@limit(20)
def user_login():
    """小程序登录，获取 openid"""
    code = request.json.get('code') if request.is_json else None
    if not code:
        return api_error(*ErrorCode.INVALID_PARAMS, '缺少 code 参数')

    openid = code_to_openid(code)
    if not openid:
        return api_error(*ErrorCode.DATA_SOURCE_ERROR, '获取 openid 失败')

    # 确保用户设置存在
    with get_db_session() as db:
        setting = db.query(UserSetting).filter(UserSetting.openid == openid).first()
        if not setting:
            setting = UserSetting(openid=openid)
            db.add(setting)

    return api_response({'openid': openid})


@app.route('/api/v1/user/favorites')
@limit(60)
@require_auth
def get_favorites(openid):
    """获取自选列表"""
    type_filter = request.args.get('type')

    with get_db_session() as db:
        query = db.query(UserFavorite).filter(UserFavorite.openid == openid)
        if type_filter:
            query = query.filter(UserFavorite.type == type_filter)
        items = query.order_by(UserFavorite.created_at.desc()).all()
        return api_response({
            'total': len(items),
            'items': [{
                'code': item.code,
                'name': item.name,
                'type': item.type,
                'price': item.price,
                'premium_rate': item.premium_rate,
                'added_at': item.created_at.isoformat() if item.created_at else None
            } for item in items]
        })


@app.route('/api/v1/user/favorites', methods=['POST'])
@limit(20)
@require_auth
def add_favorite(openid):
    """添加自选"""
    data = request.json
    if not data or not data.get('code') or not data.get('type'):
        return api_error(*ErrorCode.INVALID_PARAMS, '缺少 code 或 type 参数')

    with get_db_session() as db:
        existing = db.query(UserFavorite).filter(
            UserFavorite.openid == openid,
            UserFavorite.code == data['code'],
            UserFavorite.type == data['type']
        ).first()

        if existing:
            return api_response({'message': '已存在', 'code': data['code']})

        fav = UserFavorite(
            openid=openid,
            code=data['code'],
            name=data.get('name', ''),
            type=data['type'],
            price=data.get('price'),
            premium_rate=data.get('premium_rate')
        )
        db.add(fav)
        return api_response({'message': '添加成功', 'code': data['code']})


@app.route('/api/v1/user/favorites', methods=['DELETE'])
@limit(20)
@require_auth
def delete_favorite(openid):
    """删除自选"""
    code = request.args.get('code')
    type_val = request.args.get('type')
    if not code or not type_val:
        return api_error(*ErrorCode.INVALID_PARAMS, '缺少 code 或 type 参数')

    with get_db_session() as db:
        deleted = db.query(UserFavorite).filter(
            UserFavorite.openid == openid,
            UserFavorite.code == code,
            UserFavorite.type == type_val
        ).delete()
        return api_response({'message': '删除成功' if deleted else '未找到', 'deleted': deleted})


@app.route('/api/v1/user/reminders')
@limit(60)
@require_auth
def get_reminders(openid):
    """获取提醒列表"""
    with get_db_session() as db:
        items = db.query(UserReminder).filter(UserReminder.openid == openid).all()
        return api_response({
            'total': len(items),
            'items': [{
                'id': item.id,
                'code': item.code,
                'name': item.name,
                'type': item.type,
                'remind_type': item.remind_type,
                'remind_value': item.remind_value,
                'enabled': item.enabled,
                'created_at': item.created_at.isoformat() if item.created_at else None
            } for item in items]
        })


@app.route('/api/v1/user/reminders', methods=['POST'])
@limit(20)
@require_auth
def add_reminder(openid):
    """添加提醒"""
    data = request.json
    if not data or not data.get('code') or not data.get('type') or not data.get('remind_type'):
        return api_error(*ErrorCode.INVALID_PARAMS, '缺少必要参数')

    with get_db_session() as db:
        existing = db.query(UserReminder).filter(
            UserReminder.openid == openid,
            UserReminder.code == data['code'],
            UserReminder.type == data['type'],
            UserReminder.remind_type == data['remind_type']
        ).first()

        if existing:
            return api_response({'message': '提醒已存在'})

        reminder = UserReminder(
            openid=openid,
            code=data['code'],
            name=data.get('name', ''),
            type=data['type'],
            remind_type=data['remind_type'],
            remind_value=data.get('remind_value'),
            enabled=data.get('enabled', True)
        )
        db.add(reminder)
        return api_response({'message': '提醒添加成功', 'id': reminder.id})


@app.route('/api/v1/user/reminders/<int:reminder_id>', methods=['PUT'])
@limit(20)
@require_auth
def update_reminder(openid, reminder_id):
    """更新提醒"""
    data = request.json
    with get_db_session() as db:
        reminder = db.query(UserReminder).filter(
            UserReminder.id == reminder_id,
            UserReminder.openid == openid
        ).first()
        if not reminder:
            return api_error('NOT_FOUND', '提醒不存在', 404)

        if 'enabled' in data:
            reminder.enabled = data['enabled']
        if 'remind_value' in data:
            reminder.remind_value = data['remind_value']
        return api_response({'message': '更新成功'})


@app.route('/api/v1/user/reminders/<int:reminder_id>', methods=['DELETE'])
@limit(20)
@require_auth
def delete_reminder(openid, reminder_id):
    """删除提醒"""
    with get_db_session() as db:
        deleted = db.query(UserReminder).filter(
            UserReminder.id == reminder_id,
            UserReminder.openid == openid
        ).delete()
        return api_response({'message': '删除成功' if deleted else '未找到'})


@app.route('/api/v1/user/settings')
@limit(60)
@require_auth
def get_settings(openid):
    """获取用户设置"""
    with get_db_session() as db:
        setting = db.query(UserSetting).filter(UserSetting.openid == openid).first()
        if not setting:
            setting = UserSetting(openid=openid)
            db.add(setting)
            db.flush()
        return api_response({
            'theme': setting.theme,
            'default_tab': setting.default_tab,
            'remind_enabled': setting.remind_enabled
        })


@app.route('/api/v1/user/settings', methods=['PUT'])
@limit(20)
@require_auth
def update_settings(openid):
    """更新用户设置"""
    data = request.json
    with get_db_session() as db:
        setting = db.query(UserSetting).filter(UserSetting.openid == openid).first()
        if not setting:
            setting = UserSetting(openid=openid)
            db.add(setting)

        if 'theme' in data:
            setting.theme = data['theme']
        if 'default_tab' in data:
            setting.default_tab = data['default_tab']
        if 'remind_enabled' in data:
            setting.remind_enabled = data['remind_enabled']
        return api_response({'message': '设置更新成功'})


# ==================== 缓存预热 ====================

def start_cache_warmup():
    """启动缓存预热（后台异步执行，不阻塞服务启动）"""
    import threading

    def _warmup():
        try:
            warmup_items = [
                ('market_sentiment', lambda: factory.get_with_fallback('get_market_sentiment')[0]),
                ('convertible_temperature', lambda: factory.get_with_fallback('get_convertible_temperature')[0]),
                ('convertible_signals', lambda: factory.get_with_fallback('get_convertible_signals')[0]),
                ('fund_flow', lambda: factory.get_with_fallback('get_fund_flow')[0]),
                ('lof_summary', lambda: factory.get_with_fallback('get_lof_summary')[0]),
                ('convertible_list', lambda: factory.get_with_fallback('get_convertible_list', page=1, page_size=50)[0]),
                ('convertible_new_listed', lambda: factory.get_with_fallback('get_convertible_new_listed')[0]),
            ]
            warmup_cache(warmup_items)
        except Exception as e:
            logger.error(f'缓存预热异常: {e}')

    t = threading.Thread(target=_warmup, daemon=True)
    t.start()
    logger.info('缓存预热已启动（后台执行）')


# ==================== 启动 ====================

def serve(debug=False):
    """WSL/systemd 本地部署入口。"""
    start_cache_warmup()
    app.run(host='0.0.0.0', port=8080, debug=debug, use_reloader=False)


if __name__ == '__main__':
    serve(debug=True)
