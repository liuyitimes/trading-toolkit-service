import akshare as ak
import pandas as pd


def get_hk_ipo_list():
    """获取港股IPO列表"""
    try:
        df = ak.stock_ipo_hk_ths()
        if df is None or df.empty:
            return []

        result = []
        for _, row in df.iterrows():
            code = str(row.get('股票代码', ''))
            name = str(row.get('股票简称', ''))
            ipo_price = 0
            try:
                ipo_price = float(row.get('发行价格', 0))
            except (ValueError, TypeError):
                pass

            apply_date = str(row.get('申购日期', ''))
            list_date = str(row.get('上市日期', ''))
            win_rate = str(row.get('中签率（%）', ''))

            result.append({
                'code': code,
                'name': name,
                'ipo_price': ipo_price,
                'apply_date': apply_date,
                'list_date': list_date if list_date != '-' else '',
                'win_rate': win_rate if win_rate != '-' else '',
                'pe_ratio': str(row.get('发行市盈率', '')),
                'industry_pe': str(row.get('行业市盈率', '')),
            })
        return result
    except Exception as e:
        print(f'获取港股IPO列表失败: {e}')
        return []


def get_hk_ipo_upcoming():
    """获取申购中的港股IPO"""
    try:
        df = ak.stock_ipo_hk_ths()
        if df is None or df.empty:
            return []

        # 筛选未上市的（上市日期为 "-" 的）
        upcoming = df[df['上市日期'].astype(str) == '-'].head(10)
        if upcoming.empty:
            return []

        result = []
        for _, row in upcoming.iterrows():
            ipo_price = 0
            try:
                ipo_price = float(row.get('发行价格', 0))
            except (ValueError, TypeError):
                pass

            result.append({
                'code': str(row.get('股票代码', '')),
                'name': str(row.get('股票简称', '')),
                'ipo_price': ipo_price,
                'apply_date': str(row.get('申购日期', '')),
                'lot_size': 0,
            })
        return result
    except Exception as e:
        print(f'获取即将上市港股IPO失败: {e}')
        return []


def get_hk_ipo_summary():
    """获取港股打新市场概览"""
    try:
        df = ak.stock_ipo_hk_ths()
        if df is None or df.empty:
            return {'upcoming_count': 0, 'recent_count': 0, 'total': 0}

        upcoming = df[df['上市日期'].astype(str) == '-']
        listed = df[df['上市日期'].astype(str) != '-']

        return {
            'upcoming_count': int(upcoming.shape[0]),
            'recent_count': int(listed.head(10).shape[0]),
            'total': int(df.shape[0]),
        }
    except Exception as e:
        print(f'获取港股打新概览失败: {e}')
        return {'error': str(e)}
