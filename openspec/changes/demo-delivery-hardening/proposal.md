## Why

Demo 服务已有容器和测试，但管理能力公开、发布未被测试严格阻断，且缺少可执行的跨仓库接口约束。需要在不引入用户登录的前提下建立最小交付保障。

## What Changes

- 增加最小健康检查、生产管理端点开关、受配置约束的 CORS 和去正文请求日志。
- 引入端点矩阵与服务端契约测试。
- 为生产 PostgreSQL 演进加入 Alembic 迁移入口和 CI 发布门禁。

## Capabilities

### New Capabilities
- `demo-service-delivery`: Demo 服务的公开运行边界、契约和发布验证。

### Modified Capabilities
- `operations-and-delivery`: 明确生产持久化与发布门禁。

## Impact

影响 `cloudrun/app.py`、数据库初始化、CI/CD、容器部署配置和配套 Web 变更 `demo-delivery-hardening`。回滚时保留上一部署版本并关闭新增生产配置，不回退到容器 SQLite。
