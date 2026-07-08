# -*- coding: utf-8 -*-
"""可转债数据服务 — 直连 HTTP（新浪 + 东财），零 akshare 依赖

数据源：
  - 新浪可转债行情：vip.stock.finance.sina.com.cn（实时价格，不封 IP）
  - 东方财富可转债指标：datacenter-web.eastmoney.com（转股指标，走 em_get 限流）
  - 集思录待发转债：www.jisilu.cn（待发/配售数据，POST 请求）
"""

import json
import logging
import re

import pandas as pd

from services.http_client import sina_get, em_get, jsl_post
from utils.convert import safe_float

logger = logging.getLogger('trading_toolkit')

# ==================== 上游 API URL ====================

_SINA_BOND_LIST_URL = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeDataSimple"
_SINA_BOND_COUNT_URL = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeStockCountSimple"
_EM_BOND_LIST_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"

# ==================== 工具函数 ====================


def get_exchange_by_code(code):
    """根据代码判断交易所"""
    code_str = str(code)
    if code_str.startswith(('sh', '5', '6', '9', '11', '13')):
        return 'sh'
    elif code_str.startswith(('sz', '0', '1', '2', '3', '12')):
        return 'sz'
    elif code_str.startswith(('4', '8')):
        return 'bj'
    return ''


def _parse_sina_symbol(symbol):
    """解析新浪 symbol（如 sh110073）得到纯代码"""
    symbol = str(symbol)
    if symbol.startswith(('sh', 'sz', 'bj')):
        return symbol[2:]
    return symbol


# ==================== 上游数据获取（直连 HTTP） ====================


def _get_sina_bonds():
    """从新浪源获取实时可转债行情（320+条）

    替代 ak.bond_zh_hs_cov_spot()，直连新浪财经 API。
    使用 Market_Center.getHQNodeDataSimple + node=hskzz_z，分页拉取。
    """
    try:
        # 先获取总数计算页数
        try:
            count_resp = sina_get(_SINA_BOND_COUNT_URL,
                                  params={'node': 'hskzz_z'}, timeout=10)
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
                'node': 'hskzz_z',
                '_s_r_a': 'page',
            }
            resp = sina_get(_SINA_BOND_LIST_URL, params=params, timeout=10)
            if resp.status_code != 200:
                continue
            text = resp.text.strip()
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                try:
                    data = json.loads(text[text.index('['):text.rindex(']') + 1])
                except (ValueError, json.JSONDecodeError):
                    continue
            if isinstance(data, list) and data:
                all_rows.extend(data)

        if not all_rows:
            return None
        df = pd.DataFrame(all_rows)
        return df if not df.empty else None
    except Exception as e:
        logger.warning(f'[SinaBond] 获取新浪可转债数据失败: {e}')
        return None


def _get_em_bonds():
    """从东方财富获取可转债转股指标（1000+条，含溢价率/转股价值/评级）

    替代 ak.bond_zh_cov()，直连东财数据中心 API，走 em_get 限流。
    """
    params = {
        "reportName": "RPT_BOND_CB_LIST",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "pageSize": "500",
        "sortColumns": "PUBLIC_START_DATE",
        "sortTypes": "-1",
    }
    try:
        resp = em_get(_EM_BOND_LIST_URL, params=params, timeout=15)
        if resp.status_code != 200:
            logger.warning(f'[EmBond] HTTP {resp.status_code}')
            return None
        d = resp.json()
        if not (d.get("result") and d["result"].get("data")):
            return None
        df = pd.DataFrame(d["result"]["data"])
        return df if not df.empty else None
    except Exception as e:
        logger.warning(f'[EmBond] 获取东方财富可转债数据失败: {e}')
        return None


# ==================== 数据合并 ====================


