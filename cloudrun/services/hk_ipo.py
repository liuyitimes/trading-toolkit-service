import akshare as ak
import pandas as pd

def get_hk_ipo_list():
    """获取港股IPO列表"""
    try:
        df = ak.stock_hk_ipo_info_em()
        if df.empty:
            return []

        result = []
        for _, row in df.iterrows():
            result.append({
                'code': str(row['代码']),
                'name': str(row['名称']),
                'ipo_price': float(row['发行价']) if pd.notna(row['发行价']) else 0,
                'status': str(row['状态']),
                'list_date': str(row['上市日期']) if pd.notna(row['上市日期']) else '',
                'change_pct': float(row['涨跌幅']) if pd.notna(row['涨跌幅']) else 0
            })
        return result
    except Exception as e:
        return []

def get_hk_ipo_upcoming():
    """获取即将上市的港股IPO"""
    try:
        df = ak.stock_hk_ipo_info_em()
        if df.empty:
            return []

        upcoming = df[df['状态'] == '申购中'].head(10)
        if upcoming.empty:
            return []

        result = []
        for _, row in upcoming.iterrows():
            result.append({
                'code': str(row['代码']),
                'name': str(row['名称']),
                'ipo_price': float(row['发行价']) if pd.notna(row['发行价']) else 0,
                'list_date': str(row['上市日期']) if pd.notna(row['上市日期']) else '',
                'lot_size': int(row['每手股数']) if pd.notna(row['每手股数']) else 1000
            })
        return result
    except Exception as e:
        return []

def get_hk_ipo_summary():
    """获取港股打新市场概览"""
    try:
        df = ak.stock_hk_ipo_info_em()
        if df.empty:
            return {'upcoming_count': 0, 'recent_count': 0}

        upcoming_count = int(df[df['状态'] == '申购中'].shape[0])
        recent_count = int(df[df['状态'] == '已上市'].head(10).shape[0])

        return {
            'upcoming_count': upcoming_count,
            'recent_count': recent_count
        }
    except Exception as e:
        return {'error': str(e)}
