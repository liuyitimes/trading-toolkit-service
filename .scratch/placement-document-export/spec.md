# 配债来源信息契约

状态：ready-for-agent

本变更与 `trading-toolkit-web/openspec/changes/placement-document-export` 配套。两端唯一的待发配债来源字段是 `placement_provenance`，面向读者统一称为“配债来源信息”。

## 当前结论

- `placement_provenance` 表示单个配债候选标的的可追溯来源依据。
- `placement_evidence` 和裸 `provenance` 不再作为此概念的接口字段或兼容别名。
- 缺少可靠公告或核验记录时，服务省略对象或键，Web 显示“未提供”；不得推断资格、登记日或缴款时间。
- 当前公告结果存储主要覆盖结果公告，尚不能完整覆盖待发阶段所需的全部配债来源信息，后续实现必须先补齐可信数据适配。