def _merge_bond_data():
    """合并多源数据：新浪（实时行情） + 东方财富（转股指标），输出英文字段"""
    sina_df = _get_sina_bonds()
    if sina_df is None or sina_df.empty:
        return None

    # 解析新浪数据
    records = []
    for _, row in sina_df.iterrows():
        bond_code = _parse_sina_symbol(row.get('symbol', ''))
        trade = safe_float(row.get('trade', 0))
        if trade <= 0:
            continue
        exchange = get_exchange_by_code(row.get('symbol', ''))
        records.append({
            'bond_code': bond_code,
            'bond_name': str(row.get('name', '')),
            'price': trade,
            'change_pct': safe_float(row.get('changepercent', 0)),
            'open': safe_float(row.get('open', 0)),
            'high': safe_float(row.get('high', 0)),
            'low': safe_float(row.get('low', 0)),
            'volume': safe_float(row.get('volume', 0)),
            'amount': safe_float(row.get('amount', 0)),
            'settlement': safe_float(row.get('settlement', 0)),
            'exchange': exchange,
            'ticktime': str(row.get('ticktime', '')),
        })

    df = pd.DataFrame(records)
    if df.empty:
        return None

    # 合并东方财富的转股指标
    # EM API 返回英文列名，映射如下：
    #   SECURITY_CODE→债券代码, CONVERT_STOCK_CODE→正股代码,
    #   SECURITY_SHORT_NAME→正股简称, CONVERT_STOCK_PRICE→正股价,
    #   TRANSFER_PRICE→转股价, TRANSFER_VALUE→转股价值,
    #   TRANSFER_PREMIUM_RATIO→转股溢价率(实测返回占位值100.0，需自行计算),
    #   RATING→信用评级, ACTUAL_ISSUE_SCALE→发行规模, LISTING_DATE→上市时间
    em_df = _get_em_bonds()
    if em_df is not None and not em_df.empty:
        em_map = {}
        for _, row in em_df.iterrows():
            code = str(row.get('SECURITY_CODE', ''))
            em_map[code] = {
                'stock_code': str(row.get('CONVERT_STOCK_CODE', '')),
                'stock_name': str(row.get('SECURITY_SHORT_NAME', '')),
                'stock_price': safe_float(row.get('CONVERT_STOCK_PRICE', 0)),
                'conversion_price': safe_float(row.get('TRANSFER_PRICE', 0)),
                'conversion_value': safe_float(row.get('TRANSFER_VALUE', 0)),
                'rating': str(row.get('RATING', '')),
                'issue_size': safe_float(row.get('ACTUAL_ISSUE_SCALE', 0)),
                'list_date': str(row.get('LISTING_DATE', '')),
            }

        for col in ['stock_code', 'stock_name', 'stock_price', 'conversion_price',
                     'conversion_value', 'rating',
                     'issue_size', 'list_date']:
            df[col] = df['bond_code'].map(lambda c: em_map.get(c, {}).get(col, None if col in ['stock_name', 'rating', 'list_date', 'stock_code'] else 0))

        # 填充 NaN
        for col in ['stock_code', 'stock_name', 'rating', 'list_date']:
            df[col] = df[col].fillna('')

        # EM 的 TRANSFER_PREMIUM_RATIO 实测返回占位值 100.0（CURRENT_BOND_PRICE/CONVERT_STOCK_PRICE 均为 None），
        # 因此用新浪实时价格 + EM 转股价值自行计算溢价率：
        #   premium_rate = (bond_price - conversion_value) / conversion_value * 100
        for idx, row in df.iterrows():
            price = row.get('price', 0)
            cv = row.get('conversion_value', 0)
            if price > 0 and cv > 0:
                pr = round((price - cv) / cv * 100, 2)
                df.at[idx, 'premium_rate'] = pr
                df.at[idx, 'double_low'] = round(price + pr, 2)
            else:
                df.at[idx, 'premium_rate'] = 0
                df.at[idx, 'double_low'] = 0

    else:
        # 无 EM 数据时，所有转股指标置零
        for col in ['stock_code', 'stock_name', 'stock_price', 'conversion_price',
                     'conversion_value', 'premium_rate', 'rating',
                     'issue_size', 'list_date', 'double_low']:
            if col in ['stock_code', 'stock_name', 'rating', 'list_date']:
                df[col] = ''
            else:
                df[col] = 0

    return df


# ==================== 公开接口（保持函数签名不变） ====================


