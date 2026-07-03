import akshare as ak
import pandas as pd
import numpy as np


def safe_float(val, default=0):
    """安全转换为float"""
    try:
        if pd.isna(val):
            return default
        return float(val)
    except:
        return default


def get_lof_list():
    """获取LOF基金列表（含溢价率信息）"""
    try:
        df = ak.fund_lof_spot_em()
        if df is None or df.empty:
            return []

        result = []
        for _, row in df.iterrows():
            code = str(row.get('代码', ''))
            # 从代码提取交易所标识
            if code.startswith('sh') or code.startswith('5'):
                exchange = '沪'
            elif code.startswith('sz') or code.startswith('1'):
                exchange = '深'
            else:
                exchange = ''

            result.append({
                '代码': code,
                '名称': str(row.get('名称', '')),
                '交易所': exchange,
                '最新价': safe_float(row.get('最新价')),
                '涨跌幅': safe_float(row.get('涨跌幅')),
                '估值': safe_float(row.get('基金净值', 0)),
                '溢价率': safe_float(row.get('溢价率', 0)),
                '连续溢价': int(safe_float(row.get('连续溢价天数', 0))),
                '申购状态': str(row.get('申购状态', '不限')),
                '成交量': safe_float(row.get('成交量', 0)),
                '成交额': safe_float(row.get('成交额', 0))
            })
        return result
    except Exception as e:
        print(f'获取LOF列表失败: {e}')
        return []


def get_lof_opportunities():
    """获取LOF套利机会"""
    try:
        lof_list = get_lof_list()
        if not lof_list:
            return {'premium': [], 'discount': []}

        sorted_premium = sorted(lof_list, key=lambda x: x['溢价率'], reverse=True)[:20]
        sorted_discount = sorted(lof_list, key=lambda x: x['溢价率'])[:20]

        return {
            'premium': sorted_premium,
            'discount': sorted_discount
        }
    except Exception as e:
        print(f'获取LOF套利机会失败: {e}')
        return {'premium': [], 'discount': []}


def get_lof_market_summary():
    """获取LOF市场概览"""
    try:
        lof_list = get_lof_list()
        if not lof_list:
            return None

        premiums = [item['溢价率'] for item in lof_list]
        positive_count = sum(1 for p in premiums if p > 0)
        paused_count = sum(1 for item in lof_list if item['申购状态'] == '暂停')

        return {
            'count': len(lof_list),
            'premium_avg': round(sum(premiums) / len(premiums), 2),
            'top_premium': round(max(premiums), 2),
            'positive_count': positive_count,
            'positive_rate': round(positive_count / len(lof_list) * 100, 1),
            'paused_count': paused_count
        }
    except Exception as e:
        print(f'获取LOF市场概览失败: {e}')
        return None
