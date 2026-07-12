# 可转债抢权配售字段

状态：当前实现

抢权配售决策至少需要同时看配售额度、持仓成本和价格风险。`cloudrun/services/convertible_bond.py` 提供原始字段和服务端计算，客户端负责展示与格式化。

## 核心字段

| 字段 | 含义 | 计算或来源 |
| --- | --- | --- |
| `per_share_allocation` | 每股可配可转债面额 | 东方财富发行数据 |
| `shares_for_10_lots` | 获配 1,000 元面额所需正股数 | `round(1000 / per_share_allocation)` |
| `stock_price` | 正股现价 | 新浪财经行情 |
| `cash_ratio` | 百元含权 | `per_share_allocation / stock_price * 100` |
| `safety_pad` | 预估收益对持仓成本的缓冲 | `expected_profit / (shares_for_10_lots * stock_price) * 100%` |
| `issue_size` | 可转债发行规模（亿元） | 东方财富发行数据 |
| `tradable_amount` | 预估首日可交易规模（亿元） | 发行规模，配售公告可用时再覆盖 |
| `strategy_score` | 配售评分 | 发行规模、首日可交易量和安全垫加权 |

预估收益当前使用固定的 20% 首日溢价假设：`expected_profit = 1000 * 0.2`。它是展示和比较用的假设，不构成投资建议。

## 百元含权的口径

百元含权应始终表示每投入 100 元正股市值可获配的可转债面额：

```text
cash_ratio = per_share_allocation / stock_price * 100
```

该指标与“正股总市值 / 转债发行规模”不同，不能混用。

## 旧字段兼容

`stock_cash_ratio` 保留为“正股总市值 / 转债发行规模”的策略评分指标，不能用于展示百元含权。客户端应优先消费 `cash_ratio`；旧客户端可在 `cash_ratio` 缺失时用 `per_share_allocation` 与 `stock_price` 自行计算。

Mock 与真实响应都必须保留上述字段语义，避免使用同名字段表达不同指标。