def get_market_temperature():
    """获取可转债市场温度"""
    try:
        df = _merge_bond_data()
        if df is None or df.empty:
            return None

        # 过滤无效数据，避免异常值污染中位数：
        # - premium_rate=0：无转股数据
        # - conversion_value<50：EM 数据异常（正常转股价值 50-300，低于 50 说明数据错误）
        # - price>500 或 price<90：异常价格转债（退市债、妖债）
        # - premium_rate>100 或 <-50：异常溢价率（cv 数据错误导致的虚高 premium）
        valid = df[
            (df['premium_rate'] != 0) &
            (df['conversion_value'] >= 50) &
            (df['price'] <= 500) &
            (df['price'] >= 90) &
            (df['premium_rate'] >= -50) &
            (df['premium_rate'] <= 100)
        ]
        if valid.empty:
            return None

        price_median = float(valid['price'].median())
        premium_median = float(valid['premium_rate'].median())
        double_low_median = float(valid['double_low'].median())

        if double_low_median < 150:
            market_status = '偏低，可关注'
        elif double_low_median < 180:
            market_status = '合理，可适当关注'
        else:
            market_status = '偏高，需谨慎'

        return {
            'count': int(len(df)),
            'valid_count': int(len(valid)),
            'price_min': round(float(valid['price'].min()), 2),
            'price_max': round(float(valid['price'].max()), 2),
            'price_median': round(price_median, 2),
            'premium_median': round(premium_median, 2),
            'premium_p25': round(float(valid['premium_rate'].quantile(0.25)), 2),
            'premium_p75': round(float(valid['premium_rate'].quantile(0.75)), 2),
            'double_low_median': round(double_low_median, 1),
            'market_status': market_status,
            'source': 'sina+em',
            'ticktime': str(df['ticktime'].iloc[0]) if 'ticktime' in df.columns else '',
        }
    except Exception as e:
        logger.warning(f'获取可转债市场温度失败: {e}')
        return None


def get_convertible_bond_list():
    """获取可转债列表，返回英文字段的 dict 列表"""
    try:
        df = _merge_bond_data()
        if df is None or df.empty:
            return []

        result = []
        for _, row in df.iterrows():
            result.append({
                'bond_code': str(row['bond_code']),
                'bond_name': str(row['bond_name']),
                'price': safe_float(row['price']),
                'change_pct': safe_float(row['change_pct']),
                'stock_code': str(row.get('stock_code', '')),
                'stock_name': str(row.get('stock_name', '')),
                'exchange': str(row.get('exchange', '')),
                'conversion_value': safe_float(row.get('conversion_value', 0)),
                'premium_rate': safe_float(row.get('premium_rate', 0)),
                'double_low': safe_float(row.get('double_low', 0)),
                'rating': str(row.get('rating', '')),
                'stock_price': safe_float(row.get('stock_price', 0)),
                'conversion_price': safe_float(row.get('conversion_price', 0)),
                'remaining_size': safe_float(row.get('issue_size', 0)),
                'volume': safe_float(row.get('volume', 0)),
                'amount': safe_float(row.get('amount', 0)),
            })
        return result
    except Exception as e:
        logger.warning(f'获取可转债列表失败: {e}')
        return []


def get_convertible_bond_detail(code: str) -> dict:
    """获取单只可转债详情，返回英文字段的 dict"""
    try:
        df = _merge_bond_data()
        if df is None or df.empty:
            return {}

        matched = df[df['bond_code'] == str(code)]
        if matched.empty:
            return {}

        row = matched.iloc[0]
        result = {
            'bond_code': str(row['bond_code']),
            'bond_name': str(row['bond_name']),
            'price': safe_float(row['price']),
            'change_pct': safe_float(row['change_pct']),
            'stock_code': str(row.get('stock_code', '')),
            'stock_name': str(row.get('stock_name', '')),
            'exchange': str(row.get('exchange', '')),
            'conversion_value': safe_float(row.get('conversion_value', 0)),
            'premium_rate': safe_float(row.get('premium_rate', 0)),
            'double_low': safe_float(row.get('double_low', 0)),
            'rating': str(row.get('rating', '')),
            'stock_price': safe_float(row.get('stock_price', 0)),
            'conversion_price': safe_float(row.get('conversion_price', 0)),
            'remaining_size': safe_float(row.get('issue_size', 0)),
            'volume': safe_float(row.get('volume', 0)),
            'amount': safe_float(row.get('amount', 0)),
        }

        # 补充 EM 详情字段（申购日期/中签率等）
        # EM API 英文列名映射：
        #   SECURITY_CODE→债券代码, ACTUAL_ISSUE_SCALE→发行规模,
        #   PUBLIC_START_DATE→申购日期, CORRECODE→申购代码,
        #   ONLINE_GENERAL_LWR→中签率, ONLINE_GENERAL_AAU→申购上限,
        #   EXPIRE_DATE→到期日
        try:
            em_df = _get_em_bonds()
            if em_df is not None and not em_df.empty:
                matched_em = em_df[em_df['SECURITY_CODE'].astype(str) == str(code)]
                if not matched_em.empty:
                    bond_row = matched_em.iloc[0]
                    extra_fields = {
                        'issue_size': safe_float(bond_row.get('ACTUAL_ISSUE_SCALE', 0)),
                        'apply_date': str(bond_row.get('PUBLIC_START_DATE', '')),
                        'lottery_rate': safe_float(bond_row.get('ONLINE_GENERAL_LWR', 0)),
                        'apply_code': str(bond_row.get('CORRECODE', '')),
                        'apply_limit': safe_float(bond_row.get('ONLINE_GENERAL_AAU', 0)),
                        'maturity_date': str(bond_row.get('EXPIRE_DATE', '')),
                    }
                    for k, v in extra_fields.items():
                        if v not in (None, '', 0):
                            result[k] = v
        except Exception:
            pass

        if not result.get('maturity_date'):
            result['maturity_date'] = ''

        return result
    except Exception as e:
        logger.warning(f'获取可转债详情失败: {e}')
        return {}


