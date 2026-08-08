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
| `shareholder_amount` | 原股东优先配售合计（亿元） | 巨潮官方发行结果/优先配售公告；未获取时为 null |
| `shareholder_ratio` | 原股东优先配售率（%） | 已解析公告金额 ÷ 发行规模；未获取金额时为 null |
| `tradable_amount` | 首日可交易规模（亿元） | 发行规模 − 原股东优先配售合计；公告缺失时为 null |
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

## 公告范围与缺失处理

“股东配售部分”统一采用公告披露的原股东优先配售合计，不尝试拆分大股东或实际控制人份额，也不根据锁定期推断额外扣减。公告同步在配债快照后台刷新中执行；用户读取只返回本地快照。

公告发布前无法可靠取得股东优先配售量是已知数据缺口。公告只有比例、无法解析金额时同样按缺口处理，不能用比例孤立推算。此时相关字段为 `null`，状态为 `unavailable`，原因写入 `placement_data_reason`，前端显示 `--`。后续若出现新的公告来源或更细锁定期数据，须在相关开发开始前重新讨论口径。
