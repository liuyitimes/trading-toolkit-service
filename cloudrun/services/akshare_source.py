# -*- coding: utf-8 -*-
"""AkshareSource 实现 — 封装 akshare 实时数据调用"""

import logging

import akshare as ak
import pandas as pd

from services.base import BaseDataSource
from services.convertible_bond import (
    get_market_temperature,
    get_convertible_bond_list,
    get_convertible_bond_detail,
    get_convertible_bond_signals,
    get_pending_bonds,
)
from services.lof_fund import (
    get_lof_list as _raw_lof_list,
    get_lof_opportunities as _raw_lof_opportunities,
    get_lof_market_summary,
)
from services.hk_ipo import (
    get_hk_ipo_list as _raw_hk_ipo_list,
    get_hk_ipo_upcoming as _raw_hk_ipo_upcoming,
    get_hk_ipo_summary as _raw_hk_ipo_summary,
)
from services.normalizer import (
    normalize_lof_list,
)
from utils.convert import safe_float

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


class AkshareSource(BaseDataSource):
    """Akshare 数据源，封装现有 akshare 调用逻辑"""

    # ---- 可转债 ----

    def get_convertible_list(self, **kwargs) -> dict:
        try:
            rows = get_convertible_bond_list()
            if not rows:
                return {'total': 0, 'page': 1, 'page_size': 100, 'items': []}

            # 底层直接输出英文字段，无需 normalize
            return _apply_convertible_filters(rows, **kwargs)
        except Exception as e:
            logger.warning(f'[AkshareSource] get_convertible_list 失败: {e}')
            return {'total': 0, 'page': 1, 'page_size': 100, 'items': []}

    def get_convertible_signals(self) -> dict:
        try:
            raw = get_convertible_bond_signals()
            if not raw:
                return {'double_low': [], 'force_redeem': [], 'discount': [], 'down_revised': []}
            # 底层直接输出英文字段，无需 normalize
            return raw
        except Exception as e:
            logger.warning(f'[AkshareSource] get_convertible_signals 失败: {e}')
            return {'double_low': [], 'force_redeem': [], 'discount': [], 'down_revised': []}

    def get_convertible_detail(self, code: str) -> dict:
        try:
            result = get_convertible_bond_detail(code)
            if not result:
                return result

            # 收集额外的 EM 详情字段
            try:
                df = ak.bond_zh_cov()
                if df is not None and not df.empty:
                    matched = df[df['债券代码'].astype(str) == str(code)]
                    if not matched.empty:
                        bond_row = matched.iloc[0]
                        extra_fields = {
                            'issue_size': safe_float(bond_row.get('发行规模', 0)),
                            'apply_date': str(bond_row.get('申购日期', '')),
                            'lottery_date': str(bond_row.get('中签号发布日', '')),
                            'lottery_rate': safe_float(bond_row.get('中签率', 0)),
                            'apply_code': str(bond_row.get('申购代码', '')),
                            'apply_limit': safe_float(bond_row.get('申购上限', 0)),
                        }
                        for k, v in extra_fields.items():
                            if v not in (None, '', 0):
                                result[k] = v
            except Exception:
                pass

            # 补充分类字段（不在 EM 中的）
            if not result.get('maturity_date'):
                result['maturity_date'] = ''

            return result
        except Exception as e:
            logger.warning(f'[AkshareSource] get_convertible_detail 失败: {e}')
            return {}

    def get_convertible_temperature(self) -> dict:
        try:
            result = get_market_temperature()
            return result if result else {}
        except Exception as e:
            logger.warning(f'[AkshareSource] get_convertible_temperature 失败: {e}')
            return {}

    # ---- 待发/配售 ----

    def get_convertible_pending(self) -> list:
        try:
            rows = get_pending_bonds()
            return rows if rows else []
        except Exception as e:
            logger.warning(f'[AkshareSource] get_convertible_pending 失败: {e}')
            return []

    # ---- LOF ----

    def get_lof_list(self, **kwargs) -> list:
        try:
            rows = _raw_lof_list()
            if not rows:
                return []
            return normalize_lof_list(rows)
        except Exception as e:
            logger.warning(f'[AkshareSource] get_lof_list 失败: {e}')
            return []

    def get_lof_opportunities(self) -> dict:
        try:
            raw = _raw_lof_opportunities()
            if not raw:
                return {'premium': [], 'discount': []}
            return {
                'premium': normalize_lof_list(raw.get('premium', [])),
                'discount': normalize_lof_list(raw.get('discount', [])),
            }
        except Exception as e:
            logger.warning(f'[AkshareSource] get_lof_opportunities 失败: {e}')
            return {'premium': [], 'discount': []}

    def get_lof_summary(self) -> dict:
        try:
            result = get_lof_market_summary()
            return result if result else {}
        except Exception as e:
            logger.warning(f'[AkshareSource] get_lof_summary 失败: {e}')
            return {}

    # ---- 港股 IPO ----

    def get_hk_ipo_list(self, **kwargs) -> list:
        try:
            return _raw_hk_ipo_list()
        except Exception as e:
            logger.warning(f'[AkshareSource] get_hk_ipo_list 失败: {e}')
            return []

    def get_hk_ipo_upcoming(self) -> list:
        try:
            return _raw_hk_ipo_upcoming()
        except Exception as e:
            logger.warning(f'[AkshareSource] get_hk_ipo_upcoming 失败: {e}')
            return []

    def get_hk_ipo_summary(self) -> dict:
        try:
            return _raw_hk_ipo_summary()
        except Exception as e:
            logger.warning(f'[AkshareSource] get_hk_ipo_summary 失败: {e}')
            return {}

    # ---- 市场情绪 ----

    def get_market_sentiment(self) -> dict:
        """使用 akshare 获取市场情绪数据（新浪指数+乐咕涨跌家数）"""
        result = {}

        # 1. 新浪指数实时行情（最准确的指数点位和成交额）
        try:
            df = ak.stock_zh_index_spot_sina()
            if df is not None and not df.empty:
                index_map = {
                    'sh000001': 'sh',
                    'sz399001': 'sz',
                    'sz399006': 'cyb',
                    'sh000300': 'hs300',
                    'sh000852': 'zz1000',
                }
                for _, row in df.iterrows():
                    code = str(row.get('代码', ''))
                    if code not in index_map:
                        continue
                    prefix = index_map[code]
                    price = safe_float(row.get('最新价', 0))
                    change_pct = safe_float(row.get('涨跌幅', 0))
                    change_amount = safe_float(row.get('涨跌额', 0))
                    volume = safe_float(row.get('成交量', 0))
                    amount = safe_float(row.get('成交额', 0))

                    if prefix == 'sh':
                        result['sh_price'] = round(price, 2)
                        result['sh_change'] = round(change_pct, 2)
                        result['sh_change_amount'] = round(change_amount, 2)
                        result['sh_volume'] = round(amount / 1e8, 0)
                    elif prefix == 'sz':
                        result['sz_price'] = round(price, 2)
                        result['sz_change'] = round(change_pct, 2)
                        result['sz_change_amount'] = round(change_amount, 2)
                        result['sz_volume'] = round(amount / 1e8, 0)
                    elif prefix == 'cyb':
                        result['cyb_price'] = round(price, 2)
                        result['cyb_change'] = round(change_pct, 2)
                        result['cyb_change_amount'] = round(change_amount, 2)
                    elif prefix == 'hs300':
                        result['hs300_price'] = round(price, 2)
                        result['hs300_change'] = round(change_pct, 2)
                    elif prefix == 'zz1000':
                        result['zz1000_price'] = round(price, 2)
                        result['zz1000_change'] = round(change_pct, 2)
        except Exception as e:
            logger.warning(f'[AkshareSource] 新浪指数行情失败: {e}')

        # 1.5 北交所成交额（通过bj899050日线推算）
        if result.get('sh_volume', 0) > 0:
            try:
                bj_df = ak.stock_zh_index_daily(symbol='bj899050')
                if bj_df is not None and len(bj_df) >= 1:
                    sh_daily_df = ak.stock_zh_index_daily(symbol='sh000001')
                    if sh_daily_df is not None and len(sh_daily_df) >= 1:
                        sh_vol_daily = float(sh_daily_df.iloc[-1]['volume'])
                        bj_vol_daily = float(bj_df.iloc[-1]['volume'])
                        sh_amount_yi = result['sh_volume']
                        if sh_vol_daily > 0:
                            bj_amount = round(bj_vol_daily * sh_amount_yi * 1e8 / sh_vol_daily / 1e8, 0)
                            result['bj_volume'] = int(bj_amount)
            except Exception as e:
                logger.warning(f'[AkshareSource] 北交所成交额计算失败: {e}')

        # 沪深京三市总成交额
        bj_vol = result.get('bj_volume', 0) or 0
        result['total_volume'] = round(result.get('sh_volume', 0) + result.get('sz_volume', 0) + bj_vol, 0)

        # 2. 乐咕涨跌家数（item/value 格式）
        try:
            df = ak.stock_market_activity_legu()
            if df is not None and not df.empty:
                legu = {}
                for _, row in df.iterrows():
                    item = str(row.get('item', '')).strip()
                    val = str(row.get('value', '')).strip()
                    legu[item] = val

                # 上涨/下跌/平盘家数
                result['sh_up_count'] = int(safe_float(legu.get('上涨', 0)))
                result['sh_down_count'] = int(safe_float(legu.get('下跌', 0)))
                result['sh_flat_count'] = int(safe_float(legu.get('平盘', 0)))

                # 涨停/跌停
                result['sh_limit_up'] = int(safe_float(legu.get('涨停', 0)))
                result['sh_limit_down'] = int(safe_float(legu.get('跌停', 0)))

                # 计算情绪分数（多因子加权）
                up = result['sh_up_count']
                down = result['sh_down_count']
                total = up + down
                if total > 0:
                    up_ratio = up / total
                    ratio_score = up_ratio * 100

                    # 因子2: 量能趋势分 (0-100) — 权重40%
                    # 对比昨日成交量和5日均量（统一用成交额亿元）
                    vol_trend_score = 50
                    prev_volume = 0
                    volume_change_pct = 0
                    volume_5d_avg = 0
                    volume_5d_change_pct = 0
                    try:
                        idx_df = ak.stock_zh_index_daily(symbol='sh000001')
                        if idx_df is not None and len(idx_df) >= 6:
                            vol_today_daily = float(idx_df.iloc[-1]['volume'])
                            vol_prev_daily = float(idx_df.iloc[-2]['volume'])
                            vol_5d_list = [float(idx_df.iloc[-1 - i]['volume']) for i in range(5)]
                            vol_5d_avg_raw = sum(vol_5d_list) / 5

                            # 用新浪今日成交额(亿元) ÷ 今日成交量(股) 算出均价，再换算历史成交额
                            today_amount_yi = result.get('sh_volume', 0)
                            if today_amount_yi and vol_today_daily > 0:
                                price_per_share = today_amount_yi * 1e8 / vol_today_daily
                                prev_volume = round(vol_prev_daily * price_per_share / 1e8, 0)
                                vol_5d_avg = round(vol_5d_avg_raw * price_per_share / 1e8, 0)
                                volume_change_pct = round((vol_today_daily / vol_prev_daily - 1) * 100, 1)
                                volume_5d_change_pct = round((vol_today_daily / vol_5d_avg_raw - 1) * 100, 1)
                            else:
                                prev_volume = round(vol_prev_daily / 1e8, 0)
                                vol_5d_avg = round(vol_5d_avg_raw / 1e8, 0)
                                volume_change_pct = round((vol_today_daily / vol_prev_daily - 1) * 100, 1)
                                volume_5d_change_pct = round((vol_today_daily / vol_5d_avg_raw - 1) * 100, 1)

                            # 单日量比得分：量比1.0=50分, 1.5=100分, 0.5=0分
                            day_ratio = vol_today_daily / vol_prev_daily
                            day_score = max(0, min(100, 50 + (day_ratio - 1) * 100))
                            # 5日均量得分
                            avg_ratio = vol_today_daily / vol_5d_avg_raw
                            avg_score = max(0, min(100, 50 + (avg_ratio - 1) * 100))
                            # 综合量能趋势分
                            vol_trend_score = round((day_score + avg_score) / 2, 1)
                    except Exception as e:
                        logger.warning(f'[AkshareSource] 计算量能趋势失败: {e}')

                    result['vol_trend_score'] = vol_trend_score
                    result['prev_volume'] = float(prev_volume)
                    result['volume_change_pct'] = volume_change_pct
                    result['volume_5d_avg'] = float(vol_5d_avg)
                    result['volume_5d_change_pct'] = volume_5d_change_pct

                    # 综合情绪分 = 涨跌分×60% + 量能趋势分×40%
                    sentiment_score = ratio_score * 0.6 + vol_trend_score * 0.4
                    result['sentiment_score'] = round(sentiment_score, 1)
                    result['sh_score'] = round(up_ratio * 100, 1)
        except Exception as e:
            logger.warning(f'[AkshareSource] stock_market_activity_legu 失败: {e}')

        # 3. 深证指数走势（用新浪数据兜底，如果新浪失败则用日线）
        if 'sz_change' not in result:
            try:
                sz_df = ak.stock_zh_index_daily(symbol='sz399001')
                if sz_df is not None and len(sz_df) >= 2:
                    latest = sz_df.iloc[-1]
                    prev = sz_df.iloc[-2]
                    result['sz_volume'] = round(safe_float(latest.get('volume', 0)) / 1e8, 0)
                    prev_close = safe_float(prev.get('close', 0))
                    curr_close = safe_float(latest.get('close', 0))
                    if prev_close > 0:
                        result['sz_change'] = round((curr_close - prev_close) / prev_close * 100, 2)
            except Exception as e:
                logger.warning(f'[AkshareSource] 获取深证指数日线失败: {e}')

        # 构造标准化返回
        standard_keys = [
            'sentiment_score', 'vol_trend_score', 'prev_volume', 'volume_change_pct',
            'volume_5d_avg', 'volume_5d_change_pct',
            'sh_score', 'sz_score', 'sh_volume', 'sz_volume', 'bj_volume',
            'total_volume', 'north',
            'sh_change', 'sz_change', 'sh_up_count', 'sh_down_count',
            'sz_up_count', 'sz_down_count', 'sh_price', 'sz_price',
            'cyb_price', 'cyb_change', 'hs300_price', 'hs300_change',
            'zz1000_price', 'zz1000_change', 'sh_flat_count',
            'sh_limit_up', 'sh_limit_down', 'sh_change_amount',
            'sz_change_amount', 'cyb_change_amount',
        ]
        result.setdefault('sentiment_score', result.get('sh_score', 50))
        result.setdefault('vol_trend_score', 50)
        result.setdefault('prev_volume', 0)
        result.setdefault('volume_change_pct', 0)
        result.setdefault('volume_5d_avg', 0)
        result.setdefault('volume_5d_change_pct', 0)
        result.setdefault('sz_score', result.get('sh_score', 0))
        result.setdefault('sz_up_count', 0)
        result.setdefault('sz_down_count', 0)
        result.setdefault('bj_volume', 0)
        result.setdefault('total_volume', 0)
        result.setdefault('north', 0)

        standardized = {k: result.get(k, 0) for k in standard_keys}
        has_real_data = any(v != 0 for k, v in standardized.items() 
                          if k not in ['sentiment_score', 'vol_trend_score', 'prev_volume', 'volume_change_pct', 'volume_5d_avg', 'volume_5d_change_pct', 'sh_score', 'north', 'sz_up_count', 'sz_down_count', 'sz_score'])
        if not has_real_data:
            return {}
        return standardized

    # ---- 资金流向 ----

    def get_fund_flow(self) -> dict:
        """使用 akshare 获取行业板块资金流向（stock_fund_flow_industry）"""
        result = {}

        try:
            df = ak.stock_fund_flow_industry()
            if df is None or df.empty:
                return {}

            sectors = []
            for _, row in df.iterrows():
                name = str(row.get('行业', ''))
                if not name:
                    continue
                net_flow = safe_float(row.get('净额', 0))
                inflow = safe_float(row.get('流入资金', 0))
                outflow = safe_float(row.get('流出资金', 0))
                change_pct = safe_float(row.get('行业-涨跌幅', 0))
                leader = str(row.get('领涨股', ''))
                leader_change = safe_float(row.get('领涨股-涨跌幅', 0))
                company_count = int(safe_float(row.get('公司家数', 0)))

                sectors.append({
                    'name': name,
                    'flow': round(net_flow, 2),
                    'inflow': round(inflow, 2),
                    'outflow': round(outflow, 2),
                    'change_pct': round(change_pct, 2),
                    'leader': leader,
                    'leader_change': round(leader_change, 2),
                    'company_count': company_count,
                })

            # 按净流入排序
            sectors.sort(key=lambda x: x['flow'], reverse=True)

            # 大盘资金净流入（所有板块净流入总和）
            total_inflow = round(sum(s['flow'] for s in sectors if s['flow'] > 0), 2)
            total_outflow = round(sum(s['flow'] for s in sectors if s['flow'] < 0), 2)
            net_inflow = round(total_inflow + total_outflow, 2)

            result['total_inflow'] = total_inflow
            result['total_outflow'] = abs(total_outflow)
            result['net_inflow'] = net_inflow

            # Top 流入和流出
            top_inflow = [s for s in sectors if s['flow'] > 0][:10]
            top_outflow = sorted([s for s in sectors if s['flow'] < 0], key=lambda x: x['flow'])[:10]

            result['sectors'] = sectors
            result['top_inflow'] = top_inflow
            result['top_outflow'] = top_outflow
            result['total_count'] = len(sectors)

        except Exception as e:
            logger.warning(f'[AkshareSource] 获取行业板块资金流向失败: {e}')
            return {}

        if not result.get('sectors'):
            return {}

        return result

    # ---- 健康检查 ----

    def health_check(self) -> dict:
        """尝试调用 akshare 检测可用性"""
        try:
            df = ak.bond_cb_jsl()
            if df is not None and not df.empty:
                return {'status': 'ok', 'source': 'akshare', 'record_count': len(df)}
            return {'status': 'degraded', 'source': 'akshare', 'detail': '返回空数据'}
        except Exception as e:
            return {'status': 'error', 'source': 'akshare', 'detail': str(e)}
