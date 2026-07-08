# -*- coding: utf-8 -*-
"""LOF 套利资金预测服务 — 份额历史 + 明日预测 + 出逃风险评估

数据源（梯度降级）：
  1. 天天基金 fundgz 接口（实时净值）
  2. 东方财富 LOF 详情页（场内份额变化历史）
  3. 基金公司官网公告（巨潮资讯）
  4. 优雅降级：基于实时数据 + 历史趋势构造示例数据，source 标注 'mock'

核心计算：
  - 套利资金 = 当日份额变化 × 净值
  - 套利人数 = 套利资金 / 申购限额（仅限购基金）
  - 趋势系数 = 近 3 日均 change / 7 日均 change
  - 明日预测 = 最近一日 change × nav × 趋势系数
  - 出逃风险 = 明日预测 / 日均成交额 + 限购基金人数调整
"""

import json
import logging
import os
import random
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from services.http_client import sina_get, em_get
from utils.convert import safe_float

logger = logging.getLogger('trading_toolkit')

CST = timezone(timedelta(hours=8))

# 缓存目录
CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'lof_arbitrage'
)
CACHE_TTL = 30 * 60  # 30 分钟

# 数据源 URL
_TIANTIAN_FUND_URL = 'http://fundgz.1234567.com.cn/js/{code}.js'
_EASTMONEY_LOF_URL = 'https://fundf10.eastmoney.com/FundArchivesDatas.aspx'

# 历史数据窗口
HISTORY_DAYS = 7

# 申购限额默认值（基础数据缺失时的兜底）
DEFAULT_LIMIT_AMOUNTS = {
    '限100': 100,
    '限1000': 1000,
    '限5000': 5000,
    '限1万': 10000,
}


def _ensure_cache_dir():
    """确保缓存目录存在"""
    if not os.path.exists(CACHE_DIR):
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
        except Exception as e:
            logger.warning(f'创建缓存目录失败: {e}')


def _cache_path(code: str) -> str:
    """缓存文件路径"""
    return os.path.join(CACHE_DIR, f'{code}.json')


def _read_cache(code: str) -> Optional[dict]:
    """读取缓存，未过期则返回"""
    try:
        path = _cache_path(code)
        if not os.path.exists(path):
            return None
        mtime = os.path.getmtime(path)
        if time.time() - mtime > CACHE_TTL:
            return None
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f'读缓存失败 ({code}): {e}')
        return None


def _write_cache(code: str, data: dict):
    """写缓存"""
    try:
        _ensure_cache_dir()
        with open(_cache_path(code), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f'写缓存失败 ({code}): {e}')


def _fetch_tiantian_nav(code: str) -> Optional[float]:
    """从天天基金获取实时净值

    URL: http://fundgz.1234567.com.cn/js/{code}.js
    返回: jsonpgz({"fundcode":"161725","name":"...","jzrq":"2026-07-08","dwjz":"1.2345",...})
    """
    try:
        url = _TIANTIAN_FUND_URL.format(code=code)
        resp = sina_get(url, timeout=10)  # 用 sina session（不限流）
        if resp.status_code != 200:
            return None
        # 解析 jsonpgz({...})
        m = re.search(r'\((.+)\)', resp.text)
        if not m:
            return None
        data = json.loads(m.group(1))
        nav = safe_float(data.get('dwjz'))
        return nav if nav > 0 else None
    except Exception as e:
        logger.warning(f'[Tiantian] 获取 {code} 净值失败: {e}')
        return None


