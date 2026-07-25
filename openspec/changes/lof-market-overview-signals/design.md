# 设计

## 数据路径

摘要接口需要一个已验证的日频份额变动数据源。对于每条符合条件的记录：

```text
net_subscription_capital = max(net_share_change, 0) * NAV
account_count_lower_bound = ceil(net_subscription_capital / verified_per_account_limit)
investor_limit_lower_bound = ceil(net_subscription_capital / verified_per_investor_limit)
```

实现必须保留份额单位、份额日期、NAV（资产净值）日期、数据源 URL、获取时间、限额值、限额主体（`account` 或 `investor`）、适用渠道、适用份额类别，以及已排除非申购变动的记录。正向净份额变动是申购活动的下限代理值，而非申购总量。仅允许在单位兼容且最近已完成交易日相同的记录之间进行聚合。跨基金或跨日期时，它变为 `累计等效参与次数`；**绝不能**表示为去重后的账户数、投资者数或人数。

## API 契约

LOF 摘要响应将为 Web 总览暴露以下规范化字段：

- `溢价热点方向`：加权正溢价分类方向中的最高值。
- `昨日净申购资金（估）`：汇总资金，含数据源日期。
- `昨日净申购账户数下限`：仅限有已验证单账户限额的基金的汇总下限。
- `昨日净申购投资者限额下限`：单独的下限，仅在有明确单投资者限额时显示；它并非唯一人数。

每个字段都包含明确的不可用状态和数据源日期（在日频数据缺失时）。响应**绝不会**使用现有的 `lof_arbitrage` 模拟历史回退数据。

`hot_direction` 是可审查的证据组：`status` 为 `available` 时，响应必须同时包含 `name`、`method`、`weighted_premium`、`sample_count`、`constituents`、`unclassified_count`、`as_of`、`source` 和 `retrieved_at`。`constituents` 保留分类基金、分类依据及其纳入计算的溢价与成交额，供 Web 审查。`as_of` 来自纳入计算的有效行情日期；`source` 标识 LOF 主题分类表及其分类依据；`retrieved_at` 标识本次摘要生成时间。没有有效分类样本时，服务返回 `status: unavailable`、明确 `reason` 和未分类覆盖数，且不得返回命名方向。

## 待决产品决策

在实现之前，需选定已验证的 LOF 日频净份额变动数据源，并确认当无公开 API 可用时，明确受维护的日频数据源文件是否可接受。账户估算还需达成共识：它代表基于限额的下限估算，而非唯一人数统计。
