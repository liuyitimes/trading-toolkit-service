# -*- coding: utf-8 -*-
"""工厂 + 熔断 + 降级 — 管理数据源实例，支持自动切换与降级"""

import logging
import os
import time

logger = logging.getLogger(__name__)


# ==================== 熔断器 ====================

class CircuitBreaker:
    """简单熔断器，防止持续调用不可用的数据源"""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = None
        self.state = 'closed'  # closed / open / half_open

    def can_call(self) -> bool:
        if self.state == 'open':
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = 'half_open'
                return True
            return False
        return True

    def record_success(self):
        self.failure_count = 0
        self.state = 'closed'

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = 'open'


# ==================== 数据源工厂 ====================

class DataSourceFactory:
    """数据源工厂，管理实例注册、主源切换与降级链"""

    def __init__(self):
        self._sources: dict = {}
        self._circuit_breakers: dict = {}
        self._primary_name: str = ''
        self._fallback_chain: list = []

    def register(self, name: str, source):
        """注册数据源"""
        self._sources[name] = source
        self._circuit_breakers[name] = CircuitBreaker()

    def set_primary(self, name: str):
        """设置主数据源"""
        if name not in self._sources:
            raise ValueError(f"数据源 '{name}' 未注册")
        self._primary_name = name

    def set_fallback_chain(self, chain: list):
        """设置降级链（按优先级排列的数据源名称列表）"""
        for name in chain:
            if name not in self._sources:
                raise ValueError(f"数据源 '{name}' 未注册，无法加入降级链")
        self._fallback_chain = list(chain)

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
        """带降级的数据调用 — 依次尝试降级链中的数据源

        Returns:
            (data, source_name) 元组，data 为调用结果，source_name 为实际使用的数据源名
        """
        # 构建尝试顺序：先主源，再降级链中其他源（去重）
        tried = set()
        ordered = []
        if self._primary_name:
            ordered.append(self._primary_name)
        for name in self._fallback_chain:
            if name not in tried:
                ordered.append(name)
        # 补充所有已注册但未列出的源
        for name in self._sources:
            if name not in tried and name not in ordered:
                ordered.append(name)

        last_error = None
        for name in ordered:
            tried.add(name)
            source = self._sources.get(name)
            if source is None:
                continue

            breaker = self._circuit_breakers.get(name)
            if breaker and not breaker.can_call():
                logger.warning(f'数据源 {name} 熔断中，跳过')
                continue

            try:
                method = getattr(source, method_name, None)
                if method is None:
                    continue
                result = method(**kwargs)
                if breaker:
                    breaker.record_success()
                return result, name
            except Exception as e:
                last_error = e
                if breaker:
                    breaker.record_failure()
                logger.error(f'数据源 {name}.{method_name} 调用失败: {e}')

        logger.error(f'所有数据源的 {method_name} 均失败，最后错误: {last_error}')
        return None, None


# ==================== 全局工厂实例 ====================

def create_default_factory() -> DataSourceFactory:
    """创建默认工厂，注册 akshare（主）→ efinance → tushare 降级链"""
    from services.akshare_source import AkshareSource
    from services.efinance_source import EfinanceSource
    from services.tushare_source import TushareSource

    factory = DataSourceFactory()
    factory.register('akshare', AkshareSource())
    factory.register('efinance', EfinanceSource())
    factory.register('tushare', TushareSource())

    factory.set_primary('akshare')
    factory.set_fallback_chain(['akshare', 'efinance', 'tushare'])

    return factory
