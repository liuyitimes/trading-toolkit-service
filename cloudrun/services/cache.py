# -*- coding: utf-8 -*-
"""分级缓存系统 — 根据数据类型和交易时段动态调整 TTL"""

import json
import logging
import os
import threading
import time
from datetime import datetime, time as dt_time

logger = logging.getLogger('trading_toolkit')

# TTL 配置（秒）
CACHE_TTL_CONFIG = {
    'stock_quote': 30,
    'convertible_quote': 60,
    'market_sentiment': 300,
    'fund_flow': 300,
    'hot_sectors': 600,
    'convertible_list': 900,
    'convertible_signals': 900,
    'convertible_temperature': 900,
    'lof_list': 900,
    'lof_opportunities': 900,
    'lof_summary': 900,
    'hk_ipo_list': 1800,
    'hk_ipo_upcoming': 1800,
    'hk_ipo_summary': 1800,
    'convertible_detail': 43200,
    'convertible_pending': 1800,
    'stock_profile': 86400,
}


def is_trading_hours():
    """判断是否在 A 股交易时间内"""
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    current_time = now.time()
    morning = dt_time(9, 15) <= current_time <= dt_time(11, 30)
    afternoon = dt_time(13, 0) <= current_time <= dt_time(15, 5)
    return morning or afternoon


def get_cache_ttl(data_type: str) -> int:
    """根据数据类型和交易时段返回 TTL"""
    base_ttl = CACHE_TTL_CONFIG.get(data_type, 300)
    if not is_trading_hours():
        non_trading_types = [
            'convertible_list', 'lof_list', 'convertible_temperature',
            'convertible_signals', 'lof_opportunities', 'market_sentiment',
            'fund_flow', 'hot_sectors', 'convertible_signals', 'lof_summary',
            'hk_ipo_list', 'hk_ipo_upcoming', 'hk_ipo_summary',
        ]
        if data_type in non_trading_types:
            return min(base_ttl * 4, 14400)
    return base_ttl


def build_cache_key(module: str, action: str, **params) -> str:
    parts = [module, action]
    if params:
        sorted_params = sorted(params.items())
        param_str = ':'.join(f"{k}={v}" for k, v in sorted_params if v is not None)
        if param_str:
            parts.append(param_str)
    return ':'.join(parts)


# ==================== 内存缓存后备 ====================

class _MemoryCache:
    """简单的内存 LRU 缓存，当 redis 不可用时使用"""

    def __init__(self, max_size: int = 500):
        self._store: dict = {}
        self._expiry: dict = {}
        self._lock = threading.Lock()
        self._max_size = max_size

    def get(self, key: str):
        with self._lock:
            if key in self._store:
                if self._expiry.get(key, 0) > time.time():
                    return self._store[key]
                # 已过期，清理
                self._store.pop(key, None)
                self._expiry.pop(key, None)
            return None

    def set(self, key: str, value, ttl: int):
        with self._lock:
            # 简单淘汰：超过上限时清理过期条目
            if len(self._store) >= self._max_size:
                now = time.time()
                expired = [k for k, exp in self._expiry.items() if exp <= now]
                for k in expired:
                    self._store.pop(k, None)
                    self._expiry.pop(k, None)
            self._store[key] = value
            self._expiry[key] = time.time() + ttl

    def delete(self, key: str):
        with self._lock:
            self._store.pop(key, None)
            self._expiry.pop(key, None)

    def clear_pattern(self, pattern: str):
        """按前缀清除缓存（简化实现）"""
        prefix = pattern.replace('*', '')
        with self._lock:
            keys = [k for k in self._store if k.startswith(prefix)]
            for k in keys:
                self._store.pop(k, None)
                self._expiry.pop(k, None)


# ==================== CacheManager ====================

class CacheManager:
    """统一缓存管理器，根据环境变量自动选择 redis / fakeredis / 内存"""

    def __init__(self):
        self._backend = None
        self._backend_type = 'memory'
        self._init_backend()

    def _init_backend(self):
        redis_url = os.environ.get('REDIS_URL', '').strip()
        if not redis_url:
            # 无 REDIS_URL，尝试 fakeredis（开发环境）
            try:
                import fakeredis
                self._backend = fakeredis.FakeRedis(decode_responses=True)
                self._backend_type = 'fakeredis'
                return
            except ImportError:
                pass
        else:
            # 有 REDIS_URL，尝试连接真实 redis
            try:
                import redis
                self._backend = redis.from_url(redis_url, decode_responses=True)
                # 测试连接
                self._backend.ping()
                self._backend_type = 'redis'
                return
            except Exception:
                pass

        # 回退到内存缓存
        self._backend = _MemoryCache()
        self._backend_type = 'memory'

    @property
    def backend_type(self) -> str:
        return self._backend_type

    def get(self, key: str):
        try:
            raw = self._backend.get(key)
            if raw is None:
                return None
            # redis 返回的可能是 bytes 或 str
            if isinstance(raw, bytes):
                raw = raw.decode('utf-8')
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw
        except Exception:
            return None

    def set(self, key: str, value, ttl: int = 300):
        try:
            serialized = json.dumps(value, ensure_ascii=False, default=str)
            if self._backend_type == 'memory':
                self._backend.set(key, value, ttl)
            else:
                self._backend.set(key, serialized, ex=ttl)
        except Exception:
            pass

    def delete(self, key: str):
        try:
            self._backend.delete(key)
        except Exception:
            pass

    def clear_pattern(self, pattern: str):
        """按模式清除缓存"""
        try:
            if self._backend_type == 'memory':
                self._backend.clear_pattern(pattern)
            else:
                # redis 使用 SCAN + 批量删除
                cursor = 0
                while True:
                    cursor, keys = self._backend.scan(cursor=cursor, match=pattern, count=100)
                    if keys:
                        self._backend.delete(*keys)
                    if cursor == 0:
                        break
        except Exception:
            pass


