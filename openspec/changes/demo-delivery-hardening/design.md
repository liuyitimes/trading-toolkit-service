## Context

服务将作为 Render 新加坡的公开 Demo API 运行，不实现用户登录。Web 配套变更负责 Cloudflare Pages 和浏览器验证。

## Goals / Non-Goals

**Goals:** 以环境变量控制生产边界，提供可执行契约和可回滚的发布检查。

**Non-Goals:** 不实现鉴权、灾备、集中监控或 Worker 代理。

## Decisions

- `/healthz` 与管理诊断分离；管理端点由 `ENABLE_ADMIN_API` 显式开启。
- CORS 使用逗号分隔的允许来源；开发默认允许本地 Vite 地址。
- 端点矩阵是 OpenSpec 的机器可验证投影；Web CI 读取同一文件。
- Alembic 是生产结构演进入口；本地 SQLite 仍用于测试。

## Risks / Trade-offs

- [免费 PostgreSQL 休眠或不可用] -> 发布失败或回滚，不使用容器 SQLite。
- [大陆访问不稳定] -> 作为尽力而为限制记录，不承诺网络 SLA。
