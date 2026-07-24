## ADDED Requirements

### Requirement: Demo 服务公开运行边界
服务 MUST 公开不含敏感配置的 `/healthz`。生产环境 MUST 默认禁用管理写操作和接口日志读取；仅在显式开发开关启用时允许这些操作。

#### Scenario: 生产健康检查
- **WHEN** 外部探测请求 `/healthz`
- **THEN** 服务返回成功状态且不包含数据库、缓存或数据源细节。

#### Scenario: 生产管理请求
- **WHEN** 未启用开发管理开关时请求管理端点
- **THEN** 服务返回未找到响应且不执行管理操作。

### Requirement: 可执行端点矩阵
服务 MUST 保存机器可读的端点矩阵，并验证其中的路径和方法与 Flask 路由一致。

#### Scenario: 端点矩阵漂移
- **WHEN** 清单声明不存在的路径或错误的方法
- **THEN** 服务契约测试失败。
