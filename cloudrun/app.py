# -*- coding: utf-8 -*-
"""旺财百宝箱 — Flask 后端 API

统一响应格式、分级缓存、多数据源降级、接口限流、结构化日志。
"""

import logging
import os
import traceback

from flask import Flask, request
from flask_cors import CORS

from services.factory import create_default_factory
from services.cache import (
    get_cache_manager,
    get_cache_ttl,
    build_cache_key,
    get_with_cache_lock,
)
from utils.response import api_response, api_error, ErrorCode
from utils.limiting import limit
from utils.logging import setup_logging

# ==================== 初始化 ====================

app = Flask(__name__)
CORS(app)

# 结构化日志
logger = setup_logging(app)

# 数据源工厂（akshare → mock 降级链）
factory = create_default_factory()

# 缓存管理器
cache = get_cache_manager()

logger.info(f'后端启动完成，主数据源: {factory._primary_name}，缓存后端: {cache.backend_type}')


# ==================== 通用数据获取 ====================

def fetch_with_cache(data_type: str, method_name: str, force_refresh=False, **kwargs):
    """通用数据获取：缓存 → 数据源降级

    Args:
        data_type: 缓存类型（如 convertible_list、lof_list）
        method_name: 数据源方法名
        force_refresh: 是否强制刷新
        **kwargs: 传递给数据源方法的参数

    Returns:
        (data, source, cached) 元组
    """
    cache_key = build_cache_key(data_type.replace('_', ':'), 'data',
                                 **{k: str(v) for k, v in kwargs.items() if v is not None})
    ttl = get_cache_ttl(data_type)

    # 非强制刷新时先查缓存
    if not force_refresh:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached, 'cache', True

    # 通过工厂带降级获取数据
    data, source = factory.get_with_fallback(method_name, **kwargs)

    if data is not None:
        cache.set(cache_key, data, ttl)
        return data, source or 'unknown', False

    # 所有数据源均失败
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

        # 港股 IPO 概览
        data, _, _ = fetch_with_cache('hk_ipo_summary', 'get_hk_ipo_summary')
        result['hk_ipo'] = data or {}

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


# ==================== 港股 IPO API ====================

@app.route('/api/v1/hkipo/list')
@limit(60)
def hkipo_list():
    """港股 IPO 列表"""
    force = request.args.get('refresh', '').lower() == 'true'
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
    data, source, cached = fetch_with_cache(
        'hk_ipo_summary', 'get_hk_ipo_summary', force_refresh=force)
    if data is None:
        return api_error(*ErrorCode.DATA_SOURCE_ERROR)
    return api_response(data, source=source, cached=cached)


# ==================== 管理接口 ====================

@app.route('/api/v1/admin/health')
def admin_health():
    """详细健康检查"""
    sources_status = {}
    for name in factory._sources:
        source = factory.get_source(name)
        breaker = factory._circuit_breakers.get(name)
        try:
            health = source.health_check()
            sources_status[name] = {
                **health,
                'circuit_breaker': {
                    'state': breaker.state if breaker else 'unknown',
                    'failure_count': breaker.failure_count if breaker else 0,
                }
            }
        except Exception as e:
            sources_status[name] = {
                'status': 'error',
                'error': str(e),
                'circuit_breaker': {
                    'state': breaker.state if breaker else 'unknown',
                    'failure_count': breaker.failure_count if breaker else 0,
                }
            }

    from models.database import DATABASE_URL
    return api_response({
        'status': 'ok',
        'primary_source': factory._primary_name,
        'fallback_chain': factory._fallback_chain,
        'cache_backend': cache.backend_type,
        'sources': sources_status,
        'database': {
            'type': 'sqlite' if 'sqlite' in DATABASE_URL else 'mysql',
            'url': DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL,
        },
    })


@app.route('/api/v1/admin/switch-source', methods=['POST'])
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
def admin_cache_clear():
    """清除缓存"""
    module = request.json.get('module') if request.is_json else None
    if module:
        cache.clear_pattern(f'{module}:*')
        return api_response({'cleared': module, 'message': f'已清除 {module} 模块缓存'})
    else:
        cache.clear_pattern('*')
        return api_response({'cleared': 'all', 'message': '已清除全部缓存'})


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
    return admin_health()


