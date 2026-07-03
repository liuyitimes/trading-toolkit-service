# 前端优化与港股打新增强 - 验证清单

## Phase 1: 数据绑定联动优化

- [x] Checkpoint 1: 首页 `index.js` 的 `loadData`、`generateTimeline`、`checkIpoReminders` 函数中不存在硬编码日期字符串（如 `'2026-06-24'`、`'2026-06-26'`），均通过 `new Date()` 动态获取
- [x] Checkpoint 2: 首页 `index.js` 的 `loadData` 函数中不存在 `Math.random()` 调用（`loadMockData` 中的 Mock 数据除外）
- [x] Checkpoint 3: 首页港股打新卡片的"已上市"标签已改为"近期上市"
- [x] Checkpoint 4: 可转债页面 `convertible/index.js` 的 `formatBondItem` 函数中不存在 `Math.random()` 调用，未获取到 `hundredRight`/`lotStock`/`safetyPad` 时显示 `--`
- [x] Checkpoint 5: 可转债页面 `formatBondItem` 优先使用英文字段名（`item.price` 而非 `item['转债价格']`），中文字段仅作 `||` 兜底
- [x] Checkpoint 6: LOF 页面 `formatLofItem` 优先使用英文字段名（`item.premium` 而非 `item['溢价率']`），中文字段仅作 `||` 兜底
- [x] Checkpoint 7: 首页 `formatSignals` 优先使用英文字段名，中文字段仅作 `||` 兜底
- [x] Checkpoint 8: `app.js` 的 `globalData` 中存在 `favoriteVersion` 和 `ipoStatusVersion` 计数器
- [x] Checkpoint 9: `favoriteManager.js` 的 `toggle` 方法执行后递增 `app.globalData.favoriteVersion`
- [x] Checkpoint 10: 首页 `onShow` 中检查 `favoriteVersion` 变化并刷新自选状态
- [x] Checkpoint 11: 港股打新页面 `onShow` 中检查 `favoriteVersion` 和 `ipoStatusVersion` 变化并刷新
- [x] Checkpoint 12: 港股打新页面列表项展示申购/中签状态（从 `ipoStatusMap` 读取）

## Phase 2: 港股打新板块重构

- [x] Checkpoint 13: 港股打新页面 Tab 分类包含：全部、申购中、待上市、已上市、暗盘中（5个）
- [x] Checkpoint 14: 港股打新列表项展示发行价、每手股数、申购截止日、超额认购倍数、暗盘涨跌幅等关键字段
- [x] Checkpoint 15: 港股打新列表项支持点击跳转到详情页 `/pages/hkipoDetail/index?code=xxx`
- [x] Checkpoint 16: 港股打新页面存在"暗盘行情"卡片，展示暗盘交易中的新股数据
- [x] Checkpoint 17: 暗盘行情卡片在无数据时显示"暂无暗盘数据"占位
- [x] Checkpoint 18: 暗盘涨跌幅颜色遵循港股惯例（涨红跌绿）
- [x] Checkpoint 19: `app.json` 的 pages 数组中已注册 `pages/hkipoDetail/index`
- [x] Checkpoint 20: 港股打新详情页展示基本信息（名称/代码/行业/发行价/每手股数/发行规模/市盈率/上市日期）
- [x] Checkpoint 21: 港股打新详情页展示发行流程时间线，节点状态动态渲染（done/current/未开始）
- [x] Checkpoint 22: 港股打新详情页展示认购数据（超额认购倍数/孖展认购额/公开认购倍数/国际配售倍数）
- [x] Checkpoint 23: 港股打新详情页展示配售结果（一手中签率/申购倍数/配售回拨比例）
- [x] Checkpoint 24: 港股打新详情页展示上市表现（首日开盘价/首日收盘价/首日涨跌幅/累计涨跌幅）
- [x] Checkpoint 25: 港股打新详情页展示券商孖展列表（券商名称/孖展金额/占比/累计倍数），按金额降序
- [x] Checkpoint 26: 港股打新详情页券商孖展顶部展示总孖展额和总超额倍数
- [x] Checkpoint 27: 港股打新详情页无孖展数据时显示"暂无孖展数据"占位
- [x] Checkpoint 28: 港股打新详情页支持添加/取消自选和标记申购状态
- [x] Checkpoint 29: 超额认购倍数超过 100 倍时有高亮样式
- [x] Checkpoint 30: 港股打新详情页适配暗夜模式

## Phase 3: 打新日历动态化

- [x] Checkpoint 31: 首页 `index.js` 中存在 `generateCalendar(year, month)` 方法
- [x] Checkpoint 32: 首页 `index.wxml` 日历区域使用 `wx:for` 动态渲染，不存在硬编码的日期数字
- [x] Checkpoint 33: 日历根据 `ipoDrawList` 的 `apply_end_date`/`draw_date`/`list_date` 在对应日期显示标记
- [x] Checkpoint 34: 日历标记图标正确：申购(●蓝色)、抽签(▲橙色)、上市(★绿色)
- [x] Checkpoint 35: 日历支持月份切换（上月/下月按钮）
- [x] Checkpoint 36: 点击有事件的日期可查看当日打新事件列表
- [x] Checkpoint 37: 日历适配暗夜模式

## 全局验证

- [x] Checkpoint 38: 所有新增页面/组件在 iPhone SE（375px）和 iPhone 15 Pro Max（430px）屏幕下布局正常
- [x] Checkpoint 39: 所有新增页面/组件在暗夜模式下颜色、对比度正常
- [x] Checkpoint 40: 数据加载失败时显示错误提示和重试按钮，不静默使用 Mock 数据兜底（Mock 数据仅在首次加载且接口完全不可用时使用）
