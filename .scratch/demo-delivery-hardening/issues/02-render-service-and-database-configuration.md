# 02 — Render 服务与数据库配置

**What to build:** 在 Render 新加坡创建可由 Web 访问的服务与 PostgreSQL，并以安全的生产配置运行、部署和健康检查。

**Blocked by:** 01 — WSL 容器与迁移验收。

**Status:** ready-for-agent

- [ ] 服务使用 PostgreSQL、受限 CORS 与关闭的管理接口启动。
- [ ] 部署 Hook 与最小健康检查地址可用于自动发布验证。
- [ ] 可选异常上报在配置时启用，未配置时不影响服务。
