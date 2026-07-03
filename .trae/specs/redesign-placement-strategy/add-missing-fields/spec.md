# 配售列表补充资金/股数/规模字段 Spec

## Why

用户审查当前配售列表版面后，发现三个必要决策信息缺失、一个展示不足：

1. **正股价**：缺失。用户看列表时不点进详情不知道当前正股价格，无法判断买入成本。
2. **一手资金**（配1手需要的金额 = `sharesFor10 × stockPrice`）：缺失。用户需要在一行内看到"买多少股、花多少钱"，目前只展示股数不展示金额。
3. **沪市一手党最低手数**（约 0.6 手 = `ceil(sharesFor10 × 0.6)`）及其对应金额：缺失。笔记"一手党"策略是核心操作技巧，当前只通过一个布尔角标 `👋` 提示"存在"，不展示具体最低股数和金额。
4. **发行规模**：当前在次要信息行以灰色小字展示（20rpx），用户反映"没看到"——信息过小被忽略。

本次变更：不改变核心指标行（百元含权/安全垫/预估收益）的突出地位，仅在**信息代码行和次要行**中补全这些缺失的资金/股数字段。

## What Changes

### 前端 `index.js`
- **NEW** 在 `formatPendingItem` 中新增 4 个计算字段，不需要后端改：
  - `_costFor10LotsRaw` = `sharesFor10 × stockPrice`，用于排序
  - `costFor10Lots` = 格式化字符串（"N元"），展示一手所需资金
  - `_oneHandMinShares` = 沪市 `ceil(sharesFor10 × 0.6)`，非沪市 0
  - `oneHandMinCost` = `_oneHandMinShares × stockPrice`，格式化展示（"N≈N元"）

### 前端 `index.wxml`
- **MODIFIED** 代码行（code-row）：增加**正股价** + **当日涨跌**（两字段紧凑排列），让用户一眼看到买入成本
- **MODIFIED** 次要信息行（sub-row）：当前为"每股|配10张|规模|👋一手党"，改为：
  - 保留"每股N元"
  - "配1手"改为**配1手N股≈N元**（股数+金额）
  - 规模移至显眼位置并增加"亿"后接**评级**（若存在）
  - 沪市标的增加**"一手党最低N股≈N元"**（取代原来仅布尔标记）

### 前端 `index.wxss`
- **MODIFIED** 代码行中价格字段样式（突出显示而非灰色小字）
- **MODIFIED** 一手党资金信息样式（与普通次要信息区分，稍大字号）
- **REMOVED** 不再需要单独的 oneHandParty 布尔标签

### 排序条
- 不改变，保留现有"推荐/含权/安全垫/规模/涨幅"排序按钮

## Impact
- Affected code: `miniprogram/pages/convertible/index.js`、`index.wxml`、`index.wxss`
- 不改后端、不改 mock 数据
- 不改变其他 Tab 显示

## ADDED Requirements

### Requirement: 配售列表代码行增加正股价
配售列表代码行（code-row 区域）SHALL 在正股代码之后显示"正股价N元"和"当日涨跌N%"，使用略大于代码字号（24rpx），与股票代码灰色小字区分。

### Requirement: 配售列表一手资金展示
次要信息行 SHALL 将"配10张N股"改为"配1手N股≈N元"，其中金额 = `sharesFor10 × stockPrice`。

#### Scenario: 湖北宜化
- **WHEN** `sharesFor10=330`、`stockPrice=13.44`
- **THEN** 展示"配1手330股≈4435元"

### Requirement: 沪市一手党最低手数
沪市标的次要信息行 SHALL 展示"一手党最低N股≈N元"，其中股数 = `ceil(sharesFor10 × 0.6)`，金额 = 股数 × 股价。

#### Scenario: 沪市中汽股份
- **WHEN** `exchange='沪'`、`sharesFor10=1275`、`stockPrice=5.25`
- **THEN** 展示"一手党最低765股≈4016元"

#### Scenario: 深市标的
- **WHEN** `exchange='深'`
- **THEN** 不展示一手党信息（沪市特有策略）

### Requirement: 发行规模展示突出
代码行或次要信息行 SHALL 展示发行规模，字号不低于 22rpx（非 20rpx），避免被忽略。

## MODIFIED Requirements

### Requirement: 配售列表项信息分层（现有结构微调）
从当前三行（主行+核心指标行+次要信息行）调整为四行：

| 行 | 字段 |
|---|---|
| 主行 | 交易所 + 正股名 + 风险标签 + 登记日角标 |
| 条件行（原代码行扩展） | 正股代码 + ⭐**正股价N元** + 涨跌 + \| + 评级 + 进展 |
| 核心指标行 | 百元含权（高亮）\| 安全垫（颜色）\| 预估收益（高亮） |
| 资金信息行（原次要信息行扩展） | 每股N元 \| 配1手N股≈N元 \| 规模N亿 \| **一手党最低N≈N元(沪)** |
