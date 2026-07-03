# Tasks

## 前端 JS：detail 对象新增字段 + 板块检测 + 时间轴

- [x] Task 1: 在 `formatPendingItem` 的 detail 对象增加发行时间轴字段
  - [x] 定义 7 阶段数组 `ALL_STAGES` 按序：董事会预案、股东大会批准、交易所受理、上市委通过、同意注册、申购中、待上市
  - [x] 根据 `status` 计算 `currentStageIndex`（位置 0-6）
  - [x] 构建 `stageList` 数组，每项 `{ name, status: 'done'|'current'|'pending' }`
  - [x] 将 `stageList` 加入 `detail` 对象

- [x] Task 2: 在 `formatPendingItem` 增加板块检测
  - [x] 定义 `SECTOR_KEYWORDS` 常量（AI/新能源/半导体/医药等 10 个分类）
  - [x] 定义 `HOT_SECTORS` 集合（AI/新能源/半导体/医药/低空经济）
  - [x] 遍历关键词匹配 `stockName`，返回 `{ sectorTag, isHotSector }`
  - [x] 将 `sectorTag`、`isHotSector` 加入 `detail` 对象

## 前端 WXML：详情弹窗增加时间轴和板块标签

- [x] Task 3: 在弹窗顶部（溢价率滑块之前）增加板块标签行
  - [x] 展示 `{{selectedPending.sectorTag}}`，热门板块附加🔥
  - [x] 未匹配时显示"--"

- [x] Task 4: 在弹窗（溢价率滑块之后、核心指标之前）增加发行时间轴
  - [x] 水平布局 7 个 step：圆点 + 阶段名称
  - [x] 已完成=绿色✓、当前=金色▶、待完成=灰色○
  - [x] 用短连线连接相邻 step

## 前端 WXSS

- [x] Task 5: 板块标签样式
  - [x] `.sector-tag`：26rpx padding、圆角、颜色
  - [x] `.sector-tag.hot`：金色边框/背景

- [x] Task 6: 发行时间轴样式
  - [x] `.stage-row`：水平 flex 布局
  - [x] `.stage-dot`：圆点（8rpx 直径）
  - [x] `.stage-line`：连接线
  - [x] `.stage-name`：阶段名称 20rpx

## 验证

- [x] Task 7: node -c 语法检查通过
