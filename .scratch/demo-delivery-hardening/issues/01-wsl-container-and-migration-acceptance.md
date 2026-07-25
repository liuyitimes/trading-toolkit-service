# 01 — WSL 容器与迁移验收

**What to build:** 在 WSL Ubuntu 中证明服务容器拒绝临时 SQLite，能够使用 PostgreSQL 运行 Alembic 迁移，并对外提供最小健康状态。

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] Docker 镜像可从仓库根目录构建。
- [x] 未提供 PostgreSQL 时，容器明确拒绝启动。
- [x] PostgreSQL 容器下迁移成功，服务的健康端点返回成功。

## Answer

已在 WSL Ubuntu 中完成。镜像使用临时最小上下文构建，以避开工作区根目录异常权限的测试缓存；容器在未设置 PostgreSQL URL 时退出，在临时 PostgreSQL 实例下执行迁移并返回 `/healthz` 成功响应。测试资源已清理。