# ==================== 全局实例 & 缓存防穿透 ====================

_cache_manager = CacheManager()
_lock_registry: dict = {}
_lock_registry_lock = threading.Lock()


def get_cache_manager() -> CacheManager:
    """获取全局缓存管理器实例"""
    return _cache_manager


def _get_lock(cache_key: str) -> threading.Lock:
    """获取缓存键对应的锁"""
    with _lock_registry_lock:
        if cache_key not in _lock_registry:
            _lock_registry[cache_key] = threading.Lock()
        return _lock_registry[cache_key]


def get_with_cache_lock(cache_key: str, fetch_func, ttl: int):
    """缓存防穿透 — 先查缓存，未命中时加锁回源，防止并发穿透"""
    cache = get_cache_manager()

    # 第一次尝试读缓存
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    lock = _get_lock(cache_key)
    with lock:
        # 双重检查：可能其他线程已经填充了缓存
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        # 回源获取数据
        data = fetch_func()
        if data is not None:
            cache.set(cache_key, data, ttl)
        return data


# ==================== 后台异步刷新（SWR: stale-while-revalidate） ====================

_refresh_threads: dict = {}
_refresh_lock = threading.Lock()


def get_with_swr(cache_key: str, fetch_func, ttl: int, revalidate_ratio: float = 0.7):
    """Stale-While-Revalidate 模式：
    - 有缓存直接返回（即使过期）
    - 后台异步刷新缓存
    - 无缓存时同步获取

    Args:
        cache_key: 缓存键
        fetch_func: 回源函数
        ttl: 缓存 TTL（秒）
        revalidate_ratio: 剩余时间低于此比例时触发后台刷新（0.7 = 剩余70%时开始刷新）
    """
    cache = get_cache_manager()

    # 先尝试读缓存
    cached = cache.get(cache_key)

    if cached is not None:
        # 有缓存，检查是否需要后台刷新
        _maybe_trigger_background_refresh(cache_key, fetch_func, ttl, revalidate_ratio)
        return cached

    # 无缓存，同步获取
    lock = _get_lock(cache_key)
    with lock:
        # 双重检查
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        data = fetch_func()
        if data is not None:
            cache.set(cache_key, data, ttl)
        return data


def _maybe_trigger_background_refresh(cache_key: str, fetch_func, ttl: int, revalidate_ratio: float):
    """检查是否需要触发后台刷新"""
    # 简化实现：用一个标记键记录下次刷新时间
    cache = get_cache_manager()
    refresh_key = f'{cache_key}:_next_refresh'

    try:
        next_refresh = cache.get(refresh_key)
    except Exception:
        next_refresh = None

    now = time.time()

    if next_refresh is None or float(next_refresh) <= now:
        # 需要刷新
        with _refresh_lock:
            if cache_key not in _refresh_threads or not _refresh_threads[cache_key].is_alive():
                # 启动后台刷新线程
                t = threading.Thread(
                    target=_background_refresh_worker,
                    args=(cache_key, fetch_func, ttl, refresh_key, revalidate_ratio),
                    daemon=True
                )
                _refresh_threads[cache_key] = t
                t.start()


def _background_refresh_worker(cache_key: str, fetch_func, ttl: int, refresh_key: str, revalidate_ratio: float):
    """后台刷新工作线程"""
    try:
        cache = get_cache_manager()
        data = fetch_func()
        if data is not None:
            cache.set(cache_key, data, ttl)
            # 设置下次刷新时间：TTL * revalidate_ratio 后刷新
            next_refresh = time.time() + ttl * revalidate_ratio
            cache.set(refresh_key, str(next_refresh), ttl)
    except Exception as e:
        logger.warning(f'[CacheSWR] 后台刷新失败 {cache_key}: {e}')


# ==================== 缓存预热 ====================

def warmup_cache(items: list):
    """预热缓存

    Args:
        items: [(data_type, method_name, factory), ...] 列表
    """
    logger.info('[CacheWarmup] 开始预热缓存...')

    def _warmup_item(data_type, fetch_func):
        try:
            cache_key = build_cache_key(data_type.replace('_', ':'), 'data')
            ttl = get_cache_ttl(data_type)
            cache = get_cache_manager()

            # 已有缓存则跳过
            if cache.get(cache_key) is not None:
                logger.info(f'[CacheWarmup] {data_type}: 已有缓存，跳过')
                return

            logger.info(f'[CacheWarmup] {data_type}: 开始加载...')
            start = time.time()
            data = fetch_func()
            if data is not None:
                cache.set(cache_key, data, ttl)
                elapsed = time.time() - start
                logger.info(f'[CacheWarmup] {data_type}: 加载完成，耗时 {elapsed:.1f}s')
            else:
                logger.info(f'[CacheWarmup] {data_type}: 数据为空')
        except Exception as e:
            logger.warning(f'[CacheWarmup] {data_type}: 预热失败 - {e}')

    threads = []
    for data_type, fetch_func in items:
        t = threading.Thread(target=_warmup_item, args=(data_type, fetch_func), daemon=True)
        threads.append(t)
        t.start()

    # 等待所有预热完成（或超时）
    for t in threads:
        t.join(timeout=120)

    logger.info('[CacheWarmup] 缓存预热完成')
