# -*- coding: utf-8 -*-
"""可转债数据服务 — 直连 HTTP（新浪 + 东财），零 akshare 依赖

数据源：
  - 新浪可转债行情：vip.stock.finance.sina.com.cn（实时价格，不封 IP）
  - 东方财富可转债指标：datacenter-web.eastmoney.com（转股指标 + 待发债券，走 em_get 限流）
  - 新浪股票行情：hq.sinajs.cn（正股实时价格/涨跌）
  - 东财估值分析：RPT_VALUEANALYSIS_DET（PB、总市值、总股本）
  - 东财K线：push2his.eastmoney.com（MA20 计算）
"""

import json
import logging
import math
import re
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from services.http_client import sina_get, em_get
from utils.convert import safe_float

logger = logging.getLogger('trading_toolkit')

# ==================== 上游 API URL ====================

_SINA_BOND_LIST_URL = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeDataSimple"
_SINA_BOND_COUNT_URL = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeStockCountSimple"
_EM_BOND_LIST_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
_SINA_STOCK_QUOTE_URL = "https://hq.sinajs.cn/list="
_EM_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"

# 公告 API — 用来解析前 5 阶段日期（董事会预案→同意注册）
_EM_NOTICE_URL = "https://np-anotice-stock.eastmoney.com/api/security/ann"

# 阶段公告标题关键词（按阶段倒序匹配，确保最新公告覆盖旧的）
_STAGE_KEYWORDS = [
    # 阶段名 -> 匹配关键词（按优先级）。每个阶段的关键词必须含"阶段标志词"，
    # 避免被募集说明书、保荐变更、信用评级等无关公告误匹配。
    ('同意注册', ['同意注册批复', '同意注册的批复', '同意注册', '注册批复', '注册批文']),
    ('上市委通过', ['上市委审议通过', '上市委通过', '上市委审核通过', '上市委会议审议通过']),
    ('交易所受理', ['申请获得上海证券交易所受理', '申请获得深圳证券交易所受理',
                '申请获得上海证券交易所上市审核委员会受理', '申请获得深圳证券交易所上市审核委员会受理',
                '申请获得上交所受理', '申请获得深交所受理', '交易所受理', '申请获得受理']),
    ('股东大会批准', ['股东大会决议公告', '年度股东大会决议', '临时股东大会决议', '股东大会决议',
                  '股东大会通过', '股东大会批准', '股东大会审议通过', '年度股东大会', '临时股东大会']),
    ('董事会预案', ['可转债预案', '发行可转换公司债券预案', '公开发行可转换公司债券预案', '发行可转债预案',
                '可转换公司债券预案', '发行可转债的预案', '发行可转换公司债券的预案', '发行可转换债券预案',
                '公开发行可转换债券预案', '公司公开发行可转换公司债券预案']),
]

_TIMELINE_STAGES = ('董事会预案', '股东大会批准', '交易所受理', '上市委通过', '同意注册')
_TIMELINE_REFRESH_INTERVAL = timedelta(hours=24)
_TIMELINE_REFRESH_LOCK = threading.Lock()
_TIMELINE_REFRESHING = set()
_MA20_CACHE_TTL = 86400
_MA20_FAILURE_TTL = 300
_MA20_REFRESHING = set()

# A 股优先配售以股权登记日收市为界，登记日当天仍可参与。
_CHINA_TZ = ZoneInfo('Asia/Shanghai')

# ==================== 工具函数 ====================


def _parse_cashflows(value):
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        return json.loads(value)
    except Exception:
        return []


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


def _is_finite_number(value):
    try:
        return value is not None and math.isfinite(float(value))
    except Exception:
        return False


