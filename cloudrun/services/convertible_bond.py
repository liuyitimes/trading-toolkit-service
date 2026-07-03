import akshare as ak
import pandas as pd
import numpy as np


def get_exchange_by_code(code):
    """根据代码判断交易所"""
    code_str = str(code)
    if code_str.startswith(('sh', '5', '6', '9', '11', '13')):
        return '沪'
    elif code_str.startswith(('sz', '0', '1', '2', '3', '12')):
        return '深'
    elif code_str.startswith(('4', '8')):
        return '北'
    return ''


def safe_float(val, default=0):
    """安全转换为float"""
    try:
        if pd.isna(val):
            return default
        return float(val)
    except:
        return default


def get_market_temperature():
    """获取可转债市场温度"""
    try:
        df = ak.bond_cb_jsl()
        if df is None or df.empty:
            return None

        price_median = float(df['转债价格'].median())
        premium_median = float(df['转股溢价率'].median())
        double_low_median = float(df['双低'].median())

        if double_low_median < 150:
            market_status = '偏低，可关注'
        elif double_low_median < 180:
            market_status = '合理，可适当关注'
        else:
            market_status = '偏高，需谨慎'

        return {
            'count': int(df['转债代码'].nunique()),
            'price_min': round(float(df['转债价格'].min()), 2),
            'price_max': round(float(df['转债价格'].max()), 2),
            'price_median': round(price_median, 2),
            'premium_median': round(premium_median, 2),
            'double_low_median': round(double_low_median, 1),
            'market_status': market_status
        }
    except Exception as e:
        print(f'获取可转债市场温度失败: {e}')
        return None


def get_convertible_bond_list():
    """获取可转债列表"""
    try:
        df = ak.bond_cb_jsl()
        if df is None or df.empty:
            return []

        result = []
        for _, row in df.iterrows():
            stock_code = str(row.get('正股代码', ''))
            result.append({
                '转债代码': str(row['转债代码']),
                '转债名称': str(row['转债名称']),
                '转债价格': safe_float(row['转债价格']),
                '正股名称': str(row.get('正股名称', '')),
                '正股代码': stock_code,
                '交易所': get_exchange_by_code(stock_code),
                '转股价值': safe_float(row['转股价值']),
                '转股溢价率': safe_float(row['转股溢价率']),
                '双低': safe_float(row['双低'])
            })
        return result
    except Exception as e:
        print(f'获取可转债列表失败: {e}')
        return []


def get_convertible_bond_signals():
    """获取可转债信号"""
    try:
        df = ak.bond_cb_jsl()
        if df is None or df.empty:
            return None

        # 添加交易所标识
        df['交易所'] = df['正股代码'].apply(lambda x: get_exchange_by_code(str(x)))

        # 双低策略 Top20
        double_low = df.nsmallest(20, '双低')

        # 强赎信号：溢价率<10% 且价格105-140
        force_redeem = df[
            (df['转股溢价率'] < 10) &
            (df['转债价格'] >= 105) &
            (df['转债价格'] <= 140)
        ].head(10)

        # 折价套利：溢价率<0
        discount = df[df['转股溢价率'] < 0].head(10)

        # 下修博弈：溢价率>50% 且价格<115
        down_revised = df[
            (df['转股溢价率'] > 50) &
            (df['转债价格'] < 115)
        ].head(10)

        def df_to_records(sub_df):
            records = []
            for _, row in sub_df.iterrows():
                records.append({
                    '转债代码': str(row['转债代码']),
                    '转债名称': str(row['转债名称']),
                    '转债价格': safe_float(row['转债价格']),
                    '正股名称': str(row.get('正股名称', '')),
                    '正股代码': str(row.get('正股代码', '')),
                    '交易所': str(row.get('交易所', '')),
                    '转股价值': safe_float(row['转股价值']),
                    '转股溢价率': safe_float(row['转股溢价率']),
                    '双低': safe_float(row['双低'])
                })
            return records

        return {
            'double_low': df_to_records(double_low),
            'force_redeem': df_to_records(force_redeem),
            'discount': df_to_records(discount),
            'down_revised': df_to_records(down_revised)
        }
    except Exception as e:
        print(f'获取可转债信号失败: {e}')
        return None
