# -*- coding: utf-8 -*-
"""HTTP 客户端基础设施 — 按上游域分组 session，内置限流 / 重试 / 结构化日志。

设计依据：ADR-002「按上游域分组 session，移除 CircuitBreaker」。
每个上游域（sina/em/ths/legu/jsl）拥有独立的：
  - requests.Session（Keep-Alive 连接复用）
  - HTTPAdapter + Retry（429/5xx 指数退避，仅 GET）
  - 默认 UA / Referer
  - 独立的串行限流计数器（仅 em 域强制 ≥1s 间隔 + 抖动）

对外暴露：
  - sina_get / em_get / ths_get / legu_get / jsl_post
  - sina_session / em_session / ths_session / legu_session / jsl_session
"""

import logging
import random
import threading
import time

import requests
from requests.adapters import HTTPAdapter

try:
    from urllib3.util.retry import Retry
except ImportError:  # pragma: no cover - 老版本降级
    Retry = None

logger = logging.getLogger('trading_toolkit')

# ==================== 通用配置 ====================

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# 东财防封阈值（社区实测 2026-05）：>5 次/秒 或 单 IP 并发 ≥10 触发风控。
# 因此 em 域强制串行限流：最小间隔 1.0s + 随机抖动 0.1~0.5s。
EM_MIN_INTERVAL = 1.0
_em_last_call = [0.0]  # 模块级上次请求时间戳，list 便于闭包修改
_em_lock = threading.Lock()  # 保证多线程下 em_get 仍串行限流


# ==================== Session 构造 ====================


