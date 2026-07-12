# 数据源与缓存

状态：当前实现

## 架构

`cloudrun` 使用 Flask 提供 API。请求经 `services.factory.DataSourceFactory` 进入唯一的 `DirectSource`，再由领域服务通过 `services.http_client` 直连公开 HTTP 上游。`get_with_fallback()` 保留仅为兼容现有路由调用；它不再表示多数据源降级链。

```text
Flask route
  -> DataSourceFactory (DirectSource)
  -> domain service
  -> http_client (session, retry, timeout, upstream-specific rate limit)
  -> upstream HTTP API
```

当前不依赖 `akshare`、`efinance` 或 `tushare`。不要在新功能中重新引入这些封装作为隐式备用数据源。

## 上游分工

| 领域 | 主要上游 | 代码入口 |
| --- | --- | --- |
| 可转债行情、正股行情 | 新浪财经、东方财富 | `services/convertible_bond.py` |
| LOF 数据 | 东方财富 | `services/lof_fund.py` |
| 封闭式基金 | 新浪财经、东方财富净值 | `services/closed_end.py` |
| 港股 IPO | 同花顺 | `services/hk_ipo.py` |
| 市场情绪、资金流向 | 新浪财经、乐咕、东方财富 | `services/direct_source.py` |

所有新增上游请求必须经过 `sina_get`、`em_get`、`ths_get`、`legu_get` 等封装入口，而不是直接调用 `requests`。东方财富请求由 `em_get` 串行限流，以降低触发上游限制的概率。

## 缓存与状态

`services.cache.fetch_with_stale_fallback()` 为需要明确失败语义的接口返回 `(data, data_status)`：

| `data_status` | 含义 | 前端行为 |
| --- | --- | --- |
| `fresh` | 本次数据来自成功回源，或在有效缓存命中时正在后台刷新 | 正常显示 |
| `stale` | 强制回源失败，返回上次成功缓存 | 显示“数据延迟”提示 |
| `unavailable` | 回源失败且没有可用缓存 | 显示不可用状态，不以 Mock 数据冒充实时数据 |

普通 SWR 请求会在缓存命中时立即返回，并在后台刷新。数据展示层必须保留来源、更新时间及 `data_status`，不得静默将陈旧数据描述为实时行情。

## 变更检查

1. 新增数据端点时，明确其上游、超时和缓存 TTL。
2. 上游异常时，验证 `fresh`、`stale`、`unavailable` 三种返回。
3. 不将随机值、哈希值或未标记 Mock 值作为真实字段返回。
4. 变更接口字段后，同步更新 [数据说明](../DATA_GUIDE.md)。
