# -*- coding: utf-8 -*-
"""面向用户展示的行情记录完整性校验。"""

import math


_CONVERTIBLE_TEXT_FIELDS = ('bond_code', 'bond_name', 'stock_code', 'stock_name')
_CONVERTIBLE_POSITIVE_FIELDS = ('price', 'conversion_price', 'conversion_value')
_MISSING_TEXT_VALUES = {'', 'nan', 'nat', 'none', 'null'}


def is_complete_convertible_row(row: dict) -> bool:
    """判断一条可转债记录是否可作为当前市场事实展示。"""
    if not isinstance(row, dict):
        return False
    if any(
        str(row.get(field) or '').strip().lower() in _MISSING_TEXT_VALUES
        for field in _CONVERTIBLE_TEXT_FIELDS
    ):
        return False
    try:
        return all(
            math.isfinite(float(row.get(field) or 0)) and float(row.get(field) or 0) > 0
            for field in _CONVERTIBLE_POSITIVE_FIELDS
        )
    except (TypeError, ValueError):
        return False


def is_complete_convertible_list_payload(payload) -> bool:
    """只允许完整且非空的可转债列表成为可恢复快照。"""
    if not isinstance(payload, dict):
        return False
    items = payload.get('items')
    return isinstance(items, list) and bool(items) and all(
        is_complete_convertible_row(item) for item in items
    )
