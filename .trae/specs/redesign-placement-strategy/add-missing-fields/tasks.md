# Tasks

## 前端 JS：formatPendingItem 新增计算字段

- [x] Task 1: `formatPendingItem` 新增 4 个字段
  - [x] `_costFor10LotsRaw = sharesFor10 * stockPrice`（原始值，供排序用）
  - [x] `costFor10Lots` = 格式化字符串如 `"4435元"`
  - [x] `_oneHandMinShares` = 沪市 `Math.ceil(sharesFor10 * 0.6)`，非沪市 0
  - [x] `oneHandMinCost` = 格式化如 `"765股≈4016元"`（仅沪市有值）
- [x] 验证: node -c 语法检查

## 前端 WXML：列表项信息行补全

- [x] Task 2: 条件行（原 code-row）扩展
  - [x] 在正股代码后增加 `<text class="code-price">N元</text>`（正股价）
  - [x] 正股价后增加涨跌值 `<text class="code-change">+N%</text>`
  - [x] 用 `|` 分隔符隔开与评级/进展

- [x] Task 3: 资金信息行（原 sub-row）改造
  - [x] `每股{{item.perShare}}` 保留
  - [x] `配10张{{item.sharesFor10}}` → `配1手{{item.sharesFor10}}≈{{item.costFor10Lots}}`
  - [x] `规模{{item.issueSize}}` 保留（字号提升）
  - [x] 沪市标的增加`一手党最低{{item._oneHandMinShares}}≈{{item.oneHandMinCost}}`

## 前端 WXSS：样式微调

- [x] Task 4: 条件行价格字段样式
  - [x] `.code-price`：24rpx、monospace、深色
  - [x] `.code-change`：22rpx、红绿

- [x] Task 5: 一手党资金信息样式
  - [x] 与普通 sub-info 区分，22rpx 暖色

## 验证

- [x] Task 6: node -c 语法检查通过
- [ ] Task 7: 手工检查：正股价、一手资金、一手党最低手数、发行规模四项均可见（需运行时验证）