def _fetch_eastmoney_share_history(code: str) -> Optional[list]:
    """从东方财富 LOF 详情页获取场内份额变化

    实际生产环境东财的份额历史需要解析 FundArchivesDatas.aspx 的 HTML
    该接口对反爬敏感，且不同基金页面结构不一致。
    此处先尝试调用，失败回退到 mock。
    """
    try:
        # 东财 LOF 场内份额接口（不稳定，作为可选数据源）
        url = f'https://datacenter-web.eastmoney.com/api/data/v1/get'
        params = {
            'reportName': 'RPT_FUND_LOF_SHARE_CHANGE',
            'columns': 'ALL',
            'filter': f'(SECURITY_CODE="{code}")',
            'pageNumber': '1',
            'pageSize': str(HISTORY_DAYS),
            'sortColumns': 'TRADE_DATE',
            'sortTypes': '-1',
        }
        resp = em_get(url, params=params, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not data.get('result') or not data['result'].get('data'):
            return None
        return data['result']['data']
    except Exception as e:
        logger.warning(f'[EastMoney] 获取 {code} 份额历史失败: {e}')
        return None


def _generate_mock_history(code: str, current_amount: float = 0,
                            current_premium: float = 0) -> list:
    """生成示例历史数据（当真实数据不可用时的兜底）

    特点：
    - 基于当前成交额和溢价率动态生成
    - 反映"溢价越高 → 份额流入越快"的规律
    - 包含 7 日数据 + 略微随机波动
    - 必须显式标注 source='mock'
    """
    base_amount = current_amount if current_amount > 0 else 100  # 万元
    base_inflow = base_amount * 0.05  # 假设日均 5% 的资金流入

    # 溢价率越高，流入越多
    premium_factor = max(1.0, current_premium / 5.0) if current_premium > 0 else 1.0

    history = []
    today = datetime.now(CST).date()
    # 模拟最近 8 天的份额数据（第 8 天为基线）
    cumulative = base_amount * 100  # 累计场内份额（万元单位）

    for i in range(HISTORY_DAYS + 1, 0, -1):
        date = today - timedelta(days=i - 1)
        if i == HISTORY_DAYS + 1:
            # 第一天：基线，无变化
            history.append({
                'date': date.isoformat(),
                'share': round(cumulative, 2),
                'change': 0.0,
                'amount': round(base_amount * random.uniform(0.7, 1.0), 2),
                'nav': 1.0,
            })
            continue
        # 当日变化
        if i <= 3:  # 最近 3 天：高溢价期，流入加速
            daily_inflow = base_inflow * premium_factor * random.uniform(0.8, 1.5)
        else:  # 4-7 天前：溢价初期，流入较缓
            daily_inflow = base_inflow * 0.6 * random.uniform(0.5, 1.2)
        cumulative += daily_inflow
        history.append({
            'date': date.isoformat(),
            'share': round(cumulative, 2),
            'change': round(daily_inflow, 2),
            'amount': round(base_amount * random.uniform(0.6, 1.3), 2),
            'nav': 1.0,
        })

    return history


def fetch_share_history(code: str, current_amount: float = 0,
                        current_premium: float = 0) -> dict:
    """获取 LOF 基金近 7 日场内份额变化

    Args:
        code: 基金代码
        current_amount: 当前成交额（万元），用于 mock 兜底
        current_premium: 当前溢价率（%），用于 mock 兜底

    Returns:
        {
            'code': str,
            'history': [{date, share, change, amount, nav}],
            'source': 'tiantian' | 'eastmoney' | 'mock' | 'unavailable',
            'fetched_at': iso8601
        }
    """
    # 1. 查缓存
    cached = _read_cache(code)
    if cached:
        return cached

    # 2. 尝试天天基金（仅获取最新净值）
    nav = _fetch_tiantian_nav(code)
    if nav:
        logger.info(f'[LOFArb] 天天基金获取 {code} 净值成功: {nav}')

    # 3. 尝试东方财富份额历史
    em_history = _fetch_eastmoney_share_history(code)
    if em_history:
        try:
            history = []
            for row in em_history:
                history.append({
                    'date': str(row.get('TRADE_DATE', '')),
                    'share': safe_float(row.get('INNER_VOL', 0)),
                    'change': safe_float(row.get('CHANGE_VOL', 0)),
                    'amount': safe_float(row.get('AMOUNT', 0)),
                    'nav': safe_float(row.get('NAV', nav or 1.0)),
                })
            if len(history) >= 3:
                result = {
                    'code': code,
                    'history': history,
                    'source': 'eastmoney',
                    'fetched_at': datetime.now(CST).isoformat(),
                }
                _write_cache(code, result)
                logger.info(f'[LOFArb] 东财份额历史 {code}: {len(history)} 天')
                return result
        except Exception as e:
            logger.warning(f'[EastMoney] 解析 {code} 失败: {e}')

    # 4. 降级到 mock（基于实时数据构造）
    history = _generate_mock_history(code, current_amount, current_premium)
    if nav:
        # 用真实净值填充 nav 字段
        for h in history:
            h['nav'] = nav

    result = {
        'code': code,
        'history': history,
        'source': 'mock' if not em_history else 'tiantian+mock',
        'fetched_at': datetime.now(CST).isoformat(),
        'note': '示例数据：当前数据源未提供场内份额历史，基于当前溢价/成交额构造',
    }
    _write_cache(code, result)
    logger.info(f'[LOFArb] {code} 降级到 mock 数据（current_premium={current_premium}%）')
    return result


def calc_daily_fund(change: float, nav: float) -> float:
    """计算当日套利资金（万元）"""
    if change <= 0 or nav <= 0:
        return 0.0
    return round(change * nav, 2)


def estimate_people(fund_amount: float, limit_amount: float) -> Optional[int]:
    """反推套利人数（仅限购基金）"""
    if limit_amount <= 0 or fund_amount <= 0:
        return None
    return int(fund_amount * 10000 / limit_amount)  # fund_amount 是万元，转元


def calc_trend_status(history: list) -> str:
    """识别趋势状态（加速/平稳/减速）

    比较最近 1 日 change vs 前 2 日均 change
    """
    if len(history) < 3:
        return 'unknown'
    recent = [h['change'] for h in history[-3:] if h.get('change', 0) > 0]
    if len(recent) < 3:
        return 'unknown'
    last = recent[-1]
    prev_avg = sum(recent[:-1]) / len(recent[:-1])
    if prev_avg <= 0:
        return 'unknown'
    ratio = last / prev_avg
    if ratio >= 1.5:
        return 'accelerating'  # 加速
    if ratio <= 0.5:
        return 'decelerating'  # 减速
    return 'stable'  # 平稳


def predict_tomorrow(history: list) -> dict:
    """预测明日套利规模

    Returns:
        {
            'predicted_fund': float | None,  # 万元
            'predicted_people': int | None,
            'trend_ratio': float,
            'trend_status': str,
            'data_sufficient': bool,
        }
    """
    positive_changes = [h['change'] for h in history if h.get('change', 0) > 0]
    if len(positive_changes) < 3:
        return {
            'predicted_fund': None,
            'predicted_people': None,
            'trend_ratio': None,
            'trend_status': 'unknown',
            'data_sufficient': False,
        }

    last = history[-1]
    nav = last.get('nav', 1.0) or 1.0
    last_change = last.get('change', 0) or 0

    # 趋势系数
    recent_3 = positive_changes[-3:]
    last_3_avg = sum(recent_3) / len(recent_3)
    all_avg = sum(positive_changes) / len(positive_changes)
    trend_ratio = round(last_3_avg / all_avg, 3) if all_avg > 0 else 1.0

    # 预测
    predicted_fund = round(last_change * nav * trend_ratio, 2) if last_change > 0 else 0.0
    trend_status = calc_trend_status(history)

    return {
        'predicted_fund': predicted_fund,
        'predicted_people': None,  # 由调用方根据 limit_amount 填入
        'trend_ratio': trend_ratio,
        'trend_status': trend_status,
        'data_sufficient': True,
    }


def assess_escape_risk(predicted_fund: Optional[float], avg_daily_amount: float,
                        limit_status: str = '不限',
                        limit_amount: float = 0) -> dict:
    """评估 T+2 出逃风险

    Returns:
        {
            'coverage_ratio': float,
            'risk_level': 'low' | 'medium' | 'high' | 'extreme' | 'unknown',
            'risk_label': str,
            'description': str,
        }
    """
    if predicted_fund is None:
        return {
            'coverage_ratio': None,
            'risk_level': 'unknown',
            'risk_label': '数据不足',
            'description': '历史数据不足，无法评估出逃风险',
        }

    # 覆盖率（避免除 0）
    if avg_daily_amount <= 0:
        coverage = 0.0
    else:
        coverage = round(predicted_fund / avg_daily_amount, 3)

    # 限购基金一拖六调整
    effective_coverage = coverage
    if limit_status == '限100' and limit_amount > 0:
        # 限购基金：实际出逃压力 = 人数 / 6 账户分摊
        predicted_people = int(predicted_fund * 10000 / limit_amount)
        effective_people = predicted_people / 6
        # 用"有效人数/日均成交笔数"作为流动性指标（粗略估算）
        # 假设每笔 100 元，则日均成交笔数 ≈ avg_daily_amount * 10000 / 100
        # 调整为 effective_people / (avg_daily_amount * 100) 这个系数
        if avg_daily_amount > 0:
            effective_coverage = round(effective_people / (avg_daily_amount * 100), 3)

    # 风险等级
    if effective_coverage < 0.3:
        risk_level = 'low'
        risk_label = '低风险'
        description = '流动性充足，可顺利出逃'
    elif effective_coverage < 0.8:
        risk_level = 'medium'
        risk_label = '中风险'
        description = '流动性一般，需关注 T+2 出逃表现'
    elif effective_coverage < 1.5:
        risk_level = 'high'
        risk_label = '高风险'
        description = '流动性紧张，可能无法顺利出逃'
    else:
        risk_level = 'extreme'
        risk_label = '极端风险'
        description = '流动性枯竭，强烈建议规避'

    return {
        'coverage_ratio': effective_coverage,
        'risk_level': risk_level,
        'risk_label': risk_label,
        'description': description,
    }


def calc_7d_summary(history: list, limit_status: str = '不限',
                     limit_amount: float = 0) -> dict:
    """汇总 7 日数据 + 预测 + 风险

    Returns:
        {
            'history': [...],  # 原 history 加上 arbitrage_fund 字段
            'cumulative_fund': float,
            'cumulative_people': int | None,
            'avg_daily_amount': float,
            'predicted': {predicted_fund, predicted_people, trend_ratio, trend_status},
            'risk': {coverage_ratio, risk_level, risk_label, description},
        }
    """
    # 1. 给 history 每项加 arbitrage_fund 和 arbitrage_people
    enriched = []
    cumulative_fund = 0.0
    cumulative_people = 0

    for h in history:
        change = h.get('change', 0) or 0
        nav = h.get('nav', 1.0) or 1.0
        daily_fund = calc_daily_fund(change, nav)
        daily_people = estimate_people(daily_fund, limit_amount) if limit_status.startswith('限') else None

        enriched.append({
            **h,
            'arbitrage_fund': daily_fund,
            'arbitrage_people': daily_people,
        })

        if daily_fund > 0:
            cumulative_fund += daily_fund
        if daily_people:
            cumulative_people += daily_people

    # 2. 日均成交额
    amounts = [h.get('amount', 0) or 0 for h in history]
    avg_daily_amount = round(sum(amounts) / len(amounts), 2) if amounts else 0.0

    # 3. 预测
    predicted = predict_tomorrow(history)
    # 填入人数
    if predicted.get('predicted_fund') and limit_amount > 0 and limit_status.startswith('限'):
        predicted['predicted_people'] = estimate_people(
            predicted['predicted_fund'], limit_amount
        )

    # 4. 风险评估
    risk = assess_escape_risk(
        predicted.get('predicted_fund'),
        avg_daily_amount,
        limit_status,
        limit_amount,
    )

    return {
        'history': enriched,
        'cumulative_fund': round(cumulative_fund, 2),
        'cumulative_people': cumulative_people if limit_status.startswith('限') else None,
        'avg_daily_amount': avg_daily_amount,
        'predicted': predicted,
        'risk': risk,
    }


def get_arbitrage_prediction(code: str, current_amount: float = 0,
                              current_premium: float = 0,
                              limit_status: str = '不限',
                              limit_amount: float = 0) -> dict:
    """获取 LOF 套利资金预测（主入口）

    Args:
        code: 基金代码
        current_amount: 当前成交额（万元）
        current_premium: 当前溢价率（%）
        limit_status: 申购状态（不限/限100/限1000/暂停）
        limit_amount: 申购限额（元）

    Returns:
        {
            'code': str,
            'data_source': str,  # 'tiantian' | 'eastmoney' | 'mock'
            'limit_status': str,
            'limit_amount': float,
            'cumulative_fund': float,
            'cumulative_people': int | None,
            'avg_daily_amount': float,
            'predicted_fund': float | None,
            'predicted_people': int | None,
            'trend_ratio': float | None,
            'trend_status': str,
            'coverage_ratio': float | None,
            'risk_level': str,
            'risk_label': str,
            'description': str,
            'history': [{date, share, change, amount, nav, arbitrage_fund, arbitrage_people}],
            'fetched_at': iso8601,
            'note': str | None,  # 当 source 为 mock 时给出说明
        }
    """
    # 1. 获取历史数据
    raw = fetch_share_history(code, current_amount, current_premium)
    history = raw.get('history', [])
    source = raw.get('source', 'unavailable')
    note = raw.get('note')

    # 2. 解析 limit_amount
    if limit_status in DEFAULT_LIMIT_AMOUNTS:
        limit_amount = DEFAULT_LIMIT_AMOUNTS[limit_status]
    elif limit_status == '不限' or limit_status == '暂停':
        limit_amount = 0

    # 3. 汇总计算
    summary = calc_7d_summary(history, limit_status, limit_amount)

    # 4. 组装返回
    return {
        'code': code,
        'data_source': source,
        'limit_status': limit_status,
        'limit_amount': limit_amount,
        'cumulative_fund': summary['cumulative_fund'],
        'cumulative_people': summary['cumulative_people'],
        'avg_daily_amount': summary['avg_daily_amount'],
        'predicted_fund': summary['predicted'].get('predicted_fund'),
        'predicted_people': summary['predicted'].get('predicted_people'),
        'trend_ratio': summary['predicted'].get('trend_ratio'),
        'trend_status': summary['predicted'].get('trend_status', 'unknown'),
        'data_sufficient': summary['predicted'].get('data_sufficient', False),
        'coverage_ratio': summary['risk'].get('coverage_ratio'),
        'risk_level': summary['risk'].get('risk_level'),
        'risk_label': summary['risk'].get('risk_label'),
        'description': summary['risk'].get('description'),
        'history': summary['history'],
        'fetched_at': raw.get('fetched_at'),
        'note': note,
    }