def get_convertible_bond_signals():
    """获取可转债信号，返回英文字段的 dict"""
    try:
        df = _merge_bond_data()
        if df is None or df.empty:
            return None

        # 过滤无效数据：premium_rate=0（无转股数据）或 conversion_value<10（EM 数据异常）
        # 当 cv 极小时（如 3.17），premium_rate 会异常大（如 2250%），污染中位数
        valid = df[(df['premium_rate'] != 0) & (df['conversion_value'] >= 10)].copy()
        if valid.empty:
            return {'double_low': [], 'force_redeem': [], 'discount': [], 'down_revised': []}

        double_low = valid.nsmallest(20, 'double_low')

        force_redeem = valid[
            (valid['premium_rate'] < 10) &
            (valid['price'] >= 105) &
            (valid['price'] <= 140)
        ].head(10)

        discount = valid[valid['premium_rate'] < 0].head(10)

        down_revised = valid[
            (valid['premium_rate'] > 50) &
            (valid['price'] < 115)
        ].head(10)

        def df_to_records(sub_df):
            records = []
            for _, row in sub_df.iterrows():
                records.append({
                    'bond_code': str(row['bond_code']),
                    'bond_name': str(row['bond_name']),
                    'price': safe_float(row['price']),
                    'change_pct': safe_float(row['change_pct']),
                    'stock_code': str(row.get('stock_code', '')),
                    'stock_name': str(row.get('stock_name', '')),
                    'exchange': str(row.get('exchange', '')),
                    'conversion_value': safe_float(row['conversion_value']),
                    'premium_rate': safe_float(row['premium_rate']),
                    'double_low': safe_float(row['double_low']),
                    'rating': str(row.get('rating', '')),
                })
            return records

        return {
            'double_low': df_to_records(double_low),
            'force_redeem': df_to_records(force_redeem),
            'discount': df_to_records(discount),
            'down_revised': df_to_records(down_revised),
        }
    except Exception as e:
        logger.warning(f'获取可转债信号失败: {e}')
        return None


# ==================== 待发/配售可转债（集思录，已有直连逻辑） ====================


def get_pending_bonds():
    """获取待发/配售可转债列表（集思录数据源）"""
    try:
        rows = _fetch_jisilu_pre_list()
        if rows:
            return rows
    except Exception as e:
        logger.warning(f'获取待发可转债失败: {e}')
    return []


def _fetch_jisilu_pre_list():
    """从集思录API获取待发转债列表（使用 http_client.jsl_post）"""
    url = 'https://www.jisilu.cn/data/cbnew/pre_list/'
    payload = {
        'page': 1,
        'rp': 100,
        '_': ''
    }
    try:
        resp = jsl_post(url, data=payload, timeout=10)
        if resp.status_code == 200:
            result = resp.json()
            rows = result.get('rows', [])
            if rows:
                return _normalize_jisilu_pre_list(rows)
    except Exception as e:
        logger.warning(f'集思录API请求失败: {e}')
    return []


def _calc_strategy_score(stock_cash_ratio, safety_pad, issue_size):
    """计算策略综合评分（0-100）"""
    cash_score = min(stock_cash_ratio / 30, 1) * 45
    safety_score = min(safety_pad / 10, 1) * 35
    if issue_size <= 2:
        size_score = 20
    elif issue_size >= 10:
        size_score = 0
    else:
        size_score = (10 - issue_size) / 8 * 20
    return round(cash_score + safety_score + size_score)


def _calc_placement_score(issue_size, float_shares, safety_pad):
    """配售三因子评分 0-100"""
    size_score = max(0, 1 - issue_size / 10) * 30
    float_score = (1 - float_shares / issue_size) * 40 if issue_size > 0 else 0
    safety_score = min(safety_pad / 10, 1) * 30
    return round(size_score + float_score + safety_score)


