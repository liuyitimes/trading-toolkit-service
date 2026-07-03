# -*- coding: utf-8 -*-
"""TushareSource 实现 — 封装 tushare 数据接口"""

import datetime
import logging
import os

from services.base import BaseDataSource

logger = logging.getLogger('trading_toolkit')


def _safe_float(value, default=0.0):
    """安全转换为 float"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class TushareSource(BaseDataSource):
    """Tushare 数据源，通过 TUSHARE_TOKEN 环境变量初始化"""

    def __init__(self):
        self.token = os.environ.get('TUSHARE_TOKEN', '')
        self.pro = None
        if self.token:
            try:
                import tushare as ts
                ts.set_token(self.token)
                self.pro = ts.pro_api()
            except Exception as e:
                logger.error(f'tushare 初始化失败: {e}')

    # ---- 可转债 ----

    def get_convertible_list(self, **kwargs):
        """获取可转债列表"""
        if not self.pro:
            return {'total': 0, 'page': 1, 'page_size': 100, 'items': []}
        try:
            df_basic = self.pro.cb_basic(
                fields='ts_code,bond_short_name,stk_code,stk_short_name,'
                       'maturity_date,rating,issue_size'
            )
            if df_basic is None or df_basic.empty:
                return {'total': 0, 'page': 1, 'page_size': 100, 'items': []}

            result = []
            for _, row in df_basic.iterrows():
                ts_code = str(row.get('ts_code', ''))
                bond_code = ts_code.split('.')[0] if '.' in ts_code else ts_code
                exchange_suffix = ts_code.split('.')[-1].lower() if '.' in ts_code else ''
                exchange = 'sh' if exchange_suffix == 'sh' else 'sz' if exchange_suffix == 'sz' else ''

                result.append({
                    'bond_code': bond_code,
                    'bond_name': row.get('bond_short_name', ''),
                    'stock_code': str(row.get('stk_code', '')),
                    'stock_name': row.get('stk_short_name', ''),
                    'exchange': exchange,
                    'price': 0,
                    'conversion_value': 0,
                    'premium_rate': 0,
                    'double_low': 0,
                    'maturity_date': str(row.get('maturity_date', '')),
                    'rating': row.get('rating', ''),
                    'remaining_size': _safe_float(row.get('issue_size')),
                })

            return self._apply_filters(result, **kwargs)
        except Exception as e:
            logger.error(f'tushare 获取可转债列表失败: {e}')
            return {'total': 0, 'page': 1, 'page_size': 100, 'items': []}

    def _apply_filters(self, items: list, **kwargs) -> dict:
        """对数据进行筛选、排序和分页"""
        filtered = list(items)

        exchange = kwargs.get('exchange')
        if exchange:
            filtered = [i for i in filtered if i.get('exchange') == exchange]

        min_price = kwargs.get('min_price')
        if min_price is not None:
            filtered = [i for i in filtered if i.get('price', 0) >= min_price]

        max_price = kwargs.get('max_price')
        if max_price is not None:
            filtered = [i for i in filtered if i.get('price', 0) <= max_price]

        max_premium = kwargs.get('max_premium')
        if max_premium is not None:
            filtered = [i for i in filtered if i.get('premium_rate', 0) <= max_premium]

        sort = kwargs.get('sort', 'double_low')
        if sort == 'double_low':
            filtered.sort(key=lambda x: x.get('double_low', 0))
        elif sort == 'price':
            filtered.sort(key=lambda x: x.get('price', 0))
        elif sort == 'premium':
            filtered.sort(key=lambda x: x.get('premium_rate', 0))
        elif sort == 'premium_desc':
            filtered.sort(key=lambda x: x.get('premium_rate', 0), reverse=True)

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

    def get_convertible_signals(self):
        """获取可转债信号"""
        if not self.pro:
            return {'double_low': [], 'force_redeem': [], 'discount': [], 'down_revised': []}
        try:
            data = self.get_convertible_list()
            if not data or not isinstance(data, dict) or not data.get('items'):
                return {'double_low': [], 'force_redeem': [], 'discount': [], 'down_revised': []}

            items = data['items']
            return {
                'double_low': sorted(items, key=lambda x: x.get('double_low', 999))[:20],
                'force_redeem': [i for i in items if i.get('premium_rate', 0) < 10 and 105 <= i.get('price', 0) <= 140][:10],
                'discount': [i for i in items if i.get('premium_rate', 0) < 0][:10],
                'down_revised': [i for i in items if i.get('premium_rate', 0) > 50 and i.get('price', 0) < 115][:10],
            }
        except Exception as e:
            logger.error(f'tushare 获取可转债信号失败: {e}')
            return {'double_low': [], 'force_redeem': [], 'discount': [], 'down_revised': []}

    def get_convertible_detail(self, code: str):
        """获取单只可转债详情"""
        if not self.pro:
            return {}
        try:
            ts_code = f'{code}.SH' if code.startswith('11') else f'{code}.SZ'
            df = self.pro.cb_basic(ts_code=ts_code)
            if df is None or df.empty:
                return {}

            row = df.iloc[0]
            return {
                'bond_code': code,
                'bond_name': row.get('bond_short_name', ''),
                'stock_code': str(row.get('stk_code', '')),
                'stock_name': row.get('stk_short_name', ''),
                'exchange': 'sh' if code.startswith('11') else 'sz',
                'price': 0,
                'conversion_value': 0,
                'premium_rate': 0,
                'double_low': 0,
                'pure_bond_value': 0,
                'conversion_price': 0,
                'rating': row.get('rating', ''),
                'maturity_date': str(row.get('maturity_date', '')),
            }
        except Exception as e:
            logger.error(f'tushare 获取可转债详情失败: {e}')
            return {}

    def get_convertible_pending(self):
        """待发可转债（tushare 无此接口）"""
        return []

    def get_convertible_temperature(self):
        """获取可转债市场温度（tushare 无直接接口，返回空让工厂降级）"""
        return {}

    # ---- LOF ----

    def get_lof_list(self, **kwargs):
        """获取 LOF 基金列表"""
        if not self.pro:
            return []
        try:
            df = self.pro.fund_basic(market='L')
            if df is None or df.empty:
                return []

            result = []
            for _, row in df.iterrows():
                ts_code = str(row.get('ts_code', ''))
                code = ts_code.split('.')[0] if '.' in ts_code else ts_code
                exchange = 'sh' if '.SH' in ts_code.upper() else 'sz'

                result.append({
                    'code': code,
                    'name': row.get('name', ''),
                    'price': 0,
                    'change_pct': 0,
                    'valuation': 0,
                    'premium': 0,
                    'consecutive_premium': 0,
                    'limit_status': '--',
                    'exchange': exchange,
                })

            return result
        except Exception as e:
            logger.error(f'tushare 获取 LOF 列表失败: {e}')
            return []

    def get_lof_opportunities(self):
        """获取 LOF 套利机会（需要实时溢价率，tushare 不直接提供）"""
        return {'premium': [], 'discount': []}

    def get_lof_summary(self):
        """获取 LOF 市场概览"""
        return {}

    # ---- 港股 IPO ----

    def get_hk_ipo_list(self, **kwargs):
        """获取港股 IPO 列表（tushare 港股数据有限）"""
        return []

    def get_hk_ipo_upcoming(self):
        """获取申购中/即将上市的港股 IPO"""
        return []

    def get_hk_ipo_summary(self):
        """获取港股打新市场概览"""
        return {}

    # ---- 市场情绪 ----

    def get_market_sentiment(self):
        """获取 A 股市场情绪"""
        if not self.pro:
            return {}
        try:
            today = datetime.date.today().strftime('%Y%m%d')
            result = {}

            # 获取上证指数
            sh_df = self.pro.index_daily(ts_code='000001.SH', start_date=today)
            if sh_df is not None and not sh_df.empty:
                sh = sh_df.iloc[0]
                result['sh_change'] = _safe_float(sh.get('pct_chg'))
                result['sh_volume'] = round(_safe_float(sh.get('vol')) / 10000, 0)

            # 获取深证指数
            sz_df = self.pro.index_daily(ts_code='399001.SZ', start_date=today)
            if sz_df is not None and not sz_df.empty:
                sz = sz_df.iloc[0]
                result['sz_change'] = _safe_float(sz.get('pct_chg'))
                result['sz_volume'] = round(_safe_float(sz.get('vol')) / 10000, 0)

            # 标准化字段补全
            result.setdefault('sentiment_score', 50)
            result.setdefault('sh_score', 50)
            result.setdefault('sz_score', 50)
            result.setdefault('sh_up_count', 0)
            result.setdefault('sh_down_count', 0)
            result.setdefault('sz_up_count', 0)
            result.setdefault('sz_down_count', 0)
            result.setdefault('north', 0)

            return result if result else {}
        except Exception as e:
            logger.error(f'tushare 获取市场情绪失败: {e}')
            return {}

    # ---- 资金流向 ----

    def get_fund_flow(self):
        """获取资金流向"""
        if not self.pro:
            return {}
        try:
            today = datetime.date.today().strftime('%Y%m%d')
            df = self.pro.moneyflow_hsgt(start_date=today, end_date=today)
            if df is None or df.empty:
                return {}

            row = df.iloc[0]
            north = _safe_float(row.get('north_money')) / 10000  # 转换为亿

            result = {
                'north': round(north, 2),
                'north_5d': [],
                'north_5d_dates': [],
                'sh': 0,
                'sz': 0,
            }

            if result['north'] == 0:
                return {}
            return result
        except Exception as e:
            logger.error(f'tushare 获取资金流向失败: {e}')
            return {}

    # ---- 健康检查 ----

    def health_check(self):
        """健康检查"""
        if not self.token:
            return {'status': 'not_configured', 'source': 'tushare', 'message': 'TUSHARE_TOKEN 未配置'}
        if not self.pro:
            return {'status': 'error', 'source': 'tushare', 'message': 'tushare 初始化失败'}
        try:
            df = self.pro.trade_cal(exchange='SSE', start_date='20260101', end_date='20260102')
            if df is not None and not df.empty:
                return {'status': 'ok', 'source': 'tushare'}
            return {'status': 'error', 'source': 'tushare', 'message': '接口测试失败'}
        except Exception as e:
            return {'status': 'error', 'source': 'tushare', 'message': str(e)}
