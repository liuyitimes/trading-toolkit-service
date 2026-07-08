# -*- coding: utf-8 -*-
"""数据源抽象基类 — 定义统一的数据访问接口"""

from abc import ABC, abstractmethod


class BaseDataSource(ABC):
    """数据源抽象基类，所有数据源实现必须继承此类"""

    @abstractmethod
    def get_convertible_list(self, **kwargs) -> list:
        """获取可转债列表"""

    @abstractmethod
    def get_convertible_signals(self) -> dict:
        """获取可转债信号（双低、强赎、折价、下修）"""

    @abstractmethod
    def get_convertible_pending(self) -> list:
        """获取待发/配售可转债列表（含正股信息和配售数据）"""

    @abstractmethod
    def get_convertible_detail(self, code: str) -> dict:
        """获取单只可转债详情"""

    @abstractmethod
    def get_convertible_temperature(self) -> dict:
        """获取可转债市场温度"""

    @abstractmethod
    def get_lof_list(self, **kwargs) -> list:
        """获取 LOF 基金列表"""

    @abstractmethod
    def get_lof_opportunities(self) -> dict:
        """获取 LOF 套利机会"""

    @abstractmethod
    def get_lof_summary(self) -> dict:
        """获取 LOF 市场概览"""

    @abstractmethod
    def get_hk_ipo_list(self, **kwargs) -> list:
        """获取港股 IPO 列表"""

    @abstractmethod
    def get_hk_ipo_upcoming(self) -> list:
        """获取即将上市的港股 IPO"""

    @abstractmethod
    def get_hk_ipo_summary(self) -> dict:
        """获取港股 IPO 市场概览"""

    @abstractmethod
    def get_market_sentiment(self) -> dict:
        """获取市场情绪数据"""

    @abstractmethod
    def get_fund_flow(self) -> dict:
        """获取板块资金流向数据"""

    @abstractmethod
    def get_closed_end_list(self) -> list:
        """获取封闭式基金列表（含价格、净值、折价率）"""

    @abstractmethod
    def get_closed_end_summary(self) -> dict:
        """获取封闭式基金市场概览"""

    @abstractmethod
    def health_check(self) -> dict:
        """数据源健康检查"""