def _get_rating_by_score(score):
    if score >= 70:
        return 'recommend'
    if score >= 40:
        return 'watch'
    return 'caution'


def _get_risk_level(safety_pad):
    if safety_pad < 3:
        return 'high'
    elif safety_pad > 8:
        return 'low'
    return 'mid'


DEFAULT_PREMIUM_RATE = 0.2


def _normalize_jisilu_pre_list(rows):
    """标准化集思录待发转债数据"""
    result = []
    for item in rows:
        cell = item.get('cell', {})
        progress_nm = str(cell.get('progress_nm') or '')
        progress_full = str(cell.get('progress_full') or '')
        progress_text = progress_nm or progress_full

        stock_price = safe_float(cell.get('price', 0))
        shares_for_10_lots = safe_float(cell.get('apply10', 0))
        stock_cash_ratio = safe_float(cell.get('cb_amount', 0))
        record_price = safe_float(cell.get('record_price', 0))
        ma20_price = safe_float(cell.get('ma20_price', 0))

        expected_profit = round(1000 * DEFAULT_PREMIUM_RATE, 2)
        safety_pad = 0
        if shares_for_10_lots > 0 and stock_price > 0:
            safety_pad = round(expected_profit / (shares_for_10_lots * stock_price) * 100, 2)

        stock_trend = 0
        if ma20_price > 0:
            stock_trend = round((stock_price - ma20_price) / ma20_price * 100, 2)

        issue_size = safe_float(cell.get('amount', 0))
        online_amount = safe_float(cell.get('online_amount', 0))
        ration_rt = safe_float(cell.get('ration_rt', 0))
        if online_amount > 0:
            float_shares = online_amount
        else:
            float_shares = issue_size * (1 - ration_rt / 100) if ration_rt > 0 else issue_size
        strategy_score = _calc_placement_score(issue_size, float_shares, safety_pad)
        strategy_rating = _get_rating_by_score(strategy_score)
        risk_level = _get_risk_level(safety_pad)

        result.append({
            'stock_code': str(cell.get('stock_id', '')),
            'stock_name': str(cell.get('stock_nm', '')),
            'bond_code': str(cell.get('bond_id', '')),
            'bond_name': str(cell.get('bond_nm', '')),
            'progress': progress_nm,
            'progress_dt': str(cell.get('progress_dt', '')),
            'progress_full': progress_full,
            'issue_size': issue_size,
            'rating': str(cell.get('rating_cd') or ''),
            'shareholder_ratio': safe_float(cell.get('ration_rt', 0)),
            'conversion_price': safe_float(cell.get('convert_price', 0)),
            'stock_price': stock_price,
            'stock_change': safe_float(cell.get('increase_rt', 0)),
            'pb': safe_float(cell.get('pb', 0)),
            'per_share_allocation': safe_float(cell.get('ration', 0)),
            'shares_for_10_lots': shares_for_10_lots,
            'registration_date': str(cell.get('record_dt', '')),
            'online_issue_size': safe_float(cell.get('online_amount', 0)),
            'win_rate': safe_float(cell.get('lucky_draw_rt', 0)),
            'apply_date': str(cell.get('apply_date', '')),
            'list_date': str(cell.get('list_date', '')),
            'apply_code': str(cell.get('apply_cd', '')),
            'ration_code': str(cell.get('ration_cd', '')),
            'status': _get_bond_status_by_progress(progress_text),
            'stock_cash_ratio': stock_cash_ratio,
            'record_price': record_price,
            'ma20_price': ma20_price,
            'expected_profit': expected_profit,
            'safety_pad': safety_pad,
            'stock_trend': stock_trend,
            'strategy_score': strategy_score,
            'float_shares': round(float_shares, 2),
            'strategy_rating': strategy_rating,
            'risk_level': risk_level,
        })
    return result


def _get_bond_status_by_progress(progress):
    """将方案进展映射为状态"""
    if not progress:
        return '--'
    if '申购' in progress or '发行公告' in progress:
        return '申购中'
    if '上市' in progress:
        return '待上市'
    if '同意注册' in progress:
        return '同意注册'
    if '上市委' in progress:
        return '上市委通过'
    if '交易所受理' in progress:
        return '交易所受理'
    if '股东大会' in progress:
        return '股东大会批准'
    if '董事会' in progress:
        return '董事会预案'
    return '--'
