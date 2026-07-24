# 服务端交付指南（GitHub Actions + Render）

本项目 Demo 阶段将 Flask 服务部署到 Render 新加坡区域。中国大陆访问属于尽力而为，不承诺大陆节点、低延迟或 SLA；详细限制见 [中国大陆部署与访问约束](research/china-mainland-hosting-options.md)。

## 发布链路

```
受保护 main 合并 -> GitHub Actions 测试 -> Render Deploy Hook -> /healthz 冒烟检查
```

工作流位于 `.github/workflows/backend-deploy.yml`。测试或部署失败时，后续步骤不会继续执行。

## 一次性配置

1. 在 Render 创建 Docker Web Service，仓库根目录使用 `render.yaml`，区域选择 Singapore。
2. 在 Render 为服务设置以下环境变量：

| 变量 | 值 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | 托管 PostgreSQL URL | 必填，禁止 SQLite。 |
| `CORS_ALLOWED_ORIGINS` | Cloudflare Pages 正式域名 | 多个来源用英文逗号分隔。 |
| `ENABLE_ADMIN_API` | `false` | 生产环境保持关闭。 |
| `SENTRY_DSN` | 可选 | 留空表示不启用异常上报。 |

3. 在 GitHub Actions Secrets 设置 `RENDER_DEPLOY_HOOK_URL` 与 `RENDER_HEALTHCHECK_URL`。后者应为 `https://<service>/healthz`。
4. 在 GitHub 为 `main` 启用 PR 审查和必需检查。至少要求服务测试、CodeQL 与 Dependabot 升级审查。

Docker 启动时会验证 `DATABASE_URL` 是 PostgreSQL URL，再执行 `alembic upgrade head`。任一阶段失败都会使新实例无法启动，避免错误结构或容器 SQLite 被发布。

## 本地验证

```bash
py -3.14 -m pytest cloudrun/tests backtest/tests
docker build -f cloudrun/Dockerfile -t trading-toolkit-service .
```

本地默认 SQLite 是开发便利配置；要验证 PostgreSQL，请设置 `DATABASE_URL=postgresql+psycopg2://...` 后执行 Alembic 迁移。不要将本地数据库文件或密钥提交到仓库。

## 发布后检查

```bash
curl https://<service>/healthz
```

返回必须为最小成功信封，且仅含 `data.status: "ok"`。管理诊断端点在生产默认返回 404，不应作为公开健康检查或监控目标。
