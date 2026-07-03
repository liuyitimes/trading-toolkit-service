# Checklist

## detail 对象新字段
- [x] `detail` 含 `stageList`（7 阶段数组，每项 `{name, status}`）
- [x] `detail` 含 `sectorTag`（板块名称）
- [x] `detail` 含 `isHotSector`（boolean）

## 时间轴逻辑
- [x] ALL_STAGES 按序定义 7 个阶段
- [x] `currentStageIndex` 根据 `status` 正确计算
- [x] 已完成阶段标记 `done`（绿色✓）
- [x] 当前阶段标记 `current`（金色▶）
- [x] 待完成阶段标记 `pending`（灰色○）
- [x] `--` 状态不报错，全部显示灰色

## 板块检测逻辑
- [x] SECTOR_KEYWORDS 覆盖 10 个分类、各分类 3-6 个关键词
- [x] 匹配到关键词正确返回 sectorTag
- [x] 匹配不到返回 `--`/`false`
- [x] 热门板块标记 `isHotSector=true` 和 🔥

## WXML 弹窗
- [x] 板块标签在弹窗顶部显示
- [x] 发行时间轴在溢价率滑块后、核心指标前显示
- [x] 7 个阶段水平排列带连接线

## WXSS
- [x] `.sector-tag` / `.sector-tag.hot` 样式
- [x] `.stage-row` / `.stage-dot` / `.stage-line` / `.stage-name` 样式

## 验证
- [x] node -c 语法检查通过
