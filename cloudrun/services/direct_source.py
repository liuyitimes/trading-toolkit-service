# -*- coding: utf-8 -*-
"""DirectSource — 单一直连数据源，委托各 domain service 获取数据。

设计依据：ADR-001 / ADR-002 / ADR-004
  - 移除 akshare/efinance/tushare 全部依赖
  - 所有数据通过 http_client.py 直连上游 HTTP API
  - 可转债 / LOF / 封闭式基金 / 港股IPO 委托对应 domain service
  - 市场情绪 / 资金流向 在本文件内直连实现
  - 无降级链（单源），失败时由上层 fetch_with_stale_fallback 返回 stale cache
"""

import json
import logging
import time

import pandas as pd

from services.base import BaseDataSource
from services.convertible_bond import (
    get_market_temperature,
    get_convertible_bond_list,
    get_convertible_new_listed,
    get_convertible_bond_detail,
    get_convertible_bond_signals,
    get_pending_bonds,
)
from services.lof_fund import (
    get_lof_list as _raw_lof_list,
    get_lof_opportunities as _raw_lof_opportunities,
    get_lof_market_summary,
)
from services.closed_end import (
    get_closed_end_list as _raw_closed_end_list,
    get_closed_end_summary as _raw_closed_end_summary,
)
from services.hk_ipo import (
    get_hk_ipo_list as _raw_hk_ipo_list,
    get_hk_ipo_upcoming as _raw_hk_ipo_upcoming,
    get_hk_ipo_summary as _raw_hk_ipo_summary,
    get_hk_ipo_detail as _raw_hk_ipo_detail,
)
from services.http_client import sina_get, em_get, legu_get, ths_get
from services.normalizer import normalize_lof_list
from utils.convert import safe_float

logger = logging.getLogger('trading_toolkit')


# ==================== 可转债筛选工具 ====================


def _apply_convertible_filters(items: list, **kwargs) -> dict:
    """对标准化后的可转债数据进行筛选、排序和分页"""
    filtered = list(items)

    exchange = kwargs.get('exchange')
    if exchange:
        filtered = [item for item in filtered if item.get('exchange') == exchange]

    min_price = kwargs.get('min_price')
    if min_price is not None:
        filtered = [item for item in filtered if item.get('price', 0) >= min_price]

    max_price = kwargs.get('max_price')
    if max_price is not None:
        filtered = [item for item in filtered if item.get('price', 0) <= max_price]

    max_premium = kwargs.get('max_premium')
    if max_premium is not None:
        filtered = [item for item in filtered if item.get('premium_rate', 0) <= max_premium]

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


# ==================== 市场情绪直连实现 ====================

_SINA_INDEX_URL = (
    "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "Market_Center.getHQNodeDataSimple"
)
_SINA_INDEX_COUNT_URL = (
    "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "Market_Center.getHQNodeStockCountSimple?node=hs_s"
)
_LEGU_ACTIVITY_URL = "https://legulegu.com/stockdata/market-activity"

# 指数代码 → 输出 key 前缀映射
_INDEX_MAP = {
    'sh000001': 'sh',
    'sz399001': 'sz',
    'sz399006': 'cyb',
    'sh000300': 'hs300',
    'sh000852': 'zz1000',
}

# 量能趋势缓存（模块级，用于今日 vs 昨日成交量比较）
_VOL_HISTORY = {}  # date_str -> {sh_volume, sz_volume}
_VOL_HISTORY_MAX = 10


