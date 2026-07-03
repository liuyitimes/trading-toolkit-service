# Checklist

## 后端
- [x] normalize 返回字典含 stock_cash_ratio（透传 cb_amount）
- [x] normalize 返回字典含 record_price、ma20_price
- [x] normalize 返回字典含 expected_profit（默认 200 元）
- [x] normalize 返回字典含 safety_pad，公式 expected_profit/(shares×price)×100
- [x] normalize 返回字典含 stock_trend，公式 (price-ma20_price)/ma20_price×100
- [x] normalize 返回字典含 strategy_score（0-100）
- [x] normalize 返回字典含 risk_level（high/mid/low），阈值 3%/8%
- [x] 不自算百元含权（直接用 cb_amount）
- [x] mock_data 同步含全部新字段

## 前端：兜底与消费
- [x] cashRatio 读 `item.stock_cash_ratio`，保留兜底自算
- [x] formatPendingItem 消费 risk_level/expected_profit/stock_trend/record_price/ma20_price
- [x] formatBondItem 计算 _forcePriceGap / _revisePriceGap 原始值

## 前端：排序（所有 Tab 最优优先）
- [x] `_sortByBest` 方法按 tabKey 分派不同排序标准
- [x] normalizeSignals 每个字段列表排序后用 `_sortByBest`
- [x] applyData 中非 placement Tab `slice(0, 15)` 限制条数
- [x] switchTab 中非 placement Tab `slice(0, 15)` 限制条数
- [x] applyData 中 placement 按 `_compositeRankRaw` 降序排列
- [x] switchTab 中 placement 重置时按 composite 排序

## 前端：版面
- [x] 删除筛选条（WXML + JS data + 方法 + WXSS）
- [x] 删除评分徽章（WXML + WXSS）
- [x] 删除详情弹窗策略结论区（WXML + WXSS）
- [x] 配售列表主行含：交易所+正股名+风险标签+角标
- [x] 配售列表核心指标行含：百元含权+安全垫+预估收益（高亮）
- [x] 配售列表次要信息行含：每股配售+配10张+规模+一手党（灰色小字）
- [x] 排序条含"推荐"按钮（默认激活，对应 composite）
- [x] 详情弹窗含溢价率滑块（10%-50%），调整实时重算
- [x] 详情弹窗四分区顺序：滑块→核心指标→正股风险→发行信息
- [x] 正股风险区标注"vs20日均价"口径

## 验证
- [x] node -c index.js 语法检查通过
- [x] python py_compile convertible_bond.py 通过
- [x] python py_compile mock_data.py 通过
- [x] 后端函数单元测试（评分/风险/安全垫/趋势计算正确）
