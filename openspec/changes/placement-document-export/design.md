## 背景与目标

本变更让服务端对“配债来源信息”使用一个明确的名称和数据边界，供 Web 的逐项 Markdown 导出消费。目标是输出可追溯事实，而不是把市场观察、推断值或历史配售结果误写成当前可执行资格。

## 范围与非目标

**范围：**

- 在待发配债候选标的上定义可选 `placement_provenance` 对象。
- 从已采集的公告或核验记录中填充可用字段，并保留缺失与需复核状态。
- 维持数组及现有响应信封兼容，并与 Web 同名变更使用同一字段定义。

**非目标：**

- 不把 `placement_evidence` 或裸 `provenance` 继续作为兼容别名输出。
- 不为缺失登记日、缴款时点或参与资格新增推断算法。
- 不创建服务端 Markdown 文件、批量下载或投资执行工作流。

## 术语与契约

| 术语 | 含义 |
| --- | --- |
| 配债来源信息 | 单个待发配债候选标的可追溯来源依据；接口字段唯一为 `placement_provenance`。 |
| 公告依据 | 配债来源信息中指向公告日期、公告链接和核验时间的部分。 |
| 缺失 | 服务端没有已采集且可信的数据；字段或整个对象应省略，不能填充推断值。 |

`placement_provenance` 可包含以下键：`eligibility`、`record_date`、`allocation_terms`、`payment_timing`、`announcement_date`、`announcement_url`、`verified_at`、`verification_state`、`review_required`。键缺失表示对应事实尚不可用。

## 决策

### 只输出一个字段名

服务端仅在单个待发配债项上输出 `placement_provenance`。Web 将它规范化为内部属性 `placementProvenance`。不读取也不输出 `placement_evidence` 与裸 `provenance`，以免同一事实有多个名称和冲突的优先级。

### 来源不足时保持缺失

现有 `PlacementResult` 主要记录配售结果公告，不能可靠提供待发配债所需的参与资格、登记日和缴款时点。因此实施时只能在来源记录确实具备字段和公告链接时填充对象；否则省略对象，让 Web 明确显示“未提供”。

### 保持观察与可执行机会的界限

`verification_state` 只能由已核验的来源记录给出。缺少完整资格与条款时不得将候选标的标记为已核验或可执行，`review_required` 可用于表达冲突或人工复核需要。

## 风险与待决问题

- 当前本地公告结果库缺少部分待发阶段的资格与缴款字段，因此首次实现可能只在少量候选标的返回配债来源信息。
- 公告 URL 或日期缺失时，必须省略对应键，不能用市场数据替代。
- 无待决字段命名问题；两端统一使用 `placement_provenance`。
