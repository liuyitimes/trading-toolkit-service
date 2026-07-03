# 前端优化与港股打新增强 - 实现计划

## Phase 1: 数据绑定联动优化（消除硬编码与随机数）

### 阶段目标
移除前端所有硬编码日期、随机数兜底，统一字段命名，实现数据驱动渲染。

---

## [x] Task 1: 首页硬编码日期与随机数清理
- **Priority**: high
- **Depends On**: None
- **Description**:
  - 移除 `index.js` 中 `loadData` 内 `const today = '2026-06-26'` 硬编码，改为 `new Date().toISOString().slice(0, 10)`
  - 移除 `generateTimeline` 中 `const today = '2026-06-24'` 硬编码兜底日期，当 timeline 数据为空时返回空数组，前端显示"暂无流程信息"
  - 移除 `checkIpoReminders` 中 `const today = '2026-06-26'` 硬编码，改为动态获取当天日期
  - 移除 `loadData` 中 `win_rate` 的随机生成逻辑 `(10 + Math.random() * 20).toFixed(1)`，未获取到时设为 `null`
  - 移除 `loadData` 中可转债 `win_rate` 的随机生成 `(0.01 + Math.random() * 0.03).toFixed(3)`，未获取到时设为 `null`
  - 移除 `loadData` 中 `pe_ratio` 的随机生成 `Math.round(20 + Math.random() * 40)`，未获取到时设为 `null`
  - 移除 `loadData` 中 `issue_size` 的随机生成 `Math.round(5 + Math.random() * 15) + '亿元'`，未获取到时设为 `null`
  - 修正港股打新卡片"已上市"标签为"近期上市"
- **Acceptance Criteria Addressed**: AC-1, AC-2
- **Test Requirements**:
  - `programmatic` TR-1.1: `index.js` 中搜索 `Math.random()`，结果为 0（loadData 和 generateTimeline 范围内）
  - `programmatic` TR-1.2: `index.js` 中搜索 `'2026-06-2` 硬编码日期字符串，结果为 0（排除注释）
  - `programmatic` TR-1.3: `index.js` 中搜索 `'2026-06-1` 硬编码日期字符串，结果为 0（排除注释）
  - `human-judgement` TR-1.4: 首页港股打新卡片"已上市"标签已改为"近期上市"
- **Notes**: `loadMockData` 中的 Mock 数据保留日期硬编码，因为 Mock 数据本身就是固定的演示数据

## [x] Task 2: 可转债页面随机数兜底清理
- **Priority**: high
- **Depends On**: None
- **Description**:
  - 移除 `convertible/index.js` 的 `formatBondItem` 中 `hundredRightValue` 的随机兜底 `8 + Math.random() * 15`，改为 `0` 或 `null`
  - 移除 `lotStockCount` 的随机计算兜底 `Math.round(1000 / (hundredRightValue / 100) / stockPriceNum)`，当 `hundredRightValue` 为 null 时返回 `--`
  - 移除 `safetyPadValue` 的随机兜底 `25 / hundredRightValue * 100`，当 `hundredRightValue` 为 null 时返回 `--`
  - 当后端未返回 `百元含权`、`配售十张所需股数`、`安全垫` 字段时，对应显示 `--`
- **Acceptance Criteria Addressed**: AC-2
- **Test Requirements**:
  - `programmatic` TR-2.1: `convertible/index.js` 中搜索 `Math.random()`，结果为 0
  - `human-judgement` TR-2.2: 当后端未返回百元含权等字段时，页面显示 `--` 而非随机数值
- **Notes**: 无

## [x] Task 3: 字段命名统一（中英文混用清理）
- **Priority**: high
- **Depends On**: None
- **Description**:
  - 可转债页面 `formatBondItem`：统一使用英文字段名，移除 `item['转债价格']`、`item['转股溢价率']`、`item['双低']`、`item['转债名称']`、`item['转债代码']`、`item['正股名称']`、`item['正股代码']`、`item['交易所']`、`item['转股价值']`、`item['转股价']`、`item['正股价']`、`item['纯债价值']`、`item['到期税前收益']`、`item['评级']`、`item['信用评级']`、`item['百元含权']`、`item['配售十张所需股数']`、`item['安全垫']` 等中文字段读取
  - 改为读取英文字段名：`item.bond_code`、`item.bond_name`、`item.price`、`item.premium_rate`、`item.double_low`、`item.stock_code`、`item.stock_name`、`item.exchange`、`item.conversion_value`、`item.conversion_price`、`item.stock_price`、`item.pure_bond_value`、`item.ytm`、`item.rating`、`item.hundred_right`、`item.lot_stock_count`、`item.safety_pad`
  - LOF 页面 `formatLofItem`：移除 `item['溢价率']`、`item['最新价']`、`item['估值']`、`item['连续溢价']`、`item['申购状态']`、`item['名称']`、`item['代码']`、`item['涨跌幅']`、`item['交易所']` 兼容，统一用英文字段
  - 港股打新页面 `formatIpoItem`：确保使用英文字段名
  - 首页 `formatSignals`：移除中文字段读取，统一英文
  - 保留对后端可能仍返回中文字段的过渡兼容（`item.bond_code || item['转债代码']`），但优先使用英文字段
