# Tasks

- [x] Task 1: 后端数据透传 — formatLofItem 增加 amount/volume/limit_amount 字段，计算净溢价和可套利标记
  - [x] SubTask 1.1: 透传 `amount`（成交额）、`volume`（成交量）字段
  - [x] SubTask 1.2: 计算 `netPremium` = premium rate - 申购费率(0.15%) > 0
  - [x] SubTask 1.3: 计算 `arbitrageScore` = 溢价 > 3% + 成交额 > 100万 + 连续 > 5天 + 不限购
  - [x] SubTask 1.4: 格式化成交额（亿/万/元单位自适应）

- [x] Task 2: 表头/行布局改造 — WXML 增加成交额列、条件标记行
  - [x] SubTask 2.1: 表头增加"成交额"列 + "净溢价"列
  - [x] SubTask 2.2: 行内增加成交额数据显示（亿/万格式 + 色标）
  - [x] SubTask 2.3: 行内增加净溢价/可套利标记/流动性标记
  - [x] SubTask 2.4: 行 tap 绑定 openDetail 弹窗事件

- [x] Task 3: CSS 新样式 — 成交额列、标签、弹窗
  - [x] SubTask 3.1: `.col-volume` / `col-net-premium` 列宽定义
  - [x] SubTask 3.2: 成交额色标 `.volume-safe` / `.volume-warn` / `.volume-danger`
  - [x] SubTask 3.3: 标签样式 `.tag-arbitrage` / `.tag-sustained` / `.tag-warning`
  - [x] SubTask 3.4: 弹窗样式 `.lof-detail-modal` 仿配售弹窗
  - [x] SubTask 3.5: 暗夜模式全部覆盖

- [x] Task 4: 详情弹窗 — WXML + WXSS
  - [x] SubTask 4.1: 弹窗框架（遮罩 + 内容容器）
  - [x] SubTask 4.2: 四个区域：基金概要 / 价格净值 / 流动性 / 操作建议
  - [x] SubTask 4.3: 操作建议根据条件动态生成文字

- [x] Task 5: 顶部概览增强
  - [x] SubTask 5.1: 增加"可套利"计数（溢价>3%+成交额>100万）
  - [x] SubTask 5.2: 增加"流动性差"计数（成交额<10万）

- [x] Task 6: Mock 数据补充
  - [x] SubTask 6.1: LOF_LIST 补充 `成交量`、`成交额` 字段

# Task Dependencies
- Task 2 依赖 Task 1（数据字段就绪后才能渲染）
- Task 3 可与 Task 2 并行
- Task 5 依赖 Task 1（统计数据）
