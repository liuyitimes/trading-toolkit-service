from flask import Flask, jsonify, request
from flask_cors import CORS
from mock_data import CONVERTIBLE_BOND_LIST, LOF_LIST, HK_IPO_LIST, MARKET_SENTIMENT, FUND_FLOW
from services.convertible_bond import (
    get_market_temperature as cb_get_temperature,
    get_convertible_bond_list as cb_get_list,
    get_convertible_bond_signals as cb_get_signals
)
from services.lof_fund import (
    get_lof_list as lof_get_list,
    get_lof_opportunities as lof_get_opportunities,
    get_lof_market_summary as lof_get_summary
)
from services.hk_ipo import (
    get_hk_ipo_list as hk_get_list,
    get_hk_ipo_upcoming as hk_get_upcoming,
    get_hk_ipo_summary as hk_get_summary
)
import os
import traceback

app = Flask(__name__)
CORS(app)

USE_MOCK = os.environ.get('USE_MOCK', 'false').lower() == 'true'


# ==================== Mock数据回退函数 ====================

def mock_market_temperature():
    """Mock市场温度"""
    prices = [item['转债价格'] for item in CONVERTIBLE_BOND_LIST]
    premiums = [item['转股溢价率'] for item in CONVERTIBLE_BOND_LIST]
    double_lows = [item['双低'] for item in CONVERTIBLE_BOND_LIST]

    price_median = sorted(prices)[len(prices) // 2]
    premium_median = sorted(premiums)[len(premiums) // 2]
    double_low_median = sorted(double_lows)[len(double_lows) // 2]

    if double_low_median < 150:
        market_status = '偏低，可关注'
    elif double_low_median < 180:
        market_status = '合理，可适当关注'
    else:
        market_status = '偏高，需谨慎'

    return {
        'count': len(CONVERTIBLE_BOND_LIST),
        'price_min': min(prices),
        'price_max': max(prices),
        'price_median': round(price_median, 2),
        'premium_median': round(premium_median, 2),
        'double_low_median': round(double_low_median, 1),
        'market_status': market_status
    }


def mock_cb_signals():
    """Mock可转债信号"""
    data = CONVERTIBLE_BOND_LIST.copy()
    # 添加交易所标识
    for item in data:
        code = str(item.get('正股代码', ''))
        if code.startswith(('6', '5', '9', '11', '13')):
            item['交易所'] = '沪'
        elif code.startswith(('0', '1', '2', '3', '12')):
            item['交易所'] = '深'
        else:
            item['交易所'] = ''

    return {
        'double_low': sorted(data, key=lambda x: x['双低'])[:20],
        'force_redeem': [item for item in data if item['转股溢价率'] < 10 and 105 <= item['转债价格'] <= 140][:10],
        'discount': [item for item in data if item['转股溢价率'] < 0][:10],
        'down_revised': [item for item in data if item['转股溢价率'] > 50 and item['转债价格'] < 115][:10]
    }


def mock_lof_summary():
    """Mock LOF市场概览"""
    premiums = [item['溢价率'] for item in LOF_LIST]
    positive_count = sum(1 for p in premiums if p > 0)
    return {
        'count': len(LOF_LIST),
        'premium_avg': round(sum(premiums) / len(premiums), 2),
        'top_premium': max(premiums),
        'positive_count': positive_count,
        'positive_rate': round(positive_count / len(LOF_LIST) * 100, 1),
        'paused_count': sum(1 for item in LOF_LIST if item['申购状态'] == '暂停')
    }


def mock_hk_ipo_summary():
    """Mock港股IPO概览"""
    upcoming_count = sum(1 for item in HK_IPO_LIST if item['status'] == '申购中')
    recent_count = sum(1 for item in HK_IPO_LIST if item['status'] == '已上市')
    listed = [item for item in HK_IPO_LIST if item['status'] == '已上市']
    avg_return = sum(item.get('change_pct', 0) for item in listed) / max(recent_count, 1)
    return {
        'upcoming_count': upcoming_count,
        'recent_count': recent_count,
        'avg_return': round(avg_return, 1)
    }


# ==================== API路由 ====================

@app.route('/api/market/overview')
def market_overview():
    """市场概览"""
    try:
        # 可转债市场温度
        cb_temp = None
        if not USE_MOCK:
            cb_temp = cb_get_temperature()
        if not cb_temp:
            cb_temp = mock_market_temperature()

        # LOF市场概览
        lof_summary = None
        if not USE_MOCK:
            lof_summary = lof_get_summary()
        if not lof_summary:
            lof_summary = mock_lof_summary()

        # 港股IPO概览
        hk_summary = None
        if not USE_MOCK:
            hk_summary = hk_get_summary()
        if not hk_summary:
            hk_summary = mock_hk_ipo_summary()

        return jsonify({
            'success': True,
            'data': {
                'convertible_bond': cb_temp,
                'lof_fund': lof_summary,
                'hk_ipo': hk_summary,
                'market_sentiment': MARKET_SENTIMENT,
                'fund_flow': FUND_FLOW
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/convertible/list')
def convertible_list():
    """可转债列表"""
    try:
        if USE_MOCK:
            return jsonify({'success': True, 'data': CONVERTIBLE_BOND_LIST})

        data = cb_get_list()
        if not data:
            return jsonify({'success': True, 'data': CONVERTIBLE_BOND_LIST})
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'data': CONVERTIBLE_BOND_LIST})


@app.route('/api/convertible/signals')
def convertible_signals():
    """可转债信号"""
    try:
        if USE_MOCK:
            return jsonify({'success': True, 'data': mock_cb_signals()})

        data = cb_get_signals()
        if not data:
            return jsonify({'success': True, 'data': mock_cb_signals()})
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'data': mock_cb_signals()})


@app.route('/api/lof/list')
def lof_list():
    """LOF基金列表"""
    try:
        if USE_MOCK:
            return jsonify({'success': True, 'data': LOF_LIST})

        data = lof_get_list()
        if not data:
            return jsonify({'success': True, 'data': LOF_LIST})
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'data': LOF_LIST})