def _parse_date(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in ('nan', 'nat', 'none', 'null'):
        return None
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(text[:19 if ' ' in text else 10], fmt)
        except Exception:
            pass
    return None


def _parse_coupon_schedule(text, years=6):
    """从“第一年0.3%、第二年0.5%...”解析年度票息。"""
    default = [0.3, 0.5, 1.0, 1.5, 1.8, 2.0]
    if not text:
        return default[:years]

    rates = []
    for match in re.finditer(r'第[一二三四五六七八九十\d]+年\s*([0-9]+(?:\.[0-9]+)?)\s*%', str(text)):
        rates.append(safe_float(match.group(1)))
    if not rates:
        rates = [safe_float(x) for x in re.findall(r'([0-9]+(?:\.[0-9]+)?)\s*%', str(text))]
    if not rates:
        rates = default[:]

    while len(rates) < years:
        rates.append(rates[-1] if rates else default[min(len(rates), len(default) - 1)])
    return rates[:years]


def _parse_maturity_redemption_price(redeem_clause, par_value=100):
    """解析到期赎回价，优先识别“面值的110%/110元”等口径。"""
    text = str(redeem_clause or '')
    par = par_value if par_value > 0 else 100

    percent_match = re.search(r'面值的\s*([0-9]+(?:\.[0-9]+)?)\s*%', text)
    if percent_match:
        return round(par * safe_float(percent_match.group(1)) / 100, 4)

    yuan_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*元[（(]?含最后一期', text)
    if yuan_match:
        return safe_float(yuan_match.group(1))

    return 0


def _rating_discount_rate(rating):
    """纯债价值估算折现率；缺少实时同评级收益率曲线时用保守评级档位。"""
    text = str(rating or '').upper().replace('STI', '').strip()
    if text.startswith('AAA'):
        return 0.023
    if text.startswith('AA+'):
        return 0.026
    if text.startswith('AA-'):
        return 0.033
    if text.startswith('AA'):
        return 0.029
    if text.startswith('A+'):
        return 0.042
    if text.startswith('A-'):
        return 0.055
    if text.startswith('A'):
        return 0.048
    return 0.04


def _build_bond_cashflows(value_date, expire_date, coupon_explain, redeem_clause, par_value=100):
    start = _parse_date(value_date)
    maturity = _parse_date(expire_date)
    if not start or not maturity:
        return []

    today = datetime.now()
    years = max(1, int(round((maturity - start).days / 365.0)))
    coupons = _parse_coupon_schedule(coupon_explain, years)
    par = par_value if par_value > 0 else 100
    maturity_redemption = _parse_maturity_redemption_price(redeem_clause, par)
    if maturity_redemption <= 0:
        maturity_redemption = par + par * coupons[-1] / 100

    flows = []
    for i in range(1, years + 1):
        # 可转债付息日通常与起息日同月同日；闰日等边界用 2/28 兜底。
        try:
            pay_date = start.replace(year=start.year + i)
        except ValueError:
            pay_date = start.replace(year=start.year + i, day=28)
        if pay_date <= today:
            continue

        amount = par * coupons[min(i - 1, len(coupons) - 1)] / 100
        if i == years:
            # 东财条款常写“到期赎回价含最后一期利息”，终值不重复加最后一期票息。
            amount = maturity_redemption
        years_left = max((pay_date - today).days / 365.0, 0.001)
        flows.append({'date': pay_date.strftime('%Y-%m-%d'), 'years': years_left, 'amount': round(amount, 4)})
    return flows


def _solve_ytm(price, cashflows):
    if price <= 0 or not cashflows:
        return None

    def pv(rate):
        return sum(cf['amount'] / ((1 + rate) ** cf['years']) for cf in cashflows)

    lo, hi = -0.95, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if pv(mid) > price:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _calc_bond_floor_metrics(row, price):
    """计算双低策略的防守参考指标：纯债价值估算、到期收益率估算。"""
    par_value = safe_float(row.get('PAR_VALUE', row.get('par_value', 100))) or 100
    cashflows = _build_bond_cashflows(
        row.get('VALUE_DATE', row.get('value_date')),
        row.get('EXPIRE_DATE', row.get('maturity_date')),
        row.get('INTEREST_RATE_EXPLAIN', row.get('interest_rate_explain')),
        row.get('REDEEM_CLAUSE', row.get('redeem_clause')),
        par_value,
    )
    if not cashflows:
        return {
            'pure_bond_value': 0,
            'ytm': None,
            'bond_floor_discount_rate': _rating_discount_rate(row.get('RATING', row.get('rating'))),
            'bond_cashflows': [],
            'maturity_date': str(row.get('EXPIRE_DATE', row.get('maturity_date', '')) or ''),
        }

    discount_rate = _rating_discount_rate(row.get('RATING', row.get('rating')))
    pure_value = sum(cf['amount'] / ((1 + discount_rate) ** cf['years']) for cf in cashflows)
    ytm = _solve_ytm(price, cashflows)
    return {
        'pure_bond_value': round(pure_value, 2),
        'ytm': round(ytm * 100, 2) if ytm is not None else None,
        'bond_floor_discount_rate': round(discount_rate * 100, 2),
        'bond_cashflows': cashflows,
        'maturity_date': str(row.get('EXPIRE_DATE', row.get('maturity_date', '')) or ''),
    }


# ==================== 上游数据获取（直连 HTTP） ====================


def _derive_conversion_metrics(row, quote_price=0):
    """Build usable conversion metrics when the EM quote fields are incomplete."""
    stock_price = safe_float(row.get('CONVERT_STOCK_PRICE', 0))
    if stock_price <= 0:
        stock_price = safe_float(row.get('CONVERT_STOCK_PRICEHQ', 0))
    if stock_price <= 0:
        stock_price = safe_float(quote_price)

    conversion_price = safe_float(row.get('TRANSFER_PRICE', 0))
    if conversion_price <= 0:
        conversion_price = safe_float(row.get('INITIAL_TRANSFER_PRICE', 0))

    # RPT_BOND_CB_LIST currently duplicates the historical conversion price in
    # TRANSFER_VALUE for many rows.  It is not a live conversion value.  Only
    # combine a live underlying quote with a stated conversion price.
    conversion_value = (
        stock_price / conversion_price * 100
        if stock_price > 0 and conversion_price > 0
        else 0
    )

    force_trigger_price = safe_float(row.get('REDEEM_TRIG_PRICE', 0))
    if force_trigger_price <= 0 and conversion_price > 0:
        force_trigger_price = conversion_price * 1.3

    # RESALE_TRIG_PRICE is the conditional put-back threshold, not the downward
    # revision benchmark. The strategy continues to use its documented 85% rule.
    revise_trigger_price = conversion_price * 0.85 if conversion_price > 0 else 0

    return {
        'stock_price': round(stock_price, 4) if stock_price > 0 else 0,
        'conversion_price': round(conversion_price, 4) if conversion_price > 0 else 0,
        'conversion_value': round(conversion_value, 4) if conversion_value > 0 else 0,
        'force_trigger_price': round(force_trigger_price, 4) if force_trigger_price > 0 else 0,
        'revise_trigger_price': round(revise_trigger_price, 4) if revise_trigger_price > 0 else 0,
    }


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
        "pageNumber": "1",
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
        result = d['result']
        rows = list(result['data'])
        total_pages = int(result.get('pages') or 1)
        for page in range(2, total_pages + 1):
            params['pageNumber'] = str(page)
            page_response = em_get(_EM_BOND_LIST_URL, params=params, timeout=15)
            page_data = page_response.json()
            page_rows = (page_data.get('result') or {}).get('data') or []
            if not page_rows:
                break
            rows.extend(page_rows)
        df = pd.DataFrame(rows)
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
        # A delisted bond may remain in the EM history table and can still be
        # returned by Sina's broad quote endpoint.  It must not reach a current
        # opportunity list.
        today = datetime.now(_CHINA_TZ).date()
        if 'DELIST_DATE' in em_df.columns:
            delist_days = pd.to_datetime(em_df['DELIST_DATE'], errors='coerce').dt.date
            em_df = em_df[delist_days.isna() | (delist_days >= today)].copy()

        em_map = {}
        stock_codes = list({
            str(row.get('CONVERT_STOCK_CODE', ''))
            for _, row in em_df.iterrows()
            if row.get('CONVERT_STOCK_CODE')
        })
        stock_quotes = _fetch_sina_stock_quotes(stock_codes)
        for _, row in em_df.iterrows():
            code = str(row.get('SECURITY_CODE', ''))
            stock_code = str(row.get('CONVERT_STOCK_CODE', ''))
            metrics = _derive_conversion_metrics(
                row,
                stock_quotes.get(stock_code, {}).get('price', 0),
            )
            em_map[code] = {
                'stock_code': stock_code,
                'stock_name': str(row.get('SECURITY_SHORT_NAME', '')),
                **metrics,
                'rating': str(row.get('RATING', '')),
                'issue_size': safe_float(row.get('ACTUAL_ISSUE_SCALE', 0)),
                'list_date': str(row.get('LISTING_DATE', '')),
                'value_date': str(row.get('VALUE_DATE', '')),
                'maturity_date': str(row.get('EXPIRE_DATE', '')),
                'interest_rate_explain': str(row.get('INTEREST_RATE_EXPLAIN', '')),
                'redeem_clause': str(row.get('REDEEM_CLAUSE', '')),
                'par_value': safe_float(row.get('PAR_VALUE', 100)),
            }

        for col in ['stock_code', 'stock_name', 'stock_price', 'conversion_price',
                     'conversion_value', 'force_trigger_price', 'revise_trigger_price',
                     'rating',
                     'issue_size', 'list_date', 'value_date', 'maturity_date',
                     'interest_rate_explain', 'redeem_clause', 'par_value']:
            df[col] = df['bond_code'].map(lambda c: em_map.get(c, {}).get(col, None if col in ['stock_name', 'rating', 'list_date', 'stock_code'] else 0))

        # 填充 NaN
        for col in ['stock_code', 'stock_name', 'rating', 'list_date', 'value_date',
                    'maturity_date', 'interest_rate_explain', 'redeem_clause']:
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

            metrics = _calc_bond_floor_metrics(row, price)
            df.at[idx, 'pure_bond_value'] = metrics['pure_bond_value']
            df.at[idx, 'ytm'] = metrics['ytm'] if metrics['ytm'] is not None else 0
            df.at[idx, 'bond_floor_discount_rate'] = metrics['bond_floor_discount_rate']
            df.at[idx, 'bond_cashflows'] = json.dumps(metrics['bond_cashflows'], ensure_ascii=False)
            if metrics.get('maturity_date'):
                df.at[idx, 'maturity_date'] = metrics['maturity_date']

    else:
        # 无 EM 数据时，所有转股指标置零
        for col in ['stock_code', 'stock_name', 'stock_price', 'conversion_price',
                     'conversion_value', 'force_trigger_price', 'revise_trigger_price',
                     'premium_rate', 'rating',
                     'issue_size', 'list_date', 'double_low', 'pure_bond_value',
                     'ytm', 'bond_floor_discount_rate', 'bond_cashflows', 'maturity_date']:
            if col in ['stock_code', 'stock_name', 'rating', 'list_date', 'bond_cashflows', 'maturity_date']:
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
                'force_trigger_price': safe_float(row.get('force_trigger_price', 0)),
                'revise_trigger_price': safe_float(row.get('revise_trigger_price', 0)),
                'remaining_size': safe_float(row.get('issue_size', 0)),
                'volume': safe_float(row.get('volume', 0)),
                'amount': safe_float(row.get('amount', 0)),
                'pure_bond_value': safe_float(row.get('pure_bond_value', 0)),
                'ytm': safe_float(row.get('ytm', 0)),
                'bond_floor_discount_rate': safe_float(row.get('bond_floor_discount_rate', 0)),
                'bond_cashflows': _parse_cashflows(row.get('bond_cashflows', '')),
                'maturity_date': str(row.get('maturity_date', '')),
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
            'force_trigger_price': safe_float(row.get('force_trigger_price', 0)),
            'revise_trigger_price': safe_float(row.get('revise_trigger_price', 0)),
            'remaining_size': safe_float(row.get('issue_size', 0)),
            'volume': safe_float(row.get('volume', 0)),
            'amount': safe_float(row.get('amount', 0)),
            'pure_bond_value': safe_float(row.get('pure_bond_value', 0)),
            'ytm': safe_float(row.get('ytm', 0)),
            'bond_floor_discount_rate': safe_float(row.get('bond_floor_discount_rate', 0)),
            'bond_cashflows': _parse_cashflows(row.get('bond_cashflows', '')),
            'maturity_date': str(row.get('maturity_date', '')),
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
                    'stock_price': safe_float(row.get('stock_price', 0)),
                    'conversion_price': safe_float(row.get('conversion_price', 0)),
                    'force_trigger_price': safe_float(row.get('force_trigger_price', 0)),
                    'revise_trigger_price': safe_float(row.get('revise_trigger_price', 0)),
                    'pure_bond_value': safe_float(row.get('pure_bond_value', 0)),
                    'ytm': safe_float(row.get('ytm', 0)),
                    'bond_floor_discount_rate': safe_float(row.get('bond_floor_discount_rate', 0)),
                    'bond_cashflows': _parse_cashflows(row.get('bond_cashflows', '')),
                    'maturity_date': str(row.get('maturity_date', '')),
                    'remaining_size': safe_float(row.get('issue_size', 0)),
                    'volume': safe_float(row.get('volume', 0)),
                    'amount': safe_float(row.get('amount', 0)),
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


# ==================== 待发/配售可转债（东方财富 + 新浪 + 公告解析器） ====================


def get_pending_bonds():
    """获取待发/配售可转债列表（东方财富数据源 + 本地公告数据补充）"""
    try:
        rows = _fetch_em_pending_bonds()
        if rows:
            rows = _enrich_with_local_placement(rows)
            return rows
    except Exception as e:
        logger.warning(f'获取待发可转债失败: {e}')
    return []


def _is_pending_placement_visible(registration_date, now=None):
    """保持所有未上市观察项可见，登记日只决定状态和排序。"""
    return True


def _get_placement_observation_state(registration_date, now=None):
    """返回配售观察状态，不把登记日已过的标的从列表中删除。"""
    if not registration_date:
        return 'registration_unknown'
    try:
        record_date = datetime.strptime(str(registration_date)[:10], '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return 'registration_unknown'
    current = now or datetime.now(_CHINA_TZ)
    return 'expired' if record_date < current.date() else 'eligible'


def _is_late_stage_observation(bond, timeline):
    """判断未上市标的是否已进入末段审批或后续配售节点。"""
    registration_date = _format_date(bond.get('SECURITY_START_DATE'))
    apply_date = _format_date(bond.get('PUBLIC_START_DATE'))
    if registration_date or apply_date:
        return True
    stage_dates = (timeline or {}).get('stage_dates', {})
    return bool(stage_dates.get('上市委通过') or stage_dates.get('同意注册'))


def _enrich_with_local_placement(rows):
    """用本地公告数据库的配售结果覆盖预估数据

    对于已完成配售的债券，公告数据更准确（来自交易所官方公告）。
    东方财富的预估配售率在配售完成前可能为 0。
    """
    try:
        from services.announcement_parser import get_placement_by_stock
    except ImportError:
        return rows

    for row in rows:
        stock_code = row.get('stock_code', '')
        if not stock_code:
            continue

        local_data = get_placement_by_stock(stock_code)
        if local_data and local_data.get('shareholder_ratio') is not None:
            row['shareholder_ratio'] = local_data['shareholder_ratio']
            if local_data.get('issue_size'):
                tradable = local_data['issue_size'] * (
                    1 - local_data['shareholder_ratio'] / 100
                )
                row['tradable_amount'] = round(tradable, 2)
            if local_data.get('online_ratio') is not None:
                row['win_rate'] = local_data['online_ratio']
            row['_placement_source'] = 'announcement'

    return rows


def _fetch_em_pending_bonds():
    """从东方财富获取待发/配售可转债列表

    使用 RPT_BOND_CB_LIST 报告，筛选 LISTING_DATE 为空的债券（尚未上市）。
    配合新浪实时行情、东财估值分析和K线数据补充 PB / MA20 等字段。
    """
    # 1. 获取全部可转债数据
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
            logger.warning(f'[EmPending] HTTP {resp.status_code}')
            return []
        d = resp.json()
        if not (d.get("result") and d["result"].get("data")):
            return []
        all_bonds = d["result"]["data"]
    except Exception as e:
        logger.warning(f'[EmPending] 获取东财可转债数据失败: {e}')
        return []

    # 2. 筛选未上市且已进入末段审批或后续配售节点的债券。
    pending = [b for b in all_bonds if not b.get('LISTING_DATE')]
    now = datetime.now(_CHINA_TZ)
    timeline_by_stock = _load_timeline_cache(
        [str(b.get('CONVERT_STOCK_CODE', '')) for b in pending]
    )
    pending = [
        b for b in pending
        if _is_late_stage_observation(
            b, timeline_by_stock.get(str(b.get('CONVERT_STOCK_CODE', '')), {})
        )
    ]
    if not pending:
        return []

    logger.info(f'[EmPending] 共 {len(all_bonds)} 条转债，{len(pending)} 条未上市')

    # 3. 批量获取正股实时行情（新浪）
    stock_codes = list(set(str(b.get('CONVERT_STOCK_CODE', '')) for b in pending if b.get('CONVERT_STOCK_CODE')))
    stock_quotes = _fetch_sina_stock_quotes(stock_codes)

    # 4. 批量获取 PB / 总股本（东财估值分析）
    stock_fundamentals = _fetch_stock_fundamentals(stock_codes)

    # 5. 只读取日级 MA20 缓存。缓存未命中由列表响应后的后台任务补全，
    # 避免上游 K 线重试阻塞配售列表首屏。
    ma20_map = _load_cached_ma20(stock_codes)

    # 6. 组装结果
    result = []
    for bond in pending:
        stock_code = str(bond.get('CONVERT_STOCK_CODE', ''))
        bond_code = str(bond.get('SECURITY_CODE', ''))
        stock_name = str(bond.get('SECURITY_SHORT_NAME', ''))
        bond_name = str(bond.get('CORRECODE_NAME_ABBR', ''))

        # 正股行情（新浪）
        sq = stock_quotes.get(stock_code, {})
        stock_price = sq.get('price', 0)
        stock_change = sq.get('change_pct', 0)

        # 估值数据（东财）
        sf = stock_fundamentals.get(stock_code, {})
        pb = sf.get('pb', 0)
        total_shares = sf.get('total_shares', 0)  # 股

        # 债券核心字段
        issue_size = safe_float(bond.get('ACTUAL_ISSUE_SCALE', 0))        # 亿
        conversion_price = safe_float(bond.get('INITIAL_TRANSFER_PRICE', 0))
        per_share_alloc = safe_float(bond.get('FIRST_PER_PREPLACING', 0))  # 元/股
        rating = str(bond.get('RATING', '') or '')

        # 日期字段
        pub_start = bond.get('PUBLIC_START_DATE', '')
        sec_start = bond.get('SECURITY_START_DATE', '')
        apply_date = _format_date(pub_start)
        registration_date = _format_date(sec_start)
        observation_state = _get_placement_observation_state(registration_date, now)

        # 申购代码
        apply_code = str(bond.get('CORRECODE', '') or '')

        # 中签率
        win_rate = safe_float(bond.get('ONLINE_GENERAL_LWR', 0))

        # 每股配售额 → 10 张所需股数
        shares_for_10_lots = 0
        if per_share_alloc > 0:
            shares_for_10_lots = round(1000 / per_share_alloc)

        # 未上市债券没有可验证的首日收益。保留字段以兼容旧客户端，
        # 但用 None 明确表示不可用，且不将其注入优配评分。
        expected_profit = None
        safety_pad = None

        # 正股偏离 MA20
        ma20_price = ma20_map.get(stock_code, 0)
        stock_trend = 0
        if ma20_price > 0 and stock_price > 0:
            stock_trend = round((stock_price - ma20_price) / ma20_price * 100, 2)

        # 正股/转债比 = 总市值(亿) / 发行规模(亿)，用于策略评分。
        stock_cash_ratio = 0
        if total_shares > 0 and stock_price > 0 and issue_size > 0:
            mkt_cap_yi = stock_price * total_shares / 1e8
            stock_cash_ratio = round(mkt_cap_yi / issue_size, 2)

        # 百元含权 = 每股配售额 / 正股价格 * 100。
        # 它与 stock_cash_ratio 的评分口径不同，单独提供给客户端展示。
        cash_ratio = _calc_cash_ratio(per_share_alloc, stock_price)

        # 股权登记日价格（近似为当前价，盘中会动态变化）
        record_price = stock_price

        # 状态推导（基于日期）
        status = _get_status_from_dates(pub_start, apply_date, now)

        # 首日可交易量（亿）
        # 东财不提供股东配售率，默认等于发行规模
        # 配售完成后由公告数据 (_enrich_with_local_placement) 覆盖
        tradable_amount = issue_size

        # 配售三因子评分
        strategy_score = None
        strategy_rating = 'observation'
        risk_level = 'unverified'

        result.append({
            'stock_code': stock_code,
            'stock_name': stock_name,
            'bond_code': bond_code,
            'bond_name': bond_name,
            'progress': status,
            'progress_dt': apply_date,
            'progress_full': _build_progress_full(
                timeline_by_stock.get(stock_code, {}).get('stage_dates', {}),
                status,
                apply_date,
                registration_date,
            ),
            'issue_size': issue_size,
            'rating': rating,
            'shareholder_ratio': 0,  # 待配售完成后由公告数据覆盖
            'conversion_price': conversion_price,
            'stock_price': stock_price,
            'stock_change': stock_change,
            'pb': pb,
            'per_share_allocation': per_share_alloc,
            'shares_for_10_lots': shares_for_10_lots,
            'registration_date': registration_date,
            'placement_observation_state': observation_state,
            'online_issue_size': 0,
            'win_rate': win_rate,
            'apply_date': apply_date,
            'list_date': '',
            'apply_code': apply_code,
            'ration_code': '',
            'status': status,
            'cash_ratio': cash_ratio,
            'stock_cash_ratio': stock_cash_ratio,
            'record_price': record_price,
            'ma20_price': ma20_price,
            'expected_profit': expected_profit,
            'safety_pad': safety_pad,
            'stock_trend': stock_trend,
            'strategy_score': strategy_score,
            'tradable_amount': round(tradable_amount, 2),
            'strategy_rating': strategy_rating,
            'risk_level': risk_level,
            'strategy_status': 'observation',
            'eligibility_verified': False,
            'evidence_note': '需以发行公告核验优配资格、缴款截止和配售代码后方可执行。',
        })

    return result


def _fetch_sina_stock_quotes(stock_codes):
    """批量获取正股实时行情（新浪财经）

    返回 {stock_code: {'price': float, 'change_pct': float, 'name': str}}
    """
    if not stock_codes:
        return {}

    # 构造新浪 secid：SH → shCODE, SZ → szCODE。分批避免 URL 过长。
    symbols = []
    for code in stock_codes:
        code_str = str(code)
        if code_str.startswith(('6', '9')):
            sym = f'sh{code_str}'
        else:
            sym = f'sz{code_str}'
        symbols.append(sym)
    result = {}
    for start in range(0, len(symbols), 100):
        url = _SINA_STOCK_QUOTE_URL + ','.join(symbols[start:start + 100])
        try:
            resp = sina_get(url, timeout=10)
            resp.encoding = 'gbk'
            for line in resp.text.strip().split('\n'):
                if '="' not in line:
                    continue
                # 解析 var hq_str_sh600389="江山股份,18.82,..."
                var_part, data_part = line.split('="', 1)
                sym = var_part.split('_')[-1]  # sh600389
                stock_code = sym[2:]            # 600389
                data = data_part.rstrip('";')
                parts = data.split(',')
                if len(parts) < 10:
                    continue
                price = safe_float(parts[3])
                prev_close = safe_float(parts[2])
                change_pct = 0
                if prev_close > 0 and price > 0:
                    change_pct = round((price - prev_close) / prev_close * 100, 2)
                result[stock_code] = {
                    'price': price,
                    'change_pct': change_pct,
                    'name': parts[0],
                }
        except Exception as e:
            logger.warning(f'[SinaStock] 获取正股行情失败: {e}')
    return result


def _fetch_stock_fundamentals(stock_codes):
    """批量获取 PB / 总股本（东方财富 RPT_VALUEANALYSIS_DET）

    返回 {stock_code: {'pb': float, 'total_shares': int}}
    """
    if not stock_codes:
        return {}

    codes_str = ','.join(f'"{c}"' for c in stock_codes)
    params = {
        'reportName': 'RPT_VALUEANALYSIS_DET',
        'columns': 'SECURITY_CODE,PB_MRQ,TOTAL_SHARES,CLOSE_PRICE',
        'source': 'WEB',
        'client': 'WEB',
        'filter': f'(SECURITY_CODE in ({codes_str}))',
        'pageSize': str(len(stock_codes) * 3),  # 每只股票可能返回多行（多日）
        'sortColumns': 'TRADE_DATE',
        'sortTypes': '-1',
    }
    try:
        resp = em_get(_EM_BOND_LIST_URL, params=params, timeout=15)
        if resp.status_code != 200:
            return {}
        d = resp.json()
        if not (d.get('result') and d['result'].get('data')):
            return {}

        # 每只股票取最新一行
        result = {}
        for row in d['result']['data']:
            code = str(row.get('SECURITY_CODE', ''))
            if code and code not in result:
                result[code] = {
                    'pb': safe_float(row.get('PB_MRQ', 0)),
                    'total_shares': safe_float(row.get('TOTAL_SHARES', 0)),
                }
        return result
    except Exception as e:
        logger.warning(f'[EmFundamentals] 获取估值数据失败: {e}')
        return {}


def _fetch_stock_ma20(stock_code):
    """获取单只股票的 20 日均线（东方财富K线 API）"""
    code_str = str(stock_code)
    if code_str.startswith(('6', '9')):
        secid = f'1.{code_str}'
    else:
        secid = f'0.{code_str}'

    params = {
        'secid': secid,
        'fields1': 'f1,f2,f3,f4,f5,f6',
        'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
        'klt': '101',    # 日K
        'fqt': '1',      # 前复权
        'end': '20500101',
        'lmt': '25',     # 最近 25 根K线
        'ut': 'fa5fd1943c7b386f172d6893dbbd1',
    }
    try:
        resp = em_get(_EM_KLINE_URL, params=params, timeout=10)
        d = resp.json()
        klines = d.get('data', {}).get('klines', []) if d.get('data') else []
        if len(klines) < 20:
            return 0
        closes = [float(k.split(',')[2]) for k in klines[-20:]]
        return round(sum(closes) / 20, 2)
    except Exception as e:
        logger.warning(f'[EmKline] {stock_code} MA20 获取失败: {e}')
        return 0


def _format_date(dt_val):
    """将 API 返回的日期值格式化为 YYYY-MM-DD 字符串"""
    if not dt_val:
        return ''
    s = str(dt_val)
    # 东财返回 "2026-07-14 00:00:00" 格式，取日期部分
    return s.split(' ')[0] if ' ' in s else s


def _load_timeline_cache(stock_codes):
    """一次查询读取当前列表所需的历史时间轴节点。"""
    codes = [str(code) for code in stock_codes if code]
    if not codes:
        return {}

    try:
        from models.convertible_timeline import ConvertibleTimeline
        from models.database import get_db_session

        with get_db_session() as db:
            records = db.query(ConvertibleTimeline).filter(
                ConvertibleTimeline.stock_code.in_(codes)
            ).all()
            result = {}
            for record in records:
                try:
                    stage_dates = json.loads(record.stage_dates or '{}')
                except (TypeError, json.JSONDecodeError):
                    stage_dates = {}
                result[record.stock_code] = {
                    'stage_dates': {
                        stage: date for stage, date in stage_dates.items()
                        if stage in _TIMELINE_STAGES and _format_date(date)
                    },
                    'last_checked_at': record.last_checked_at,
                }
            return result
    except Exception as e:
        logger.warning(f'[Timeline] 读取缓存失败: {e}')
        return {}


def _timeline_needs_refresh(cached_timeline, now=None):
    stage_dates = cached_timeline.get('stage_dates', {}) if cached_timeline else {}
    if all(stage in stage_dates for stage in _TIMELINE_STAGES):
        return False

    last_checked_at = cached_timeline.get('last_checked_at') if cached_timeline else None
    current = now or datetime.now()
    return last_checked_at is None or current - last_checked_at >= _TIMELINE_REFRESH_INTERVAL


def _ma20_cache_key(stock_code):
    return f'convertible:ma20:{stock_code}'


def _load_cached_ma20(stock_codes):
    from services.cache import get_cache_manager

    cache = get_cache_manager()
    result = {}
    for stock_code in stock_codes:
        cached = cache.get(_ma20_cache_key(stock_code))
        if cached is None:
            continue
        if isinstance(cached, dict):
            result[stock_code] = safe_float(cached.get('value', 0))
        else:
            result[stock_code] = safe_float(cached)
    return result


def schedule_pending_enrichment(rows):
    """在列表缓存写入后，串行补全 MA20 与缺失的历史时间轴节点。"""
    from services.cache import get_cache_manager

    stock_codes = [
        str(row.get('stock_code') or row.get('CONVERT_STOCK_CODE') or '')
        for row in rows
    ]
    timeline_by_stock = _load_timeline_cache(stock_codes)
    timeline_candidates = []
    ma20_candidates = []
    cache = get_cache_manager()

    for bond in rows:
        stock_code = str(bond.get('stock_code') or bond.get('CONVERT_STOCK_CODE') or '')
        if stock_code and _timeline_needs_refresh(timeline_by_stock.get(stock_code)):
            bond_code = str(bond.get('bond_code') or bond.get('SECURITY_CODE') or '')
            timeline_candidates.append((stock_code, bond_code))
        if stock_code and cache.get(_ma20_cache_key(stock_code)) is None:
            ma20_candidates.append(stock_code)

    if not timeline_candidates and not ma20_candidates:
        return

    with _TIMELINE_REFRESH_LOCK:
        timeline_candidates = [
            item for item in timeline_candidates if item[0] not in _TIMELINE_REFRESHING
        ]
        ma20_candidates = [
            stock_code for stock_code in ma20_candidates if stock_code not in _MA20_REFRESHING
        ]
        if not timeline_candidates and not ma20_candidates:
            return
        _TIMELINE_REFRESHING.update(stock_code for stock_code, _ in timeline_candidates)
        _MA20_REFRESHING.update(ma20_candidates)

    threading.Thread(
        target=_pending_enrichment_worker,
        args=(ma20_candidates, timeline_candidates),
        name='convertible-pending-enrichment',
        daemon=True,
    ).start()


def _pending_enrichment_worker(ma20_candidates, timeline_candidates):
    from services.cache import get_cache_manager

    refreshed = False
    try:
        cache = get_cache_manager()
        for stock_code in ma20_candidates:
            ma20 = _fetch_stock_ma20(stock_code)
            cache.set(
                _ma20_cache_key(stock_code),
                {'value': ma20},
                _MA20_CACHE_TTL if ma20 > 0 else _MA20_FAILURE_TTL,
            )
            refreshed = refreshed or ma20 > 0

        for stock_code, bond_code in timeline_candidates:
            try:
                stage_dates = _fetch_stage_dates_from_notice(stock_code)
                _save_timeline_cache(stock_code, bond_code, stage_dates)
                refreshed = refreshed or bool(stage_dates)
            except Exception as e:
                logger.warning(f'[Timeline] {stock_code} 刷新失败: {e}')
    finally:
        with _TIMELINE_REFRESH_LOCK:
            _MA20_REFRESHING.difference_update(ma20_candidates)
            _TIMELINE_REFRESHING.difference_update(
                stock_code for stock_code, _ in timeline_candidates
            )

    if refreshed:
        cache.delete('convertible:pending:data')


def _save_timeline_cache(stock_code, bond_code, stage_dates):
    """按节点合并保存；同一节点保留最早公告日。"""
    from models.convertible_timeline import ConvertibleTimeline
    from models.database import get_db_session

    normalized = {
        stage: _format_date(date)
        for stage, date in stage_dates.items()
        if stage in _TIMELINE_STAGES and _format_date(date)
    }
    with get_db_session() as db:
        record = db.query(ConvertibleTimeline).filter_by(stock_code=stock_code).first()
        if record is None:
            record = ConvertibleTimeline(stock_code=stock_code, bond_code=bond_code)
            db.add(record)
            current_dates = {}
        else:
            try:
                current_dates = json.loads(record.stage_dates or '{}')
            except (TypeError, json.JSONDecodeError):
                current_dates = {}

        for stage, date in normalized.items():
            if stage not in current_dates or date < current_dates[stage]:
                current_dates[stage] = date
        record.bond_code = bond_code or record.bond_code
        record.stage_dates = json.dumps(current_dates, ensure_ascii=False, sort_keys=True)
        record.last_checked_at = datetime.now()


def _build_progress_full(stage_dates, status, apply_date, registration_date):
    """组装 progress_full 字符串，供前端 parseProgressDates 解析

    格式：每行 `YYYY-MM-DD 阶段名`
    例：`2026-05-07 董事会预案;2026-05-09 股东大会批准;2026-06-17 同意注册;2026-07-13 股权登记日;2026-07-14 申购中`
    """
    parts = []
    # 1) 读取已持久化的公告节点；缺失节点由后台刷新任务补全。
    for stage in _TIMELINE_STAGES:
        d = stage_dates.get(stage)
        if d:
            parts.append(f'{d} {stage}')
    # 2) 股权登记日
    if registration_date:
        parts.append(f'{registration_date} 股权登记日')
    # 3) 申购中（必有，否则不展示）
    if apply_date and status == '申购中':
        parts.append(f'{apply_date} 申购中')
    return ';'.join(parts)


def _fetch_stage_dates_from_notice(stock_code, max_pages=2, page_size=100):
    """通过 EM 公告接口解析前 5 阶段日期（董事会预案→同意注册）

    公告按时间倒序返回，从最近 200 条中匹配 5 个阶段对应的关键词。
    匹配规则：每阶段只保留**最早**一条公告（因为预案可能会"二次修订"，
    但作为首次进入该阶段的标志，应取最早的公告日期）。
    """
    if not stock_code:
        return {}

    stage_dates = {}
    for page in range(1, max_pages + 1):
        params = {
            'cb': 'jQuery_callback',
            'page_size': page_size,
            'page_index': page,
            'ann_type': 'A',
            'client_source': 'web',
            'stock_list': stock_code,
            'f_node': '0',
            's_node': '0',
        }
        try:
            resp = em_get(_EM_NOTICE_URL, params=params, timeout=10)
            if resp.status_code != 200:
                break
            text = resp.text
            # 去掉 jQuery 包装
            m = re.search(r'jQuery_callback\((.*)\)', text, re.S)
            if not m:
                break
            data = json.loads(m.group(1))
            items = data.get('data', {}).get('list', [])
            if not items:
                break
            for it in items:
                title = it.get('title', '') or it.get('title_ch', '')
                if not title:
                    continue
                notice_date = _format_date(it.get('notice_date', ''))
                if not notice_date:
                    continue
                # 跳过与可转债无关的公告（减少误匹配）
                if '可转债' not in title and '可转换公司债券' not in title and '转债' not in title:
                    continue
                for stage, keywords in _STAGE_KEYWORDS:
                    for kw in keywords:
                        if kw in title:
                            previous_date = stage_dates.get(stage)
                            if not previous_date or notice_date < previous_date:
                                stage_dates[stage] = notice_date
                            break
            # 5 个阶段都齐了就停
            if len(stage_dates) >= 5:
                break
        except Exception as e:
            logger.warning(f'[StageDates] {stock_code} 第{page}页失败: {e}')
            break

    return stage_dates


def _get_status_from_dates(pub_start_raw, apply_date_str, now):
    """根据日期推导债券状态"""
    if not pub_start_raw:
        return '--'
    try:
        if isinstance(pub_start_raw, str):
            pub_dt = datetime.strptime(pub_start_raw.split(' ')[0], '%Y-%m-%d')
        else:
            pub_dt = pub_start_raw
        if pub_dt.date() > now.date():
            return '申购中'  # 尚未到申购日
        else:
            return '待上市'  # 已过申购日但未上市
    except Exception:
        return '--'


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


def _calc_cash_ratio(per_share_allocation, stock_price):
    """计算百元含权；输入无效时返回 0。"""
    per_share = safe_float(per_share_allocation)
    price = safe_float(stock_price)
    if per_share <= 0 or price <= 0:
        return 0
    return round(per_share / price * 100, 2)


def _calc_placement_score(issue_size, tradable_amount, safety_pad):
    """配售三因子评分 0-100
    tradable_amount: 首日可交易量（亿），= 发行规模 - 原股东配售部分
    """
    size_score = max(0, 1 - issue_size / 10) * 30
    float_score = (1 - tradable_amount / issue_size) * 40 if issue_size > 0 else 0
    safety_score = min(safety_pad / 10, 1) * 30
    return round(size_score + float_score + safety_score)


def _get_rating_by_score(score):
    if score >= 70:
        return 'recommend'
    if score >= 40:
        return 'watch'
    return 'caution'


def _get_risk_level(safety_pad):
    if safety_pad is None:
        return 'unverified'
    if safety_pad < 3:
        return 'high'
    elif safety_pad > 8:
        return 'low'
    return 'mid'
