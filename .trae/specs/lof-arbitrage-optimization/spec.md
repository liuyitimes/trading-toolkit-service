# LOF 套利页面深度改造 Spec

## Why

当前 LOF 套利页面仅展示毛溢价率，缺少套利者决定是否出手的关键信息（净溢价、成交额、限购额度、费用成本）。通过学习 LOF 套利知识体系，将页面从"列表页"升级为"套利决策辅助工具"。

## What Changes

### 1. 新增"成交额"列（流动性指标）
后端已返回 `成交量`、`成交额` 字段，前端未使用。新增列展示当日成交额，附加值高低色标记：
- 成交额 > 1000 万 → 绿色（流动性好）
- 100万 - 1000万 → 黄色（可关注）
- < 100 万 → 红色（流动性风险）
- 列位置：替换"连续天数"列右侧

### 2. 净溢价率计算
根据申购状态计算套利成本，显示"净溢价"：
- `含申购费`: 溢价率 - 0.15%（当前mock均"不限"）
- `暂停申购`: 无套利空间，显示"N/A"
- `限购`: 与不限购相同计算，加"限购"标记
- **显示规则**：仅在溢价Tab下展示；折价Tab下展示净溢价(负) vs 赎回费

### 3. 限购额度展示
- "限100" 标签改为 `限100元` 完整格式
- 行内显示 `限额: 100元`，支持多账户（一拖六）

### 4. 可套利标记
行内条件渲染标签：
- 溢价 > 3% + 成交额 > 100万 → `🟢 可套利` 绿色标签
- 连续溢价 > 5天 → `📈 溢价持续` 蓝色标签
- 成交额 < 10万 → `⚠️ 流动性差` 黄色警告标签

### 5. 行情详情弹窗（仿配售弹窗）
点击行弹出详情，分 4 个区域：
1. **基金概要**: 名称/代码/交易所/申购状态/限额
2. **价格与净值**: 当前价/估值(IOPV)/偏离/溢价率/净溢价
3. **流动性数据**: 成交额/成交量/连续溢价天数
4. **操作建议**: 根据溢价率+成交额+限购状态给出文字建议

### 6. 顶部概览增强
增加"可套利标的"计数（溢价>3%+成交额>100万）

### 7. 后端数据透传
`formatLofItem()` 透传 `volume`、`amount`、`limit_amount` 字段到前端

## Impact
- Affected specs: `frontend-optimization`（已归档，不冲突）
- Affected code:
  - `miniprogram/pages/lof/index.js` — formatLofItem + 净溢价 + 弹窗
  - `miniprogram/pages/lof/index.wxml` — 表头+行+弹窗
  - `miniprogram/pages/lof/index.wxss` — 新列+标签+弹窗

## ADDED Requirements

### Requirement 1: 成交额列
The system SHALL display the daily trading amount in the LOF list.

#### Scenario: Normal display
- **WHEN** LOF list loads and `amount` > 0
- **THEN** show `X.XX亿` or `XXX万` format with color-coded background

#### Scenario: No data
- **WHEN** `amount` is 0 or null
- **THEN** show `--`

### Requirement 2: 净溢价
The system SHALL calculate net premium = premium - subscription fee - commission.

#### Scenario: Premium arbitrage (不限购)
- **WHEN** premium > 0 and limit_status = '不限'
- **THEN** net_premium = premium - 0.15

#### Scenario: Paused
- **WHEN** limit_status = '暂停'
- **THEN** show `N/A` (无法申购)

### Requirement 3: 详情弹窗
The system SHALL provide a detail popup when tapping a row.

#### Scenario: Tap row
- **WHEN** user taps any LOF row
- **THEN** popup shows fund summary, price/NAV data, liquidity data, and arbitrage advice

### Requirement 4: 可套利标记
The system SHALL auto-tag rows meeting arbitrage criteria.

#### Scenario: Tradeable arbitrage
- **WHEN** premium >= 3 AND amount >= 100万 AND limit_status != '暂停'
- **THEN** show `可套利` green tag

#### Scenario: Poor liquidity
- **WHEN** amount < 10万 or amount is null
- **THEN** show `流动性差` warning tag

## MODIFIED Requirements
None.

## REMOVED Requirements
None.