- **Acceptance Criteria Addressed**: AC-8
- **Test Requirements**:
  - `programmatic` TR-3.1: `convertible/index.js` 的 `formatBondItem` 函数中，直接读取中文字段（非 `||` 兜底）的代码行为 0
  - `programmatic` TR-3.2: `lof/index.js` 的 `formatLofItem` 函数中，直接读取中文字段（非 `||` 兜底）的代码行为 0
  - `programmatic` TR-3.3: `index.js` 的 `formatSignals` 函数中，直接读取中文字段（非 `||` 兜底）的代码行为 0
  - `human-judgement` TR-3.4: 各页面在数据正常加载时显示正确，无字段读取错误导致的 `--` 或 `undefined`
- **Notes**: 后端字段标准化（normalizer.py）由 backend-api-design spec 负责，本任务只做前端适配，保留 `||` 兜底以防后端未完成标准化

## [x] Task 4: 跨页面状态同步机制
- **Priority**: medium
- **Depends On**: None
- **Description**:
  - 在 `app.js` 的 `globalData` 中添加 `favoriteVersion: 0` 和 `ipoStatusVersion: 0` 计数器
  - `favoriteManager.js` 的 `toggle` 和 `remove` 方法中，调用后递增 `app.globalData.favoriteVersion`
  - 首页 `onShow` 中检查 `favoriteVersion` 是否变化，变化则调用 `refreshFavorites`
  - 港股打新页面 `onShow` 中检查 `favoriteVersion` 和 `ipoStatusVersion`，变化则刷新
  - 自选管理页面 `onShow` 中检查 `favoriteVersion`，变化则刷新
  - 首页 `toggleSubscribe` 和 `toggleWin` 中递增 `app.globalData.ipoStatusVersion`
  - 港股打新页面读取 `ipoStatusMap` 并在列表中展示申购/中签状态
- **Acceptance Criteria Addressed**: AC-7, AC-10
- **Test Requirements**:
  - `programmatic` TR-4.1: `app.js` 的 `globalData` 中存在 `favoriteVersion` 和 `ipoStatusVersion` 字段
  - `programmatic` TR-4.2: `favoriteManager.js` 的 `toggle` 方法中存在递增 `favoriteVersion` 的代码
  - `human-judgement` TR-4.3: 在港股打新页面添加自选后，切到首页，自选状态已同步（无需下拉刷新）
  - `human-judgement` TR-4.4: 在首页标记申购后，切到港股打新页面，申购状态已同步
- **Notes**: 使用简单的版本号计数器方案，不引入 EventBus 等额外复杂度

---

## Phase 2: 港股打新板块重构（参考捷利交易宝）

### 阶段目标
参考捷利交易宝，重构港股打新列表页，新增暗盘行情、详情页、券商孖展等核心功能。

---

## [x] Task 5: 港股打新列表页增强
- **Priority**: high
- **Depends On**: Task 3
- **Description**:
  - Tab 分类改为：全部 / 申购中 / 待上市 / 已上市 / 暗盘中（根据 `status` 和 `dark_pool_status` 字段筛选）
  - 列表项增加字段展示：发行价、每手股数、申购截止日、上市日、超额认购倍数（`oversubscription`）、暗盘涨跌幅（`dark_pool_change`）
  - 列表项点击跳转详情页 `navigateTo /pages/hkipoDetail/index?code=xxx`
  - 列表支持排序：按超额认购倍数、暗盘涨跌幅排序（点击表头切换）
  - 列表项展示申购状态标记（从 `ipoStatusMap` 读取 `subscribed`/`won`）
  - 移除 `getMockData` 中的硬编码数据，改为从后端获取，获取失败时显示空状态
- **Acceptance Criteria Addressed**: AC-9
- **Test Requirements**:
  - `programmatic` TR-5.1: `hkipo/index.wxml` 中存在 5 个 Tab（全部/申购中/待上市/已上市/暗盘中）
  - `programmatic` TR-5.2: `hkipo/index.js` 中 `formatIpoItem` 函数包含 `oversubscription` 和 `dark_pool_change` 字段处理
  - `programmatic` TR-5.3: `hkipo/index.wxml` 中列表项存在 `bindtap` 或 `catchtap` 跳转详情页的代码
  - `human-judgement` TR-5.4: 列表项展示发行价、每手股数、申购截止日等关键字段，布局清晰
  - `human-judgement` TR-5.5: 点击列表项可跳转到详情页
  - `human-judgement` TR-5.6: Tab 切换功能正常，各分类下显示对应的 IPO 数据
