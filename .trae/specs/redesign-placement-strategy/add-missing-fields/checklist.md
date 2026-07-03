# Checklist

## formatPendingItem 新增字段
- [x] `formatPendingItem` 计算 `_costFor10LotsRaw`（原始金额）
- [x] `formatPendingItem` 计算 `costFor10Lots`（格式化"N元"）
- [x] `formatPendingItem` 计算 `_oneHandMinShares`（沪市 ceil(sharesFor10×0.6)）
- [x] `formatPendingItem` 计算 `oneHandMinCost`（格式化"N股≈N元"）
- [x] 深市标的 `_oneHandMinShares=0`，不展示

## WXML 条件行（原 code-row）
- [x] 正股代码后显示正股价N元
- [x] 正股价后显示当日涨跌
- [x] 字段紧凑排列，与评级/进展用分隔符隔开

## WXML 资金信息行（原 sub-row）
- [x] 每股N元保留
- [x] 配1手N股≈N元（含金额）
- [x] 规模N亿保留（字号提升）
- [x] 沪市标的追加一手党最低N股≈N元

## WXSS 样式
- [x] `.code-price`：24rpx、monospace、深色
- [x] `.code-change`：22rpx、红绿
- [x] 一手党信息22rpx暖色

## 验证
- [x] node -c 语法检查通过
- [ ] 正股价在列表中可见（需运行时验证）
- [ ] 一手资金（配1手≈N元）在列表中可见（需运行时验证）
- [ ] 一手党最低手数（沪市）在列表中可见（需运行时验证）
- [ ] 发行规模在列表中可见（非灰色极小字，需运行时验证）
- [ ] 其他 Tab 不受影响（需运行时验证）
