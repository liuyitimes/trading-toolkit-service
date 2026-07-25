# Trading Toolkit Service OpenSpec

`openspec/specs/` 是 Flask 服务所负责行为的版本化唯一事实来源。它随 `trading-toolkit-service` Git 仓库保存，确保任意设备上的克隆都包含当前基线和活跃变更。

## 范围

- 版本化 HTTP 端点、响应信封、数据采集、规范化、缓存、持久化和服务端计算。
- 数据来源、降级数据行为、运维配置和 Python 回测包。
- 共享 API 契约中由服务侧负责的要求。

独立版本管理的 `trading-toolkit-web` 仓库负责 Vue 路由、视图、客户端计算和浏览器持久化。跨越这些边界的功能必须在两个仓库使用相同的变更名称；每个变更产物仅描述所属仓库的工作，并标识配套变更。

## 工作流

1. 阅读 `openspec/specs/` 下相关的基线规范。
2. 实现前创建或更新 `openspec/changes/<change-name>/`。
3. 完成提案、增量规格、设计和任务。
4. 验证实现并运行 `openspec validate <change-name> --json`。
5. 在本仓库归档已接受的变更，将其增量合并到此 Service 基线。