- **Notes**: 后端需扩展 `hk_ipo.py` 返回 `oversubscription`、`dark_pool_change`、`lot_size`、`win_rate` 等字段，前端做 `||` 兜底

## [x] Task 6: 港股打新暗盘行情模块
- **Priority**: medium
- **Depends On**: Task 5
- **Description**:
  - 在港股打新页面列表上方新增"暗盘行情"卡片
  - 卡片展示当日暗盘交易中的新股：名称、代码、暗盘价、暗盘涨跌幅、发行价对比
  - 暗盘涨跌幅正数红色（港股惯例涨红跌绿），负数绿色
  - 点击暗盘卡片项跳转详情页
  - 暗盘数据从 `callMarketSafe('hkipoDarkPool')` 获取（新 action），数据为空时显示"暂无暗盘数据"
  - 暗盘卡片支持左右滑动查看多只
- **Acceptance Criteria Addressed**: AC-5
- **Test Requirements**:
  - `programmatic` TR-6.1: `hkipo/index.wxml` 中存在暗盘行情卡片的 WXML 结构
  - `programmatic` TR-6.2: `hkipo/index.js` 中存在加载暗盘数据的逻辑（调用 `callMarketSafe`）
  - `human-judgement` TR-6.3: 有暗盘数据时，卡片展示新股名称、暗盘价、暗盘涨跌幅
  - `human-judgement` TR-6.4: 无暗盘数据时，显示"暂无暗盘数据"占位
  - `human-judgement` TR-6.5: 暗盘涨跌幅颜色正确（涨红跌绿，港股惯例）
- **Notes**: 港股涨跌色与 A 股相反（涨红跌绿），需注意颜色样式

## [x] Task 7: 港股打新详情页 - 基础信息与发行流程
- **Priority**: high
- **Depends On**: Task 5
- **Description**:
  - 新建 `pages/hkipoDetail/` 目录，包含 index.js/json/wxml/wxss
  - 在 `app.json` 中注册新页面路由
  - 详情页接收 `code` 参数，调用 `callMarketSafe('hkipoDetail', { code })` 获取详情数据
  - 基本信息区域：名称、代码、行业、发行价、每手股数、发行规模、市盈率、上市日期
  - 发行流程时间线：递表→聆讯通过→招股开始→招股截止→公布中签→上市，动态渲染
  - 时间线节点支持 done/current/未开始 三种状态
  - 支持添加/取消自选（调用 `favoriteManager.toggle`）
  - 支持标记申购状态（从 `ipoStatusMap` 读取/写入）
  - 适配暗夜模式
- **Acceptance Criteria Addressed**: AC-4
- **Test Requirements**:
  - `programmatic` TR-7.1: `app.json` 的 pages 数组中包含 `pages/hkipoDetail/index`
  - `programmatic` TR-7.2: `hkipoDetail/index.js` 的 `onLoad` 中读取 `code` 参数并调用数据加载
  - `programmatic` TR-7.3: `hkipoDetail/index.wxml` 中存在基本信息区域和时间线区域
  - `human-judgement` TR-7.4: 详情页展示完整的基本信息（名称/代码/行业/发行价/每手股数等）
  - `human-judgement` TR-7.5: 发行流程时间线动态渲染，节点状态正确
  - `human-judgement` TR-7.6: 自选和申购状态标记功能正常
  - `human-judgement` TR-7.7: 暗夜模式下样式正常
- **Notes**: 详情页数据由后端 `hkipoDetail` action 提供，前端做字段兜底

## [x] Task 8: 港股打新详情页 - 认购数据与配售结果
- **Priority**: high
- **Depends On**: Task 7
- **Description**:
  - 在详情页新增"认购数据"区域：超额认购倍数（`oversubscription`）、孖展认购额（`margin_total`）、公开认购倍数（`public_oversubscription`）、国际配售倍数（`international_oversubscription`）
  - 新增"配售结果"区域：一手中签率（`win_rate`）、申购倍数（`apply_multiple`）、配售回拨比例（`clawback_ratio`）
  - 新增"上市表现"区域：首日开盘价（`open_price`）、首日收盘价（`close_price`）、首日涨跌幅（`change_pct`）、累计涨跌幅（`total_change`）
  - 各区域数据不足时对应字段显示 `--`
  - 认购倍数超过 100 倍时高亮显示
