# -*- coding: utf-8 -*-
"""EfinanceSource 实现 — 封装 efinance 数据调用作为备用数据源

efinance 是轻量级 Python 金融数据接口库，封装了东方财富的数据。
import 统一放在方法内部 try/except 中，避免 efinance 未安装时导致整个模块加载失败。
"""

import logging

from services.base import BaseDataSource
from services.normalizer import (
    normalize_convertible_list,
    normalize_lof_list,
)

logger = logging.getLogger('trading_toolkit')


def _apply_convertible_filters(items: list, **kwargs) -> dict:
    """对标准化后的可转债数据进行筛选、排序和分页

    Args:
        items: 标准化后的可转债列表
        **kwargs: 筛选和分页参数

    Returns:
        分页结果 dict: { total, page, page_size, items }
    """
    filtered = list(items)

    # 交易所筛选
    exchange = kwargs.get('exchange')
    if exchange:
        filtered = [item for item in filtered if item.get('exchange') == exchange]

    # 最低价格筛选
    min_price = kwargs.get('min_price')
    if min_price is not None:
        filtered = [item for item in filtered if item.get('price', 0) >= min_price]

    # 最高价格筛选
    max_price = kwargs.get('max_price')
    if max_price is not None:
        filtered = [item for item in filtered if item.get('price', 0) <= max_price]

    # 最高溢价率筛选
    max_premium = kwargs.get('max_premium')
    if max_premium is not None:
        filtered = [item for item in filtered if item.get('premium_rate', 0) <= max_premium]

    # 排序
    sort = kwargs.get('sort', 'double_low')
    if sort == 'double_low':
        filtered.sort(key=lambda x: x.get('double_low', 0))
    elif sort == 'price':
        filtered.sort(key=lambda x: x.get('price', 0))
    elif sort == 'premium':
        filtered.sort(key=lambda x: x.get('premium_rate', 0))
    elif sort == 'premium_desc':
        filtered.sort(key=lambda x: x.get('premium_rate', 0), reverse=True)

    # 分页
    page = kwargs.get('page', 1)
    page_size = kwargs.get('page_size', 100)
    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    paged = filtered[start:end]

    return {
        'total': total,
        'page': page,
        'page_size': page_size,
        'items': paged,
    }


# ========== efinance 列名 → normalizer 期望列名映射 ==========

# 可转债列名映射（efinance → normalizer）
_BOND_COLUMN_MAP = {
    '债券代码': '转债代码',
    '债券名称': '转债名称',
    '最新价': '转债价格',
    '正股代码': '正股代码',
    '正股名称': '正股名称',
    '转股价值': '转股价值',
    '转股溢价率': '转股溢价率',
    '双低': '双低',
}

# LOF 基金列名映射（efinance → normalizer）
_LOF_COLUMN_MAP = {
    '基金代码': '代码',
    '基金名称': '名称',
    '最新价': '最新价',
    '涨跌幅': '涨跌幅',
    '估算值': '估值',
    '溢价率': '溢价率',
    '申购状态': '申购状态',
}


def _map_columns(df, column_map: dict):
    """将 DataFrame 列名映射为 normalizer 期望的列名，返回映射后的 list[dict]

    Args:
        df: efinance 返回的 DataFrame
        column_map: 列名映射字典 {efinance列名: normalizer列名}

    Returns:
        list[dict]: 列名映射后的字典列表
    """
    # 先找出 DataFrame 中实际存在的列
    available_src = [col for col in column_map if col in df.columns]
    rename_dict = {col: column_map[col] for col in available_src}
    # 只保留有映射关系的列
    mapped = df[available_src].rename(columns=rename_dict)
    return mapped.to_dict('records')


