## 1. 契约与数据组装

- [x] 1.1 创建与 Web 同名的 `placement-document-export` OpenSpec 变更，统一“配债来源信息”术语和 `placement_provenance` 字段。验证：两仓库 OpenSpec 变更文档交叉检查。
- [ ] 1.2 为待发配债数据建立只读取已采集公告或核验记录的来源信息适配器。验证：服务单元测试覆盖完整、部分和缺失来源。
- [ ] 1.3 在 `GET /api/v1/convertible/pending` 单项响应中可选输出 `placement_provenance`，不得输出 `placement_evidence` 或裸 `provenance`。验证：API 契约测试。

## 2. 可靠性与验证

- [ ] 2.1 覆盖来源缺失、未核验、需复核和完整公告依据，确认不会生成推断或虚构字段。验证：`cloudrun/tests/test_convertible_pending.py`。
- [ ] 2.2 运行服务端相关测试和 `openspec validate placement-document-export --json`。验证：命令退出码为零。
