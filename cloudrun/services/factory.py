# -*- coding: utf-8 -*-
"""数据源工厂 — 管理数据源实例（单源模式，无降级链）

设计依据：ADR-002「按上游域分组 session，移除 CircuitBreaker」
  - 移除 CircuitBreaker 熔断器（由 http_client 的 Retry + 上层 stale cache 兜底替代）
  - 移除降级链（单源 DirectSource，失败时由 fetch_with_stale_fallback 返回 stale cache）
  - get_with_fallback 接口保持不变（app.py 有 8 处调用），仍返回 (data, source_name) 元组
"""

import logging

logger = logging.getLogger(__name__)


class DataSourceFactory:
    """数据源工厂（单源模式）— 管理 DirectSource 实例。

    保留 register / set_primary / get_with_fallback 接口以兼容现有调用方，
    但不再支持多源降级链。失败时返回 (None, None)，由上层 stale cache 兜底。
    """

    def __init__(self):
        self._sources: dict = {}
        self._primary_name: str = ''

    def register(self, name: str, source):
        """注册数据源"""
        self._sources[name] = source

    def set_primary(self, name: str):
        """设置主数据源"""
        if name not in self._sources:
            raise ValueError(f"数据源 '{name}' 未注册")
        self._primary_name = name

    def set_fallback_chain(self, chain: list):
        """设置降级链（单源模式下空操作，仅保留接口兼容）"""
        pass

    def get_primary_source(self):
        """获取主数据源"""
        return self._sources.get(self._primary_name)

    def get_source(self, name: str):
        """按名称获取数据源"""
        return self._sources.get(name)

    def switch_source(self, source_name: str):
        """切换主数据源"""
        if source_name not in self._sources:
            raise ValueError(f"数据源 '{source_name}' 未注册")
        self._primary_name = source_name
        logger.info(f'主数据源已切换为: {source_name}')

    def get_with_fallback(self, method_name: str, **kwargs):
        """数据调用 — 单源模式，直接调用主数据源。

        接口与原工厂保持一致，返回 (data, source_name) 元组。
        失败时返回 (None, None)，由上层 fetch_with_stale_fallback 返回 stale cache。
        """
        name = self._primary_name
        source = self._sources.get(name)
        if source is None:
            logger.error(f'无可用数据源（primary={name}）')
            return None, None

        try:
            method = getattr(source, method_name, None)
            if method is None:
                logger.error(f'数据源 {name} 无方法 {method_name}')
                return None, None
            result = method(**kwargs)
            return result, name
        except Exception as e:
            logger.error(f'数据源 {name}.{method_name} 调用失败: {e}')
            return None, None


# ==================== 全局工厂实例 ====================

def create_default_factory() -> DataSourceFactory:
    """创建默认工厂，注册 DirectSource（单一数据源，零 akshare 依赖）"""
    from services.direct_source import DirectSource

    factory = DataSourceFactory()
    factory.register('direct', DirectSource())
    factory.set_primary('direct')
    return factory
