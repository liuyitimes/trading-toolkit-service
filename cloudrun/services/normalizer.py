# -*- coding: utf-8 -*-
"""字段标准化 — 将中文字段映射为英文 snake_case"""

# 交易所映射
_EXCHANGE_MAP = {'沪': 'sh', '深': 'sz', '北': 'bj'}


def normalize_convertible(row: dict) -> dict:
    """将可转债数据标准化"""
    raw_exchange = str(row.get('交易所', ''))
    exchange = _EXCHANGE_MAP.get(raw_exchange, raw_exchange)
    return {
        'bond_code': str(row.get('转债代码', '')),
        'bond_name': str(row.get('转债名称', '')),
        'price': float(row.get('转债价格', 0)),
        'change_pct': float(row.get('涨跌幅', 0)),
        'stock_code': str(row.get('正股代码', '')),
        'stock_name': str(row.get('正股名称', '')),
        'conversion_value': float(row.get('转股价值', 0)),
        'premium_rate': float(row.get('转股溢价率', 0)),
        'double_low': float(row.get('双低', 0)),
        'exchange': exchange,
        'rating': str(row.get('评级', '')),
        'maturity_date': str(row.get('到期时间', '')),
        'remaining_size': float(row.get('剩余规模', 0)),
        'volume': float(row.get('成交量', 0)),
        'amount': float(row.get('成交额', 0)),
    }


def normalize_convertible_list(rows: list) -> list:
    """批量标准化可转债数据"""
    return [normalize_convertible(row) for row in rows]


def normalize_lof(row: dict) -> dict:
    """将 LOF 基金数据标准化"""
    raw_exchange = str(row.get('交易所', ''))
    exchange = _EXCHANGE_MAP.get(raw_exchange, raw_exchange)
    return {
        'code': str(row.get('代码', '')),
        'name': str(row.get('名称', '')),
        'price': float(row.get('最新价', 0)),
        'change_pct': float(row.get('涨跌幅', 0)),
        'valuation': float(row.get('估值', 0)),
        'premium': float(row.get('溢价率', 0)),
        'consecutive_premium': int(row.get('连续溢价', 0)),
        'limit_status': str(row.get('申购状态', '')),
        'exchange': exchange,
        'volume': round(float(row.get('成交量', 0)) / 10000, 2),
        'amount': round(float(row.get('成交额', 0)) / 10000, 2),
    }


def normalize_lof_list(rows: list) -> list:
    """批量标准化 LOF 基金数据"""
    return [normalize_lof(row) for row in rows]