@app.route('/api/lof/opportunities')
def lof_opportunities():
    """LOF套利机会"""
    try:
        if USE_MOCK:
            premium = sorted(LOF_LIST, key=lambda x: x['溢价率'], reverse=True)[:20]
            discount = sorted(LOF_LIST, key=lambda x: x['溢价率'])[:20]
            return jsonify({'success': True, 'data': {'premium': premium, 'discount': discount}})

        data = lof_get_opportunities()
        if not data['premium'] and not data['discount']:
            premium = sorted(LOF_LIST, key=lambda x: x['溢价率'], reverse=True)[:20]
            discount = sorted(LOF_LIST, key=lambda x: x['溢价率'])[:20]
            data = {'premium': premium, 'discount': discount}
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/hkipo/list')
def hkipo_list():
    """港股IPO列表"""
    try:
        if USE_MOCK:
            return jsonify({'success': True, 'data': HK_IPO_LIST})

        data = hk_get_list()
        if not data:
            return jsonify({'success': True, 'data': HK_IPO_LIST})
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'data': HK_IPO_LIST})


@app.route('/api/hkipo/upcoming')
def hkipo_upcoming():
    """即将上市的港股IPO"""
    try:
        if USE_MOCK:
            return jsonify({'success': True, 'data': [item for item in HK_IPO_LIST if item['status'] == '申购中'][:10]})

        data = hk_get_upcoming()
        if not data:
            return jsonify({'success': True, 'data': [item for item in HK_IPO_LIST if item['status'] == '申购中'][:10]})
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/health')
def health():
    """健康检查"""
    return jsonify({
        'success': True,
        'data': {
            'status': 'ok',
            'use_mock': USE_MOCK,
            'akshare_available': not USE_MOCK
        }
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)