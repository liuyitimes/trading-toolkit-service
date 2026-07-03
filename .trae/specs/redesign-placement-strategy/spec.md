# 抢权配售策略版面重设计 Spec（最终版）

## Why

学习《抢权配售策略》笔记并实测集思录 pre_list API 真实返回字段后，核心发现：

1. **核心字段被忽略**：集思录 API 实际返回了 `cb_amount`（百元含权）、`record_price`（登记日基准价）、`ma20_price`（20日均价）三个关键策略字段，但 normalize 一个都没消费，前端去读不存在的 `stock_cash_ratio`，真实数据下百元含权/安全垫/预估收益全部显示 `--`。
2. **原算法口径错误**：百元含权集思录已按 `ration/record_price×100` 预计算，自算会因用实时价导致偏差。
3. **安全垫口径偏差**：当前公式未引入"预期溢价率"参数。
4. **数据不存在**：净利润增速、A股市值、近20日涨幅在 pre_list 接口无字段。

本次重设计原则：**所有策略参数基于已确认存在的数据字段**，数据不存在的能力降级或标注 TBD。

**用户最终确认的决策：**
- 所有策略 Tab 默认按"最优优先"排序（最有的排最前面）
- 每个 Tab 最多显示 15 条（各策略自身数量决定，估计不超过 15 条）
- 删除筛选快捷条、策略评分徽章、策略结论区——笔记没提，过度设计

## What Changes

### 后端
- **NEW** normalize 透传被忽略的三个字段：`cb_amount→stock_cash_ratio`、`record_price`、`ma20_price`
- **NEW** 补算 `expected_profit`（= 1000 × 0.2，默认）和 `safety_pad`（对齐笔记定义）
- **NEW** 补算 `stock_trend` = `(price - ma20_price) / ma20_price × 100`（近20日涨幅代理，UI 标注口径）
- **NEW** 补算 `risk_level`：安全垫<3%→high，3-8%→mid，>8%→low
- **NEW** 补算 `strategy_score`（0-100，仅用于后端导出/排序，前端不展示）
- **DECISION** 不自算百元含权，直接透传集思录 `cb_amount`
- **DECISION** 不实现净利润增速评分/筛选——数据源不存在

### 前端
- **MODIFIED** `formatPendingItem` 消费后端新字段，含兜底自算（后端无字段时前端用 `ration/price` 自算）
- **MODIFIED** 所有 Tab 默认按策略最优优先排序（通过 `normalizeSignals` 内 `_sortByBest` 实现）
- **MODIFIED** 所有 Tab 默认 limit ≤ 15 条（`applyData` + `switchTab` 中 `slice(0, 15)`）
- **NEW** 详情弹窗"预期溢价率"滑块可调（10%-50%，默认 20%），安全垫和预估收益实时重算
- **NEW** 配售列表分层结构：主行（正股名+风险标签+角标）+ 核心指标行（百元含权/安全垫/预估收益）+ 次要信息行（每股配售/配10张/规模/一手党）
- **NEW** 详情弹窗四分区：溢价率滑块 → 核心指标 → 正股风险（含 vs20日均价） → 发行信息
- **REMOVED** 筛选快捷条（高含权/高安全垫/小盘债按钮）
- **REMOVED** 列表评分徽章
- **REMOVED** 详情弹窗策略结论区

### 排序规则

| Tab | 排序依据 | 最优标准 |
|---|---|---|
| 配售 | 综合排序分（含权50%+安全垫30%+规模20%） | 分越高越靠前 |
| 双低 | `doubleLowNum` 升序 | 双低值越小越好 |
| 强赎 | `_forcePriceGap` 绝对值升序 | 越接近130%强赎线越靠前 |
| 折价 | `premiumNum` 升序 | 折价越大（溢价越负）越靠前 |
| 下修 | `_revisePriceGap` 绝对值升序 | 越接近85%下修触发线越靠前 |

### 数据
- 不改数据源，仅透传 + 补算

## Impact
- `cloudrun/services/convertible_bond.py`
- `cloudrun/mock_data.py`
- `miniprogram/pages/convertible/index.js`
- `miniprogram/pages/convertible/index.wxml`
- `miniprogram/pages/convertible/index.wxss`