# ==================== 用户 API ====================

from models.database import init_db, SessionLocal
from models.user import UserFavorite, UserReminder, UserSetting
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
    db = SessionLocal()
    try:
        setting = db.query(UserSetting).filter(UserSetting.openid == openid).first()
        if not setting:
            setting = UserSetting(openid=openid)
            db.add(setting)
            db.commit()
    finally:
        db.close()

    return api_response({'openid': openid})


@app.route('/api/v1/user/favorites')
@limit(60)
@require_auth
def get_favorites(openid):
    """获取自选列表"""
    type_filter = request.args.get('type')

    db = SessionLocal()
    try:
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
    finally:
        db.close()


@app.route('/api/v1/user/favorites', methods=['POST'])
@limit(20)
@require_auth
def add_favorite(openid):
    """添加自选"""
    data = request.json
    if not data or not data.get('code') or not data.get('type'):
        return api_error(*ErrorCode.INVALID_PARAMS, '缺少 code 或 type 参数')

    db = SessionLocal()
    try:
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
        db.commit()
        return api_response({'message': '添加成功', 'code': data['code']})
    finally:
        db.close()


@app.route('/api/v1/user/favorites', methods=['DELETE'])
@limit(20)
@require_auth
def delete_favorite(openid):
    """删除自选"""
    code = request.args.get('code')
    type_val = request.args.get('type')
    if not code or not type_val:
        return api_error(*ErrorCode.INVALID_PARAMS, '缺少 code 或 type 参数')

    db = SessionLocal()
    try:
        deleted = db.query(UserFavorite).filter(
            UserFavorite.openid == openid,
            UserFavorite.code == code,
            UserFavorite.type == type_val
        ).delete()
        db.commit()
        return api_response({'message': '删除成功' if deleted else '未找到', 'deleted': deleted})
    finally:
        db.close()


@app.route('/api/v1/user/reminders')
@limit(60)
@require_auth
def get_reminders(openid):
    """获取提醒列表"""
    db = SessionLocal()
    try:
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
    finally:
        db.close()


@app.route('/api/v1/user/reminders', methods=['POST'])
@limit(20)
@require_auth
def add_reminder(openid):
    """添加提醒"""
    data = request.json
    if not data or not data.get('code') or not data.get('type') or not data.get('remind_type'):
        return api_error(*ErrorCode.INVALID_PARAMS, '缺少必要参数')

    db = SessionLocal()
    try:
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
        db.commit()
        return api_response({'message': '提醒添加成功', 'id': reminder.id})
    finally:
        db.close()


@app.route('/api/v1/user/reminders/<int:reminder_id>', methods=['PUT'])
@limit(20)
@require_auth
def update_reminder(openid, reminder_id):
    """更新提醒"""
    data = request.json
    db = SessionLocal()
    try:
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
        db.commit()
        return api_response({'message': '更新成功'})
    finally:
        db.close()


@app.route('/api/v1/user/reminders/<int:reminder_id>', methods=['DELETE'])
@limit(20)
@require_auth
def delete_reminder(openid, reminder_id):
    """删除提醒"""
    db = SessionLocal()
    try:
        deleted = db.query(UserReminder).filter(
            UserReminder.id == reminder_id,
            UserReminder.openid == openid
        ).delete()
        db.commit()
        return api_response({'message': '删除成功' if deleted else '未找到'})
    finally:
        db.close()


@app.route('/api/v1/user/settings')
@limit(60)
@require_auth
def get_settings(openid):
    """获取用户设置"""
    db = SessionLocal()
    try:
        setting = db.query(UserSetting).filter(UserSetting.openid == openid).first()
        if not setting:
            setting = UserSetting(openid=openid)
            db.add(setting)
            db.commit()
            db.refresh(setting)
        return api_response({
            'theme': setting.theme,
            'default_tab': setting.default_tab,
            'remind_enabled': setting.remind_enabled
        })
    finally:
        db.close()


@app.route('/api/v1/user/settings', methods=['PUT'])
@limit(20)
@require_auth
def update_settings(openid):
    """更新用户设置"""
    data = request.json
    db = SessionLocal()
    try:
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
        db.commit()
        return api_response({'message': '设置更新成功'})
    finally:
        db.close()


# ==================== 启动 ====================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