- **Acceptance Criteria Addressed**: AC-4
- **Test Requirements**:
  - `programmatic` TR-8.1: `hkipoDetail/index.wxml` 中存在"认购数据"、"配售结果"、"上市表现"三个区域
  - `programmatic` TR-8.2: `hkipoDetail/index.js` 中 `formatDetail` 函数处理 `oversubscription`、`win_rate`、`open_price` 等字段
  - `human-judgement` TR-8.3: 认购数据区域展示超额认购倍数等字段，数据不足时显示 `--`
  - `human-judgement` TR-8.4: 配售结果区域展示一手中签率等字段
  - `human-judgement` TR-8.5: 上市表现区域展示首日开盘价、收盘价、涨跌幅
  - `human-judgement` TR-8.6: 超额认购倍数超过 100 倍时有高亮样式
- **Notes**: 无

## [x] Task 9: 港股打新详情页 - 券商孖展模块
- **Priority**: medium
- **Depends On**: Task 7
- **Description**:
  - 在详情页新增"券商孖展"区域
  - 展示各券商孖展认购数据：券商名称、孖展金额（亿）、占比（%）、累计倍数
  - 孖展数据从详情接口的 `margin_list` 字段获取
  - 数据以列表形式展示，按孖展金额降序排列
  - 顶部展示汇总：总孖展额、总超额倍数
  - 数据不足时显示"暂无孖展数据"占位
  - 适配暗夜模式
- **Acceptance Criteria Addressed**: AC-6
- **Test Requirements**:
  - `programmatic` TR-9.1: `hkipoDetail/index.wxml` 中存在"券商孖展"区域
  - `programmatic` TR-9.2: `hkipoDetail/index.js` 中存在 `margin_list` 字段的处理逻辑
  - `human-judgement` TR-9.3: 有孖展数据时，展示券商名称、孖展金额、占比，按金额降序
  - `human-judgement` TR-9.4: 顶部展示总孖展额和总超额倍数
  - `human-judgement` TR-9.5: 无孖展数据时，显示"暂无孖展数据"占位
  - `human-judgement` TR-9.6: 暗夜模式下样式正常
- **Notes**: 参考捷利交易宝"券商孖展资金分布"功能

---

## Phase 3: 打新日历动态化

### 阶段目标
将首页打新日历从硬编码改为基于真实数据动态渲染。

---

## [x] Task 10: 打新日历动态渲染
- **Priority**: medium
- **Depends On**: Task 1
- **Description**:
  - 移除 `index.wxml` 中硬编码的日历日期（`<view class="day">21...` 等）
  - 在 `index.js` 中新增 `generateCalendar(year, month)` 方法，生成当月日历数据结构
  - 日历数据结构：`{ day: number, date: 'YYYY-MM-DD', events: [{ type: 'subscribe'|'draw'|'list', name: string, code: string }] }`
  - 遍历 `ipoDrawList`，根据 `apply_end_date`、`draw_date`、`list_date` 将事件填入对应日期
  - 日历支持月份切换：点击上月/下月按钮切换，重新生成日历数据
  - 点击有事件的日期，弹出当日打新事件列表
  - 日历标记图标：申购(●蓝色)、抽签(▲橙色)、上市(★绿色)
  - 适配暗夜模式
- **Acceptance Criteria Addressed**: AC-3
- **Test Requirements**:
  - `programmatic` TR-10.1: `index.js` 中存在 `generateCalendar` 函数
  - `programmatic` TR-10.2: `index.wxml` 中日历区域使用 `wx:for` 动态渲染，不存在硬编码的日期数字
  - `programmatic` TR-10.3: `index.js` 中存在月份切换逻辑（`prevMonth`/`nextMonth` 方法）
  - `human-judgement` TR-10.4: 日历根据 `ipoDrawList` 数据在对应日期显示申购、抽签、上市标记
  - `human-judgement` TR-10.5: 月份切换功能正常，切换后日历重新渲染
  - `human-judgement` TR-10.6: 点击有事件的日期可查看当日打新事件
  - `human-judgement` TR-10.7: 暗夜模式下日历样式正常
- **Notes**: 日历数据来源于已有的 `ipoDrawList`，无需额外接口调用

---

## Task Dependencies

```
Phase 1 (可并行):
  Task 1 (首页硬编码清理) ──→ Task 10 (打新日历动态化)
  Task 2 (可转债随机数清理) ──→ 独立
  Task 3 (字段命名统一) ──→ Task 5 (港股打新列表增强)
  Task 4 (跨页面状态同步) ──→ 独立

Phase 2 (依赖 Phase 1 的 Task 3):
  Task 5 (列表增强) ──→ Task 6 (暗盘行情)
                    ──→ Task 7 (详情页基础) ──→ Task 8 (认购数据)
                                             ──→ Task 9 (券商孖展)

Phase 3 (依赖 Phase 1 的 Task 1):
  Task 10 (打新日历动态化)
```