def _make_session(ua: str = _DEFAULT_UA, referer: str = '',
                  status_forcelist=None, total_retries: int = 3,
                  backoff_factor: float = 0.6):
    """构造带重试策略的 requests.Session。

    - status_forcelist: 默认 [429, 500, 502, 503, 504]（不含 403，403 是风控信号不重试）
    - backoff_factor: 指数退避因子（urllib3 标准）
    """
    session = requests.Session()
    session.trust_env = False  # 不读取系统代理，直连上游
    session.headers.update({
        "User-Agent": ua,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    if referer:
        session.headers.update({"Referer": referer})

    if Retry is not None:
        retry_kwargs = dict(
            total=total_retries,
            connect=total_retries,
            read=total_retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist or [429, 500, 502, 503, 504],
        )
        # 兼容新老 urllib3：新版用 allowed_methods，老版用 method_whitelist
        try:
            retry = Retry(allowed_methods=["GET"], **retry_kwargs)
        except TypeError:  # pragma: no cover
            retry = Retry(method_whitelist=["GET"], **retry_kwargs)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
    return session


# ==================== 按上游域分组的 Session ====================

sina_session = _make_session(
    referer="https://vip.stock.finance.sina.com.cn/",
)

em_session = _make_session(
    referer="https://data.eastmoney.com/",
)

ths_session = _make_session(
    ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    referer="https://basic.10jqka.com.cn/",
)

legu_session = _make_session(
    referer="https://legulegu.com/",
)

jsl_session = _make_session(
    ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    referer="https://www.jisilu.cn/",
)

cninfo_session = _make_session(
    ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    referer="http://www.cninfo.com.cn/new/disclosure",
)
cninfo_session.headers.update({
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/plain, */*",
})


# ==================== 结构化日志 ====================


def _log_request(domain: str, url: str, status_code: int,
                 start_ts: float, err: str = ''):
    """统一记录 HTTP 请求日志（JSON 结构化）。

    避免记录完整 URL 查询串（含 token 等），只记录域名 + 路径前缀。
    """
    elapsed_ms = int((time.time() - start_ts) * 1000)
    # 截取 path 部分，去除查询参数
    path = url.split('?')[0]
    # 仅保留域名 + 前 80 字符路径，避免日志过长
    if len(path) > 80:
        path = path[:80] + '...'
    extra = {
        'domain': domain,
        'path': path,
        'status': status_code,
        'elapsed_ms': elapsed_ms,
    }
    if err:
        extra['error'] = err
        logger.warning(f'[HTTP] {domain} {status_code} {elapsed_ms}ms {err}', extra=extra)
    else:
        logger.info(f'[HTTP] {domain} {status_code} {elapsed_ms}ms', extra=extra)


# ==================== 对外暴露的请求函数 ====================


def em_get(url, params=None, headers=None, timeout=15, **kwargs):
    """东财统一请求入口：自动串行限流（≥1s + 抖动）+ 复用 em_session。

    所有 eastmoney.com 接口都应通过它请求，避免高频被封 IP。
    批量场景可临时调大 EM_MIN_INTERVAL（模块级变量）。
    多线程下通过 _em_lock 保证仍串行限流。
    """
    with _em_lock:
        wait = EM_MIN_INTERVAL - (time.time() - _em_last_call[0])
        if wait > 0:
            time.sleep(wait + random.uniform(0.1, 0.5))
    start = time.time()
    try:
        resp = em_session.get(url, params=params, headers=headers,
                              timeout=timeout, **kwargs)
        _log_request('em', url, resp.status_code, start)
        return resp
    except Exception as e:
        _log_request('em', url, -1, start, str(e))
        raise
    finally:
        with _em_lock:
            _em_last_call[0] = time.time()


def sina_get(url, params=None, headers=None, timeout=15, **kwargs):
    """新浪财经 HTTP GET，复用 sina_session。"""
    start = time.time()
    try:
        resp = sina_session.get(url, params=params, headers=headers,
                                timeout=timeout, **kwargs)
        _log_request('sina', url, resp.status_code, start)
        return resp
    except Exception as e:
        _log_request('sina', url, -1, start, str(e))
        raise


def ths_get(url, params=None, headers=None, timeout=15, **kwargs):
    """同花顺 HTTP GET，复用 ths_session。"""
    start = time.time()
    try:
        resp = ths_session.get(url, params=params, headers=headers,
                               timeout=timeout, **kwargs)
        _log_request('ths', url, resp.status_code, start)
        return resp
    except Exception as e:
        _log_request('ths', url, -1, start, str(e))
        raise


def legu_get(url, params=None, headers=None, timeout=15, **kwargs):
    """乐股网 HTTP GET，复用 legu_session。"""
    start = time.time()
    try:
        resp = legu_session.get(url, params=params, headers=headers,
                                timeout=timeout, **kwargs)
        _log_request('legu', url, resp.status_code, start)
        return resp
    except Exception as e:
        _log_request('legu', url, -1, start, str(e))
        raise


def jsl_post(url, data=None, headers=None, timeout=15, **kwargs):
    """集思录 HTTP POST，复用 jsl_session。"""
    start = time.time()
    try:
        resp = jsl_session.post(url, data=data, headers=headers,
                                timeout=timeout, **kwargs)
        _log_request('jsl', url, resp.status_code, start)
        return resp
    except Exception as e:
        _log_request('jsl', url, -1, start, str(e))
        raise


def cninfo_post(url, data=None, headers=None, timeout=15, **kwargs):
    """巨潮资讯 HTTP POST，复用 cninfo_session。"""
    start = time.time()
    try:
        resp = cninfo_session.post(url, data=data, headers=headers,
                                   timeout=timeout, **kwargs)
        _log_request('cninfo', url, resp.status_code, start)
        return resp
    except Exception as e:
        _log_request('cninfo', url, -1, start, str(e))
        raise


def cninfo_get(url, params=None, headers=None, timeout=15, **kwargs):
    """巨潮资讯 HTTP GET，复用 cninfo_session。"""
    start = time.time()
    try:
        resp = cninfo_session.get(url, params=params, headers=headers,
                                  timeout=timeout, **kwargs)
        _log_request('cninfo', url, resp.status_code, start)
        return resp
    except Exception as e:
        _log_request('cninfo', url, -1, start, str(e))
        raise
