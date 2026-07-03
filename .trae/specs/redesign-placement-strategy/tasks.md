# Tasks

## 后端

- [x] Task 1: normalize 透传被忽略的三个集思录字段（cb_amount→stock_cash_ratio、record_price、ma20_price）
- [x] Task 2: 补算 expected_profit、safety_pad、stock_trend
- [x] Task 3: 新增 _calc_strategy_score / _get_risk_level / DEFAULT_PREMIUM_RATE，返回 strategy_score 和 risk_level
- [x] Task 4: mock_data.py 同步添加新字段

## 前端：formatPendingItem

- [x] Task 5: `cashRatio` 优先读 `stock_cash_ratio`（cb_amount），兜底 `per_share/stock_price*100`
- [x] Task 6: 消费 risk_level/expected_profit/stock_trend/record_price/ma20_price 字段
- [x] Task 7: 计算 `_compositeRankRaw` 供配售综合排序使用（不展示）
- [x] Task 8: 计算 `_forcePriceGap`/`_revisePriceGap` 供强赎/下修排序使用

## 前端：排序逻辑（所有 Tab 最优优先）

- [x] Task 9: 新增 `_sortByBest(list, tabKey)` 方法，各 Tab 按自身策略标准排序：
  - double_low: doubleLowNum 升序
  - force_redeem: _forcePriceGap 绝对值升序（最接近130%触发线优先）
  - discount: premiumNum 升序（折价最大优先）
  - down_revised: _revisePriceGap 绝对值升序（最接近85%触发线优先）
- [x] Task 10: `normalizeSignals` 中每个字段列表排序后用 `_sortByBest`
- [x] Task 11: `applyData` 中非 placement Tab `slice(0, 15)` 限制条数，placement 按 `_compositeRankRaw` 排序后同样限制

## 前端：版面精简

- [x] Task 12: 删除筛选快捷条（WXML + WXSS + JS data/filter 方法）
- [x] Task 13: 删除评分徽章（WXML + WXSS）
- [x] Task 14: 删除详情弹窗策略结论区（WXML + WXSS）
- [x] Task 15: 配售列表项分层结构：主行（正股名+风险标签+角标）+ 核心指标行 + 次要信息行
- [x] Task 16: 详情弹窗四分区：溢价率滑块→核心指标→正股风险（含vs20日均价）→发行信息
- [x] Task 17: 排序条新增"推荐"按钮（默认激活，对应 `composite` 排序）

## 验证

- [x] Task 18: node -c 语法检查通过（index.js）
- [x] Task 19: python py_compile 语法检查通过（convertible_bond.py、mock_data.py）
- [x] Task 20: 后端函数单元测试（评分/风险等级/安全垫/趋势计算正确）