class EfinanceSource(BaseDataSource):
    """Efinance 数据源 — 基于东方财富公开接口，作为备用数据源"""

    # ---- 可转债 ----

    def get_convertible_list(self, **kwargs) -> dict:
        """通过 efinance 获取可转债列表"""
        try:
            import efinance as ef
            df = ef.bond.get_realtime_quotes()
            if df is None or df.empty:
                return {'total': 0, 'page': 1, 'page_size': 100, 'items': []}

            # 列名映射后交给 normalizer 标准化
            rows = _map_columns(df, _BOND_COLUMN_MAP)
            if not rows:
                return {'total': 0, 'page': 1, 'page_size': 100, 'items': []}

            normalized = normalize_convertible_list(rows)
            return _apply_convertible_filters(normalized, **kwargs)
        except Exception as e:
            logger.warning(f'[EfinanceSource] get_convertible_list 失败: {e}')
            return {'total': 0, 'page': 1, 'page_size': 100, 'items': []}

    def get_convertible_signals(self) -> dict:
        """通过 efinance 获取可转债信号"""
        try:
            import efinance as ef
            df = ef.bond.get_realtime_quotes()
            if df is None or df.empty:
                return {'double_low': [], 'force_redeem': [], 'discount': [], 'down_revised': []}

            rows = _map_columns(df, _BOND_COLUMN_MAP)
            if not rows:
                return {'double_low': [], 'force_redeem': [], 'discount': [], 'down_revised': []}

            normalized = normalize_convertible_list(rows)

            # 双低策略 Top 20
            double_low = sorted(normalized, key=lambda x: x.get('double_low', 0))[:20]

            # 强赎信号：溢价率 < 10 且 105 <= 价格 <= 140
            force_redeem = [
                item for item in normalized
                if item.get('premium_rate', 0) < 10 and 105 <= item.get('price', 0) <= 140
            ][:10]

            # 折价套利：溢价率 < 0
            discount = [item for item in normalized if item.get('premium_rate', 0) < 0][:10]

            # 下修博弈：溢价率 > 50 且 价格 < 115
            down_revised = [
                item for item in normalized
                if item.get('premium_rate', 0) > 50 and item.get('price', 0) < 115
            ][:10]

            return {
                'double_low': double_low,
                'force_redeem': force_redeem,
                'discount': discount,
                'down_revised': down_revised,
            }
        except Exception as e:
            logger.warning(f'[EfinanceSource] get_convertible_signals 失败: {e}')
            return {'double_low': [], 'force_redeem': [], 'discount': [], 'down_revised': []}

    def get_convertible_detail(self, code: str) -> dict:
        """通过 efinance 获取单只可转债详情"""
        try:
            import efinance as ef
            df = ef.bond.get_realtime_quotes()
            if df is None or df.empty:
                return {}

            rows = _map_columns(df, _BOND_COLUMN_MAP)
            if not rows:
                return {}

            normalized = normalize_convertible_list(rows)

            # 查找目标转债
            for item in normalized:
                if str(item.get('bond_code', '')) == str(code):
                    result = dict(item)

                    # 补充缺失字段（与 akshare/mock 保持一致的兜底逻辑）
                    if not result.get('conversion_value'):
                        result['conversion_value'] = 0
                    if not result.get('premium_rate'):
                        result['premium_rate'] = 0

                    # 纯债价值（基于 code 哈希模拟）
                    code_hash = sum(ord(c) for c in str(code))
                    result['pure_bond_value'] = round(90 + (code_hash % 100) / 10.0, 2)

                    # 转股价估算
                    conversion_value = result.get('conversion_value', 0)
                    price = result.get('price', 0)
                    if conversion_value > 0 and price > 0:
                        result['conversion_price'] = round(100 * price / conversion_value, 2)
                    else:
                        result['conversion_price'] = 0

                    # 模拟评级
                    if price >= 150:
                        result['rating'] = 'A+'
                    elif price >= 120:
                        result['rating'] = 'AA'
                    elif price >= 100:
                        result['rating'] = 'AA+'
                    else:
                        result['rating'] = 'AAA'

                    # 模拟到期日期
                    year = 2028 + (code_hash % 5)
                    month = 1 + (code_hash % 12)
                    day = 1 + (code_hash % 28)
                    result['maturity_date'] = f'{year}-{month:02d}-{day:02d}'

                    return result

            return {}
        except Exception as e:
            logger.warning(f'[EfinanceSource] get_convertible_detail 失败: {e}')
            return {}

    def get_convertible_pending(self) -> list:
        """efinance 无待发/配售接口，返回空"""
        return []

    def get_convertible_temperature(self) -> dict:
        """通过 efinance 获取可转债市场温度"""
        try:
            import efinance as ef
            df = ef.bond.get_realtime_quotes()
            if df is None or df.empty:
                return {}

            rows = _map_columns(df, _BOND_COLUMN_MAP)
            if not rows:
                return {}

            normalized = normalize_convertible_list(rows)
            prices = [item['price'] for item in normalized]
            premiums = [item['premium_rate'] for item in normalized]
            double_lows = [item['double_low'] for item in normalized]

            prices_sorted = sorted(prices)
            premiums_sorted = sorted(premiums)
            double_lows_sorted = sorted(double_lows)
            n = len(prices_sorted)

            price_median = prices_sorted[n // 2]
            premium_median = premiums_sorted[n // 2]
            double_low_median = double_lows_sorted[n // 2]

            if double_low_median < 150:
                market_status = '偏低，可关注'
            elif double_low_median < 180:
                market_status = '合理，可适当关注'
            else:
                market_status = '偏高，需谨慎'

            return {
                'count': len(normalized),
                'price_min': min(prices),
                'price_max': max(prices),
                'price_median': round(price_median, 2),
                'premium_median': round(premium_median, 2),
                'double_low_median': round(double_low_median, 1),
                'market_status': market_status,
                'sh_flow': 0,
                'sz_flow': 0,
            }
        except Exception as e:
            logger.warning(f'[EfinanceSource] get_convertible_temperature 失败: {e}')
            return {}

    # ---- LOF ----

    def get_lof_list(self, **kwargs) -> list:
        """通过 efinance 获取 LOF 基金列表"""
        try:
            import efinance as ef
            df = ef.fund.get_realtime_quotes()
            if df is None or df.empty:
                return []

            rows = _map_columns(df, _LOF_COLUMN_MAP)
            if not rows:
                return []

            return normalize_lof_list(rows)
        except Exception as e:
            logger.warning(f'[EfinanceSource] get_lof_list 失败: {e}')
            return []

    def get_lof_opportunities(self) -> dict:
        """通过 efinance 获取 LOF 套利机会"""
        try:
            import efinance as ef
            df = ef.fund.get_realtime_quotes()
            if df is None or df.empty:
                return {'premium': [], 'discount': []}

            rows = _map_columns(df, _LOF_COLUMN_MAP)
            if not rows:
                return {'premium': [], 'discount': []}

            normalized = normalize_lof_list(rows)

            # 按溢价率排序，取 Top 20
            premium = sorted(normalized, key=lambda x: x.get('premium', 0), reverse=True)[:20]
            discount = sorted(normalized, key=lambda x: x.get('premium', 0))[:20]

            return {
                'premium': premium,
                'discount': discount,
            }
        except Exception as e:
            logger.warning(f'[EfinanceSource] get_lof_opportunities 失败: {e}')
            return {'premium': [], 'discount': []}

    def get_lof_summary(self) -> dict:
        """通过 efinance 获取 LOF 市场概览"""
        try:
            import efinance as ef
            df = ef.fund.get_realtime_quotes()
            if df is None or df.empty:
                return {}

            rows = _map_columns(df, _LOF_COLUMN_MAP)
            if not rows:
                return {}

            normalized = normalize_lof_list(rows)
            premiums = [item.get('premium', 0) for item in normalized]
            positive_count = sum(1 for p in premiums if p > 0)

            return {
                'count': len(normalized),
                'premium_avg': round(sum(premiums) / max(len(premiums), 1), 2),
                'top_premium': max(premiums) if premiums else 0,
                'positive_count': positive_count,
                'positive_rate': round(positive_count / max(len(normalized), 1) * 100, 1),
                'paused_count': sum(1 for item in normalized if item.get('limit_status') == '暂停'),
            }
        except Exception as e:
            logger.warning(f'[EfinanceSource] get_lof_summary 失败: {e}')
            return {}

    # ---- 港股 IPO ----

    def get_hk_ipo_list(self, **kwargs) -> list:
        """通过 efinance 获取港股 IPO 列表"""
        try:
            import efinance as ef
            # 尝试 efinance 的港股新股接口（可能不存在，需 try/except）
            df = ef.stock.get_latest_ipo()
            if df is None or df.empty:
                return []

            rows = df.to_dict('records')
            return rows
        except Exception as e:
            logger.warning(f'[EfinanceSource] get_hk_ipo_list 失败: {e}')
            return []

    def get_hk_ipo_upcoming(self) -> list:
        """通过 efinance 获取即将上市的港股 IPO"""
        try:
            import efinance as ef
            df = ef.stock.get_latest_ipo()
            if df is None or df.empty:
                return []

            rows = df.to_dict('records')
            # 过滤即将上市的数据（如有状态字段）
            upcoming = [item for item in rows if '待上市' in str(item.get('上市日期', item.get('status', '')))]
            return upcoming if upcoming else rows
        except Exception as e:
            logger.warning(f'[EfinanceSource] get_hk_ipo_upcoming 失败: {e}')
            return []

    def get_hk_ipo_summary(self) -> dict:
        """通过 efinance 获取港股 IPO 市场概览"""
        try:
            import efinance as ef
            df = ef.stock.get_latest_ipo()
            if df is None or df.empty:
                return {}

            rows = df.to_dict('records')
            return {
                'upcoming_count': len(rows),
                'recent_count': 0,
                'avg_return': 0,
            }
        except Exception as e:
            logger.warning(f'[EfinanceSource] get_hk_ipo_summary 失败: {e}')
            return {}

    # ---- 市场情绪 ----

    def get_market_sentiment(self) -> dict:
        """efinance 无直接市场情绪接口，返回空（工厂会自动降级到其他源）"""
        return {}

    # ---- 资金流向 ----

    def get_fund_flow(self) -> dict:
        """efinance 无直接资金流向接口，返回空（工厂会自动降级到其他源）"""
        return {}

    # ---- 健康检查 ----

    def health_check(self) -> dict:
        """检测 efinance 可用性"""
        try:
            import efinance as ef
            df = ef.bond.get_realtime_quotes()
            if df is not None and not df.empty:
                return {'status': 'ok', 'source': 'efinance', 'record_count': len(df)}
            return {'status': 'degraded', 'source': 'efinance', 'detail': '返回空数据'}
        except Exception as e:
            return {'status': 'error', 'source': 'efinance', 'detail': str(e)}
