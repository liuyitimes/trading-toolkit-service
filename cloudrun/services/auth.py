# -*- coding: utf-8 -*-
"""用户认证服务

提供微信小程序 code 换取 openid 的能力，以及请求鉴权装饰器。
"""

import os
import requests
import logging
from functools import wraps
from flask import request
from utils.response import api_error, ErrorCode

logger = logging.getLogger('trading_toolkit')

# 微信小程序配置
WX_APPID = os.environ.get('WX_APPID', '')
WX_SECRET = os.environ.get('WX_SECRET', '')


def code_to_openid(code: str) -> str:
    """通过微信小程序 code 获取 openid"""
    if not WX_APPID or not WX_SECRET:
        logger.warning('WX_APPID 或 WX_SECRET 未配置，返回测试 openid')
        return f'test_{code}'

    url = 'https://api.weixin.qq.com/sns/jscode2session'
    params = {
        'appid': WX_APPID,
        'secret': WX_SECRET,
        'js_code': code,
        'grant_type': 'authorization_code'
    }
    try:
        resp = requests.get(url, params=params, timeout=5)
        data = resp.json()
        if 'openid' in data:
            return data['openid']
        else:
            logger.error(f'获取 openid 失败: {data}')
            return None
    except Exception as e:
        logger.error(f'调用微信接口失败: {e}')
        return None


def require_auth(f):
    """鉴权装饰器：要求请求在 X-Openid 头中携带 openid"""
    @wraps(f)
    def decorated(*args, **kwargs):
        openid = request.headers.get('X-Openid')
        if not openid:
            return api_error('UNAUTHORIZED', '缺少 X-Openid 头', 401)
        kwargs['openid'] = openid
        return f(*args, **kwargs)
    return decorated