def _fetch_sina_index_spot():
    """直连新浪获取所有指数实时行情（分页拉取）。

    替代 ak.stock_zh_index_spot_sina()。
    """
    # 先获取总数
    try:
        count_resp = sina_get(_SINA_INDEX_COUNT_URL, timeout=10)
        total = int(count_resp.text.strip().strip('"') or '0')
        pages = (total // 80) + 1 if total else 5
    except Exception:
        pages = 5  # 默认拉 5 页

    all_rows = []
    for page in range(1, pages + 1):
        params = {
            'page': str(page),
            'num': '80',
            'sort': 'symbol',
            'asc': '1',
            'node': 'hs_s',
            'symbol': '',
            '_s_a_a': '',
            '_s_a_b': '',
            '_s_a_c': '',
            '_s_a_d': '',
        }
        try:
            resp = sina_get(_SINA_INDEX_URL, params=params, timeout=15)
            if resp.status_code == 200:
                # 新浪返回标准 JSON 数组（非 JSONP）
                data = resp.json()
                if isinstance(data, list):
                    all_rows.extend(data)
        except Exception as e:
            logger.warning(f'[DirectSource] 新浪指数第 {page} 页失败: {e}')

    return all_rows


def _fetch_legu_activity():
    """直连乐咕获取赚钱效应数据。

    替代 ak.stock_market_activity_legu()。
    """
    resp = legu_get(_LEGU_ACTIVITY_URL, timeout=15)
    if resp.status_code != 200:
        return {}
    try:
        import io
        from bs4 import BeautifulSoup
        dfs = pd.read_html(io.StringIO(resp.text))
        if not dfs:
            return {}
        df = dfs[0]
        # 拆成 item/value 对（每 2 列一组）
        pairs = {}
        for i in range(0, min(len(df.columns), 6), 2):
            sub = df.iloc[:, i:i + 2]
            sub.columns = ['item', 'value']
            for _, row in sub.iterrows():
                item = str(row.get('item', '')).strip()
                val = str(row.get('value', '')).strip()
                if item and item != 'nan':
                    pairs[item] = val

        # 补充 metric-activity 和统计日期
        soup = BeautifulSoup(resp.text, features='lxml')
        metric = soup.find('div', attrs={'class': 'metric-activity'})
        if metric:
            for line in metric.text.strip().split('\n'):
                line = line.strip()
                if line:
                    # 格式 "上涨 1234" 或 "上涨：1234"
                    parts = line.replace('：', ' ').split(None, 1)
                    if len(parts) == 2:
                        pairs[parts[0].strip()] = parts[1].strip()
        meta = soup.find('div', attrs={'class': 'market-activity-meta'})
        if meta:
            pairs['统计日期'] = meta.text.strip()
        return pairs
    except Exception as e:
        logger.warning(f'[DirectSource] 乐咕数据解析失败: {e}')
        return {}


def _compute_vol_trend(today_sh_volume_yi):
    """简化版量能趋势计算 — 基于模块级缓存比较今日 vs 昨日成交额。

    原实现依赖 ak.stock_zh_index_daily（需要 JS 解密），此处简化为缓存比较。
    首次调用无昨日数据时返回默认值 50。
    """
    if not today_sh_volume_yi:
        return 50.0, 0, 0, 0, 0

    today_str = time.strftime('%Y-%m-%d')
    yesterday = _VOL_HISTORY.get(today_str)

    if yesterday and yesterday.get('sh_volume'):
        prev_vol = yesterday['sh_volume']
        ratio = today_sh_volume_yi / prev_vol if prev_vol > 0 else 1.0
        day_score = max(0, min(100, 50 + (ratio - 1) * 100))
        change_pct = round((ratio - 1) * 100, 1)
        return round(day_score, 1), int(prev_vol), change_pct, int(prev_vol), change_pct

    return 50.0, 0, 0, 0, 0


def _save_vol_history(sh_volume, sz_volume):
    """保存今日成交额到模块级缓存（供次日比较）"""
    today_str = time.strftime('%Y-%m-%d')
    _VOL_HISTORY[today_str] = {
        'sh_volume': sh_volume,
        'sz_volume': sz_volume,
        'saved_at': time.time(),
    }
    # 清理过期数据
    if len(_VOL_HISTORY) > _VOL_HISTORY_MAX:
        oldest = sorted(_VOL_HISTORY.keys())[:-_VOL_HISTORY_MAX]
        for k in oldest:
            _VOL_HISTORY.pop(k, None)


# ==================== 资金流向直连实现 ====================

# 同花顺行业资金流 HTML 端点（无需 hexin-v 反爬，实测可用）
_THS_SECTOR_FLOW_URL = (
    "http://data.10jqka.com.cn/funds/hyzjl/field/tradezdf/order/desc/ajax/1/free/1/"
)


def _fetch_ths_sector_flow():
    """直连同花顺获取行业板块资金流数据。

    替代 ak.stock_fund_flow_industry()。
    实测此 AJAX 端点无需 hexin-v token，可直接请求（GBK 编码 HTML）。
    """
    resp = ths_get(_THS_SECTOR_FLOW_URL, timeout=15)
    if resp.status_code != 200:
        return []
    resp.encoding = 'gbk'
    try:
        import io
        import pandas as pd
        dfs = pd.read_html(io.StringIO(resp.text))
        if not dfs:
            return []
        df = dfs[0]
        if df.empty:
            return []
        return df.to_dict('records')
    except Exception as e:
        logger.warning(f'[DirectSource] 同花顺板块资金流解析失败: {e}')
        return []


# ==================== DirectSource 主类 ====================


class DirectSource(BaseDataSource):
    """直连数据源 — 零 akshare 依赖，所有数据通过 http_client 直连上游。

    单源设计：无降级链，失败时由上层 fetch_with_stale_fallback 返回 stale cache
    并显示「数据延迟」徽章（ADR-003）。
    """

    # ---- 可转债 ----

    def get_convertible_list(self, **kwargs) -> dict:
        try:
            rows = get_convertible_bond_list()
            if not rows:
                return {'total': 0, 'page': 1, 'page_size': 100, 'items': []}
            return _apply_convertible_filters(rows, **kwargs)
        except Exception as e:
            logger.warning(f'[DirectSource] get_convertible_list 失败: {e}')
            return {'total': 0, 'page': 1, 'page_size': 100, 'items': []}

    def get_convertible_signals(self) -> dict:
        try:
            raw = get_convertible_bond_signals()
            if not raw:
                return {'double_low': [], 'force_redeem': [], 'discount': [], 'down_revised': []}
            return raw
        except Exception as e:
            logger.warning(f'[DirectSource] get_convertible_signals 失败: {e}')
            return {'double_low': [], 'force_redeem': [], 'discount': [], 'down_revised': []}

    def get_convertible_detail(self, code: str) -> dict:
        try:
            result = get_convertible_bond_detail(code)
            if not result:
                return {}
            if not result.get('maturity_date'):
                result['maturity_date'] = ''
            return result
        except Exception as e:
            logger.warning(f'[DirectSource] get_convertible_detail 失败: {e}')
            return {}

    def get_convertible_temperature(self) -> dict:
        try:
            result = get_market_temperature()
            return result if result else {}
        except Exception as e:
            logger.warning(f'[DirectSource] get_convertible_temperature 失败: {e}')
            return {}

    def get_convertible_pending(self) -> list:
        try:
            rows = get_pending_bonds()
            return rows if rows else []
        except Exception as e:
            logger.warning(f'[DirectSource] get_convertible_pending 失败: {e}')
            return []

    def get_convertible_new_listed(self) -> list:
        try:
            rows = get_convertible_new_listed()
            return rows if rows else []
        except Exception as e:
            logger.warning(f'[DirectSource] get_convertible_new_listed 失败: {e}')
            return []

    def sync_placement_announcements(self, days_back=30) -> dict:
        """触发公告同步（可转债 + 配股）"""
        try:
            from services.announcement_parser import (
                sync_cb_placement_announcements,
                sync_stock_placement_announcements,
            )
            cb_stats = sync_cb_placement_announcements(days_back=days_back)
            stock_stats = sync_stock_placement_announcements(days_back=max(days_back, 90))
            return {
                'convertible_bond': cb_stats,
                'stock': stock_stats,
            }
        except Exception as e:
            logger.warning(f'[DirectSource] sync_placement_announcements 失败: {e}')
            return {'error': str(e)}

    # ---- LOF ----

    def get_lof_list(self, **kwargs) -> list:
        try:
            rows = _raw_lof_list()
            if not rows:
                return []
            return normalize_lof_list(rows)
        except Exception as e:
            logger.warning(f'[DirectSource] get_lof_list 失败: {e}')
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
            logger.warning(f'[DirectSource] get_lof_opportunities 失败: {e}')
            return {'premium': [], 'discount': []}

    def get_lof_summary(self) -> dict:
        try:
            result = get_lof_market_summary()
            return result if result else {}
        except Exception as e:
            logger.warning(f'[DirectSource] get_lof_summary 失败: {e}')
            return {}

    # ---- 港股 IPO ----

    def get_hk_ipo_list(self, **kwargs) -> list:
        try:
            return _raw_hk_ipo_list()
        except Exception as e:
            logger.warning(f'[DirectSource] get_hk_ipo_list 失败: {e}')
            return []

    def get_hk_ipo_upcoming(self) -> list:
        try:
            return _raw_hk_ipo_upcoming()
        except Exception as e:
            logger.warning(f'[DirectSource] get_hk_ipo_upcoming 失败: {e}')
            return []

    def get_hk_ipo_summary(self) -> dict:
        try:
            return _raw_hk_ipo_summary()
        except Exception as e:
            logger.warning(f'[DirectSource] get_hk_ipo_summary 失败: {e}')
            return {}

    def get_hk_ipo_detail(self, code=None, **kwargs) -> dict:
        try:
            return _raw_hk_ipo_detail(code)
        except Exception as e:
            logger.warning(f'[DirectSource] get_hk_ipo_detail 失败: {e}')
            return None

    # ---- 封闭式基金 ----

    def get_closed_end_list(self) -> list:
        try:
            return _raw_closed_end_list()
        except Exception as e:
            logger.warning(f'[DirectSource] get_closed_end_list 失败: {e}')
            return []

    def get_closed_end_summary(self) -> dict:
        try:
            return _raw_closed_end_summary()
        except Exception as e:
            logger.warning(f'[DirectSource] get_closed_end_summary 失败: {e}')
            return {}

    # ---- 市场情绪 ----

    def get_market_sentiment(self) -> dict:
        """直连新浪指数 + 乐咕赚钱效应，计算市场情绪分数。

        数据由新浪指数行情与乐咕涨跌家数直连获取；量能趋势基于缓存比较。
        """
        result = {}

        # 1. 新浪指数实时行情
        try:
            rows = _fetch_sina_index_spot()
            if rows:
                for row in rows:
                    code = str(row.get('symbol', ''))
                    if code not in _INDEX_MAP:
                        continue
                    prefix = _INDEX_MAP[code]
                    price = safe_float(row.get('trade', 0))
                    change_pct = safe_float(row.get('changepercent', 0))
                    change_amount = safe_float(row.get('pricechange', 0))
                    amount = safe_float(row.get('amount', 0))

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
            logger.warning(f'[DirectSource] 新浪指数行情失败: {e}')

        # 北交所成交额暂不计算（原实现依赖 stock_zh_index_daily JS 解密）
        result['bj_volume'] = 0
        result['total_volume'] = round(
            result.get('sh_volume', 0) + result.get('sz_volume', 0), 0
        )

        # 2. 乐咕涨跌家数
        try:
            legu = _fetch_legu_activity()
            if legu:
                result['sh_up_count'] = int(safe_float(legu.get('上涨', 0)))
                result['sh_down_count'] = int(safe_float(legu.get('下跌', 0)))
                result['sh_flat_count'] = int(safe_float(legu.get('平盘', 0)))
                result['sh_limit_up'] = int(safe_float(legu.get('涨停', 0)))
                result['sh_limit_down'] = int(safe_float(legu.get('跌停', 0)))

                up = result['sh_up_count']
                down = result['sh_down_count']
                total = up + down
                if total > 0:
                    up_ratio = up / total
                    ratio_score = up_ratio * 100

                    # 量能趋势分（简化版，基于缓存比较）
                    vol_score, prev_vol, vol_chg, vol_5d, vol_5d_chg = \
                        _compute_vol_trend(result.get('sh_volume', 0))
                    result['vol_trend_score'] = vol_score
                    result['prev_volume'] = float(prev_vol)
                    result['volume_change_pct'] = vol_chg
                    result['volume_5d_avg'] = float(vol_5d)
                    result['volume_5d_change_pct'] = vol_5d_chg

                    # 综合情绪分 = 涨跌分×60% + 量能趋势分×40%
                    sentiment_score = ratio_score * 0.6 + vol_score * 0.4
                    result['sentiment_score'] = round(sentiment_score, 1)
                    result['sh_score'] = round(up_ratio * 100, 1)
        except Exception as e:
            logger.warning(f'[DirectSource] 乐咕赚钱效应失败: {e}')

        # 保存今日成交额到缓存（供次日量能比较）
        _save_vol_history(result.get('sh_volume', 0), result.get('sz_volume', 0))

        # 标准化返回，保持 API 字段稳定。
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
        # 检查是否有真实数据
        check_keys = [k for k in standard_keys if k not in (
            'sentiment_score', 'vol_trend_score', 'prev_volume', 'volume_change_pct',
            'volume_5d_avg', 'volume_5d_change_pct', 'sh_score', 'north',
            'sz_up_count', 'sz_down_count', 'sz_score')]
        has_real_data = any(standardized[k] != 0 for k in check_keys)
        if not has_real_data:
            return {}
        return standardized

    # ---- 资金流向 ----

    def get_fund_flow(self) -> dict:
        """直连同花顺获取行业板块资金流数据。

        替代 ak.stock_fund_flow_industry()。
        实测 THS AJAX 端点无需 hexin-v，GBK 编码 HTML，pd.read_html 解析。
        THS 列名：行业/行业指数/涨跌幅/流入资金(亿)/流出资金(亿)/净额(亿)/公司家数/领涨股/涨跌幅.1/当前价(元)
        """
        result = {}
        try:
            items = _fetch_ths_sector_flow()
            if not items:
                return {}

            sectors = []
            for item in items:
                name = str(item.get('行业', '')).strip()
                if not name:
                    continue
                net_flow = safe_float(item.get('净额(亿)', 0))
                inflow = safe_float(item.get('流入资金(亿)', 0))
                outflow = safe_float(item.get('流出资金(亿)', 0))
                # THS 涨跌幅是 "2.95%" 字符串，需去 %
                change_pct_str = str(item.get('涨跌幅', '0')).strip('%')
                change_pct = safe_float(change_pct_str)
                leader = str(item.get('领涨股', '')).strip()
                leader_change_str = str(item.get('涨跌幅.1', '0')).strip('%')
                leader_change = safe_float(leader_change_str)
                company_count = int(safe_float(item.get('公司家数', 0)))

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

            sectors.sort(key=lambda x: x['flow'], reverse=True)

            total_inflow = round(sum(s['flow'] for s in sectors if s['flow'] > 0), 2)
            total_outflow = round(sum(s['flow'] for s in sectors if s['flow'] < 0), 2)
            net_inflow = round(total_inflow + total_outflow, 2)

            result['total_inflow'] = total_inflow
            result['total_outflow'] = abs(total_outflow)
            result['net_inflow'] = net_inflow
            result['sectors'] = sectors
            result['top_inflow'] = [s for s in sectors if s['flow'] > 0][:10]
            result['top_outflow'] = sorted(
                [s for s in sectors if s['flow'] < 0], key=lambda x: x['flow'])[:10]
            result['total_count'] = len(sectors)
        except Exception as e:
            logger.warning(f'[DirectSource] 获取行业板块资金流向失败: {e}')
            return {}

        if not result.get('sectors'):
            return {}
        return result

    # ---- 健康检查 ----

    def health_check(self) -> dict:
        """直连新浪指数端点检测可用性（轻量级，不依赖 akshare）"""
        try:
            resp = sina_get(_SINA_INDEX_COUNT_URL, timeout=10)
            if resp.status_code == 200:
                count = resp.text.strip().strip('"')
                return {
                    'status': 'ok',
                    'source': 'direct',
                    'detail': f'新浪指数端点正常, 指数总数={count}',
                }
            return {'status': 'degraded', 'source': 'direct',
                    'detail': f'HTTP {resp.status_code}'}
        except Exception as e:
            return {'status': 'error', 'source': 'direct', 'detail': str(e)}
