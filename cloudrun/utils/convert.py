# -*- coding: utf-8 -*-
"""通用转换工具"""

import pandas as pd


def safe_float(val, default=0):
    """安全转换为 float，处理 NaN/None/异常值"""
    try:
        if pd.isna(val):
            return default
        return float(val)
    except (ValueError, TypeError):
        return default
