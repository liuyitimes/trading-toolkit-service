# -*- coding: utf-8 -*-
"""services 包 — 数据源抽象层、标准化、缓存与工厂（直连单源模式）"""

from services.base import BaseDataSource
from services.normalizer import (
    normalize_convertible,
    normalize_convertible_list,
    normalize_lof,
    normalize_lof_list,
)
from services.direct_source import DirectSource
from services.cache import (
    CacheManager,
    get_cache_manager,
    get_cache_ttl,
    build_cache_key,
    is_trading_hours,
    get_with_cache_lock,
    fetch_with_stale_fallback,
    CACHE_TTL_CONFIG,
)
from services.factory import (
    DataSourceFactory,
    create_default_factory,
)

__all__ = [
    # 基类
    'BaseDataSource',
    # 标准化
    'normalize_convertible',
    'normalize_convertible_list',
    'normalize_lof',
    'normalize_lof_list',
    # 数据源实现
    'DirectSource',
    # 缓存
    'CacheManager',
    'get_cache_manager',
    'get_cache_ttl',
    'build_cache_key',
    'is_trading_hours',
    'get_with_cache_lock',
    'fetch_with_stale_fallback',
    'CACHE_TTL_CONFIG',
    # 工厂
    'DataSourceFactory',
    'create_default_factory',
]
