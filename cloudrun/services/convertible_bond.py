import akshare as ak
import pandas as pd


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


def safe_float(val, default=0):
    """安全转换为float"""
    try:
        if pd.isna(val):
            return default
        return float(val)
    except:
        return default


def _get_sina_bonds():
    """从新浪源获取实时可转债行情（320+条）"""
    try:
        df = ak.bond_zh_hs_cov_spot()
        if df is None or df.empty:
            return None
        return df
    except Exception as e:
        print(f'获取新浪可转债数据失败: {e}')
        return None


def _get_em_bonds():
    """从东方财富获取可转债转股指标（1000+条，含溢价率/转股价值/评级）"""
    try:
        df = ak.bond_zh_cov()
        if df is None or df.empty:
            return None
        return df
    except Exception as e:
        print(f'获取东方财富可转债数据失败: {e}')
        return None


def _parse_sina_symbol(symbol):
    """解析新浪 symbol（如 sh110073）得到纯代码"""
    symbol = str(symbol)
    if symbol.startswith('sh'):
        return symbol[2:]
    elif symbol.startswith('sz'):
        return symbol[2:]
    elif symbol.startswith('bj'):
        return symbol[2:]
    return symbol


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
    em_df = _get_em_bonds()
    if em_df is not None and not em_df.empty:
        em_map = {}
        for _, row in em_df.iterrows():
            code = str(row.get('债券代码', ''))
            em_map[code] = {
                'stock_code': str(row.get('正股代码', '')),
                'stock_name': str(row.get('正股简称', '')),
                'stock_price': safe_float(row.get('正股价', 0)),
                'conversion_price': safe_float(row.get('转股价', 0)),
                'conversion_value': safe_float(row.get('转股价值', 0)),
                'premium_rate': safe_float(row.get('转股溢价率', 0)),
                'rating': str(row.get('信用评级', '')),
                'issue_size': safe_float(row.get('发行规模', 0)),
                'list_date': str(row.get('上市时间', '')),
            }

        for col in ['stock_code', 'stock_name', 'stock_price', 'conversion_price',
                     'conversion_value', 'premium_rate', 'rating',
                     'issue_size', 'list_date']:
            df[col] = df['bond_code'].map(lambda c: em_map.get(c, {}).get(col, None if col in ['stock_name', 'rating', 'list_date', 'stock_code'] else 0))

        # 填充 NaN（String 列 map 不到会变成 NaN）
        for col in ['stock_code', 'stock_name', 'rating', 'list_date']:
            df[col] = df[col].fillna('')

        # 计算双低 = 实时价格 + 溢价率
        for idx, row in df.iterrows():
            pr = row.get('premium_rate', 0)
            if pr and pr != 0 and row['price'] != 0:
                df.at[idx, 'double_low'] = round(row['price'] + pr, 2)
            else:
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


def get_market_temperature():
    """获取可转债市场温度"""
    try:
        df = _merge_bond_data()
        if df is None or df.empty:
            return None

        valid = df[df['premium_rate'] != 0]
        if valid.empty:
            return None

        price_median = float(df['price'].median())
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
            'price_min': round(float(df['price'].min()), 2),
            'price_max': round(float(df['price'].max()), 2),
            'price_median': round(price_median, 2),
            'premium_median': round(premium_median, 2),
            'double_low_median': round(double_low_median, 1),
            'market_status': market_status,
            'source': 'sina+em',
            'ticktime': str(df['ticktime'].iloc[0]) if 'ticktime' in df.columns else '',
        }
    except Exception as e:
        print(f'获取可转债市场温度失败: {e}')
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
        print(f'获取可转债列表失败: {e}')
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

        return result
    except Exception as e:
        print(f'获取可转债详情失败: {e}')
        return {}


def get_convertible_bond_signals():
    """获取可转债信号，返回英文字段的 dict"""
    try:
        df = _merge_bond_data()
        if df is None or df.empty:
            return None

        valid = df[df['premium_rate'] != 0].copy()
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
        print(f'获取可转债信号失败: {e}')
        return None
