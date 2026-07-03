# -*- coding: utf-8 -*-
"""services 包 — 数据源抽象层、标准化、缓存与工厂"""

from services.base import BaseDataSource
from services.normalizer import (
    normalize_convertible,
    normalize_convertible_list,
    normalize_lof,
    normalize_lof_list,
)
from services.mock_source import MockSource
from services.akshare_source import AkshareSource
from services.efinance_source import EfinanceSource
from services.tushare_source import TushareSource
from services.cache import (
    CacheManager,
    get_cache_manager,
    get_cache_ttl,
    build_cache_key,
    is_trading_hours,
    get_with_cache_lock,
    CACHE_TTL_CONFIG,
)
from services.factory import (
    CircuitBreaker,
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
    'MockSource',
    'AkshareSource',
    'EfinanceSource',
    'TushareSource',
    # 缓存
    'CacheManager',
    'get_cache_manager',
    'get_cache_ttl',
    'build_cache_key',
    'is_trading_hours',
    'get_with_cache_lock',
    'CACHE_TTL_CONFIG',
    # 工厂
    'CircuitBreaker',
    'DataSourceFactory',
    'create_default_factory',
]
