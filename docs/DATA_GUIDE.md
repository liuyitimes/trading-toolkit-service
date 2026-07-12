# 后端数据说明

状态：当前实现

## 请求链路

```text
Flask route
  -> DataSourceFactory / DirectSource
  -> domain service
  -> 新浪财经、东方财富、同花顺或乐咕公开接口
  -> cache / unified response
```

后端不再使用 akshare、efinance 或 tushare 作为运行时数据源。上游请求通过 `services/http_client.py` 管理会话、超时、重试和限流。

## 响应格式

业务接口使用统一包裹格式：

```json
{
  "success": true,
  "data": {},
  "meta": {
    "cached": false,
    "source": "direct",
    "update_time": "2026-07-12T00:00:00Z"
  }
}
```

对于使用陈旧缓存兜底的接口，响应还会包含 `data_status`：

| 值 | 含义 |
| --- | --- |
| `fresh` | 上游请求成功，或命中正在后台刷新的有效缓存 |
| `stale` | 回源失败，返回上次成功缓存 |
| `unavailable` | 回源失败且没有缓存 |

客户端必须把 `stale` 展示为数据延迟，不能将它标记为实时数据。

## 模块与字段

| 模块 | 主要接口 | 主要上游 |
| --- | --- | --- |
| 市场概览 | `/api/v1/market/overview`、`/market/sentiment`、`/market/fund-flow` | 新浪财经、乐咕、东方财富 |
| 可转债 | `/api/v1/convertible/*` | 新浪财经、东方财富 |
| LOF | `/api/v1/lof/*` | 东方财富 |
| 封闭式基金 | `/api/v1/closed-end/*` | 新浪财经、东方财富 |
| 港股 IPO | `/api/v1/hkipo/*` | 同花顺 |
| 用户数据 | `/api/v1/user/favorites` | 本地数据库或 PostgreSQL |

可转债配售接口使用 `cash_ratio` 表示百元含权；`stock_cash_ratio` 是独立的策略评分指标。完整口径见 [领域说明](domain/convertible-placement.md)。数据源、缓存和失败语义见 [数据源与缓存](architecture/data-sources.md)。
