# -*- coding: utf-8 -*-
"""MockSource 实现 — 基于 mock_data.py 提供离线数据"""

import os
import sys

# mock_data.py 位于 cloudrun/ 目录，需要加入搜索路径
_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent not in sys.path:
    sys.path.insert(0, _parent)

from mock_data import (
    CONVERTIBLE_BOND_LIST,
    LOF_LIST,
    HK_IPO_LIST,
    MARKET_SENTIMENT,
    FUND_FLOW,
)
from services.base import BaseDataSource
from services.normalizer import (
    normalize_convertible_list,
    normalize_lof_list,
)


def _apply_convertible_filters(items: list, **kwargs) -> dict:
    """对标准化后的可转债数据进行筛选、排序和分页

    Args:
        items: 标准化后的可转债列表
        **kwargs: 筛选和分页参数
            - exchange: 交易所筛选 (sh/sz/bj)
            - sort: 排序方式 (double_low/price/premium/premium_desc)
            - min_price: 最低价格
            - max_price: 最高价格
            - max_premium: 最高溢价率
            - page: 页码 (默认 1)
            - page_size: 每页大小 (默认 100)

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


def _get_exchange_by_code(code: str) -> str:
    """根据正股代码判断交易所标识"""
    if code.startswith(('6', '5', '9', '11', '13')):
        return '沪'
    elif code.startswith(('0', '1', '2', '3', '12')):
        return '深'
    elif code.startswith(('4', '8')):
        return '北'
    return ''


class MockSource(BaseDataSource):
    """Mock 数据源，使用本地静态数据"""

    # ---- 可转债 ----

    def get_convertible_list(self, **kwargs) -> dict:
        # 构造原始数据并补充交易所字段
        rows = []
        for item in CONVERTIBLE_BOND_LIST:
            row = dict(item)
            row.setdefault('交易所', _get_exchange_by_code(str(item.get('正股代码', ''))))
            rows.append(row)

        # 先 normalize 数据
        normalized = normalize_convertible_list(rows)

        # 在标准化数据上做筛选、排序、分页
        return _apply_convertible_filters(normalized, **kwargs)

    def get_convertible_signals(self) -> dict:
        data = []
        for item in CONVERTIBLE_BOND_LIST:
            row = dict(item)
            row.setdefault('交易所', _get_exchange_by_code(str(item.get('正股代码', ''))))
            data.append(row)

        # 双低策略 Top20
        double_low = sorted(data, key=lambda x: x['双低'])[:20]
        # 强赎信号：溢价率<10 且 105<=价格<=140
        force_redeem = [
            item for item in data
            if item['转股溢价率'] < 10 and 105 <= item['转债价格'] <= 140
        ][:10]
        # 折价套利：溢价率<0
        discount = [item for item in data if item['转股溢价率'] < 0][:10]
        # 下修博弈：溢价率>50 且 价格<115
        down_revised = [
            item for item in data
            if item['转股溢价率'] > 50 and item['转债价格'] < 115
        ][:10]

        return {
            'double_low': normalize_convertible_list(double_low),
            'force_redeem': normalize_convertible_list(force_redeem),
            'discount': normalize_convertible_list(discount),
            'down_revised': normalize_convertible_list(down_revised),
        }

    def get_convertible_detail(self, code: str) -> dict:
        for item in CONVERTIBLE_BOND_LIST:
            if str(item.get('转债代码')) == str(code):
                row = dict(item)
                row.setdefault('交易所', _get_exchange_by_code(str(item.get('正股代码', ''))))
                result = normalize_convertible_list([row])[0]

                # 增强返回数据：纯债价值（基于 code 哈希模拟 90-100 范围）
                code_hash = sum(ord(c) for c in str(code))
                result['pure_bond_value'] = round(90 + (code_hash % 100) / 10.0, 2)

                # 转股价格：根据价格和转股价值反算
                conversion_value = result.get('conversion_value', 0)
                price = result.get('price', 0)
                if conversion_value > 0 and price > 0:
                    # 转股价值 = 100 / 转股价 * 正股价，所以转股价 = 100 * 正股价 / 转股价值
                    # 这里近似用 100 * price / conversion_value 估算
                    result['conversion_price'] = round(100 * price / conversion_value, 2)
                else:
                    result['conversion_price'] = 0

                # 模拟评级（基于价格范围）
                if price >= 150:
                    result['rating'] = 'A+'
                elif price >= 120:
                    result['rating'] = 'AA'
                elif price >= 100:
                    result['rating'] = 'AA+'
                else:
                    result['rating'] = 'AAA'

                # 模拟到期日期（2028-2032 范围）
                year = 2028 + (code_hash % 5)
                month = 1 + (code_hash % 12)
                day = 1 + (code_hash % 28)
                result['maturity_date'] = f'{year}-{month:02d}-{day:02d}'

                return result
        return {}

    def get_convertible_temperature(self) -> dict:
        prices = [item['转债价格'] for item in CONVERTIBLE_BOND_LIST]
        premiums = [item['转股溢价率'] for item in CONVERTIBLE_BOND_LIST]
        double_lows = [item['双低'] for item in CONVERTIBLE_BOND_LIST]

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
            'count': len(CONVERTIBLE_BOND_LIST),
            'price_min': min(prices),
            'price_max': max(prices),
            'price_median': round(price_median, 2),
            'premium_median': round(premium_median, 2),
            'double_low_median': round(double_low_median, 1),
            'market_status': market_status,
            'sh_flow': 18.32,
            'sz_flow': 14.24,
        }

    # ---- LOF ----

    def get_lof_list(self, **kwargs) -> list:
        return normalize_lof_list(LOF_LIST)

    def get_lof_opportunities(self) -> dict:
        normalized = normalize_lof_list(LOF_LIST)
        sorted_premium = sorted(normalized, key=lambda x: x['premium'], reverse=True)[:20]
        sorted_discount = sorted(normalized, key=lambda x: x['premium'])[:20]
        return {
            'premium': sorted_premium,
            'discount': sorted_discount,
        }

    def get_lof_summary(self) -> dict:
        premiums = [item['溢价率'] for item in LOF_LIST]
        positive_count = sum(1 for p in premiums if p > 0)
        return {
            'count': len(LOF_LIST),
            'premium_avg': round(sum(premiums) / len(premiums), 2),
            'top_premium': max(premiums),
            'positive_count': positive_count,
            'positive_rate': round(positive_count / len(LOF_LIST) * 100, 1),
            'paused_count': sum(1 for item in LOF_LIST if item['申购状态'] == '暂停'),
        }

    # ---- 港股 IPO ----

    def get_hk_ipo_list(self, **kwargs) -> list:
        return HK_IPO_LIST

    def get_hk_ipo_upcoming(self) -> list:
        return [item for item in HK_IPO_LIST if item.get('status') == '申购中']

    def get_hk_ipo_summary(self) -> dict:
        upcoming_count = sum(1 for item in HK_IPO_LIST if item.get('status') == '申购中')
        recent_count = sum(1 for item in HK_IPO_LIST if item.get('status') == '已上市')
        listed = [item for item in HK_IPO_LIST if item.get('status') == '已上市']
        avg_return = sum(item.get('change_pct', 0) for item in listed) / max(recent_count, 1)
        return {
            'upcoming_count': upcoming_count,
            'recent_count': recent_count,
            'avg_return': round(avg_return, 1),
        }

    # ---- 市场情绪 & 资金流向 ----

    def get_market_sentiment(self) -> dict:
        result = dict(MARKET_SENTIMENT)
        result.setdefault('sentiment_score', 50)
        result.setdefault('north', FUND_FLOW.get('north', 32.56))
        return result

    def get_fund_flow(self) -> dict:
        sectors = [
            {'name': '半导体', 'flow': 80.68, 'inflow': 2587.41, 'outflow': 2506.73, 'change_pct': 2.21, 'leader': '北京君正', 'leader_change': 20.00, 'company_count': 180},
            {'name': '证券', 'flow': 57.78, 'inflow': 371.72, 'outflow': 313.95, 'change_pct': 3.06, 'leader': '长江证券', 'leader_change': 9.97, 'company_count': 50},
            {'name': '元件', 'flow': 112.24, 'inflow': 812.05, 'outflow': 699.80, 'change_pct': 3.14, 'leader': '三环集团', 'leader_change': 12.64, 'company_count': 62},
            {'name': '白酒', 'flow': 6.09, 'inflow': 68.70, 'outflow': 62.60, 'change_pct': 1.64, 'leader': '酒鬼酒', 'leader_change': 7.20, 'company_count': 19},
            {'name': '银行', 'flow': -5.45, 'inflow': 54.50, 'outflow': 59.95, 'change_pct': -0.23, 'leader': '招商银行', 'leader_change': 1.20, 'company_count': 42},
            {'name': '医药', 'flow': -12.34, 'inflow': 320.50, 'outflow': 332.84, 'change_pct': -0.85, 'leader': '恒瑞医药', 'leader_change': 2.10, 'company_count': 350},
            {'name': '新能源', 'flow': -25.67, 'inflow': 450.30, 'outflow': 475.97, 'change_pct': -1.25, 'leader': '宁德时代', 'leader_change': -0.80, 'company_count': 200},
            {'name': '消费', 'flow': -8.90, 'inflow': 180.20, 'outflow': 189.10, 'change_pct': -0.45, 'leader': '贵州茅台', 'leader_change': 0.50, 'company_count': 120},
            {'name': '军工', 'flow': 3.89, 'inflow': 95.60, 'outflow': 91.71, 'change_pct': 0.80, 'leader': '中航沈飞', 'leader_change': 3.20, 'company_count': 85},
            {'name': '地产', 'flow': -2.67, 'inflow': 42.30, 'outflow': 44.97, 'change_pct': -0.60, 'leader': '万科A', 'leader_change': -1.20, 'company_count': 110},
        ]
        sectors.sort(key=lambda x: x['flow'], reverse=True)
        top_inflow = [s for s in sectors if s['flow'] > 0][:10]
        top_outflow = sorted([s for s in sectors if s['flow'] < 0], key=lambda x: x['flow'])[:10]
        return {
            'sectors': sectors,
            'top_inflow': top_inflow,
            'top_outflow': top_outflow,
            'total_count': len(sectors),
        }

    # ---- 健康检查 ----

    def health_check(self) -> dict:
        return {'status': 'ok', 'source': 'mock'}
