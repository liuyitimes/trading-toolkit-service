# 服务端交付指南（GitHub Actions + Render）

本项目 Demo 阶段将 Flask 服务部署到 Render 新加坡区域。中国大陆访问属于尽力而为，不承诺大陆节点、低延迟或 SLA；详细限制见 [中国大陆部署与访问约束](research/china-mainland-hosting-options.md)。

## 发布链路

```
PR -> Backend CI（单测 + 迁移冒烟 + 镜像冒烟）
   -> 合并受保护 main
   -> Backend CI 在同一提交全绿
   -> Backend Deploy（串行、不取消）
   -> Render Deploy Hook -> /healthz 信封校验
   -> 失败则自动回滚到发布前的 live 部署
```

| 工作流 | 职责 | 触发 |
| --- | --- | --- |
| `backend-ci.yml` | 测试、迁移冒烟、镜像冒烟 | 任意分支 push、指向 main 的 PR |
| `backend-deploy.yml` | 发布、健康验证、自动回滚、发布归档 | Backend CI 在 main 成功后、手动触发 |

部署**不再**由 `push` 直接触发：发布必须消费同一提交的 CI 结果，避免"测试红了但照样上线"。

## 门禁明细

### 单元测试（SQLite）

`python -m pytest cloudrun/tests backtest/tests`，附 `compileall` 语法检查与 API 日志自检。

### PostgreSQL 迁移冒烟

使用 `postgres:16` service 容器，`DATABASE_URL` 刻意写成**不带驱动名**的 `postgresql://` 形态（即托管平台注入的原样值），依次验证：

1. 空库 `alembic upgrade head` 成功；
2. `alembic current` 可读；
3. 核心表（`alembic_version`、`lof_execution_rule`、`lof_execution_fund`）存在；
4. 以生产形态 `import app` 可完成，且驱动为 `psycopg2`。

### 镜像启动冒烟

构建真实镜像后以 `--network host` 启动，连接到 service 容器里的 PostgreSQL，断言 `/healthz` 返回成功信封；另外断言 `DATABASE_URL` 为 SQLite 时容器**必须拒绝启动**（生产兜底不能被悄悄绕过）。

> 该门禁是为 2026-10-22 发布故障补的：故障时 SQLAlchemy 2.1 把 `postgresql://` 解析到未安装的 psycopg（v3），只有真实构建并启动镜像才能发现。详见 [发布故障处置记录](release-incident-2026-10-22.md)。

## 一次性配置

1. 在 Render 创建 Docker Web Service，仓库根目录使用 `render.yaml`，区域选择 Singapore。
2. 在 Render 为服务设置以下环境变量：

| 变量 | 值 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | 托管 PostgreSQL URL | 必填，禁止 SQLite。`postgresql://` 与 `postgres://` 均会在运行期补齐驱动名。 |
| `CORS_ALLOWED_ORIGINS` | Cloudflare Pages 正式域名 | 多个来源用英文逗号分隔。 |
| `ENABLE_ADMIN_API` | `false` | 生产环境保持关闭。 |
| `SENTRY_DSN` | 可选 | 留空表示不启用异常上报。 |

3. 在 GitHub Actions Secrets 设置：

| Secret | 必填 | 用途 |
| --- | --- | --- |
| `RENDER_DEPLOY_HOOK_URL` | 是 | 触发部署。缺失时发布直接失败，不会静默跳过。 |
| `RENDER_HEALTHCHECK_URL` | 是 | `https://<service>/healthz`。 |
| `RENDER_API_KEY` | 否 | 自动回滚。缺失时降级为人工回滚并在 summary 给出步骤。 |
| `RENDER_SERVICE_ID` | 否 | 同上。 |

4. 在 GitHub 为 `main` 启用 PR 审查和必需检查。至少要求 `Backend CI` 三个 job、CodeQL 与 Dependabot 升级审查。

Docker 启动时会验证 `DATABASE_URL` 是 PostgreSQL URL，再执行 `alembic upgrade head`。任一阶段失败都会使新实例无法启动，避免错误结构、错误驱动或容器 SQLite 被发布。

## 本地验证

```bash
python -m pytest cloudrun/tests backtest/tests
docker build -f cloudrun/Dockerfile -t trading-toolkit-service .
```

本地默认 SQLite 是开发便利配置。要验证生产形态，两条命令即可复刻容器启动路径（不需要真实数据库）：

```bash
# 1) 驱动解析：必须输出 psycopg2
cd cloudrun && DATABASE_URL=postgresql://u:p@127.0.0.1:5432/db \
  python -c "import models.database as d; print(d.engine.dialect.driver)"

# 2) 迁移 SQL 生成（离线，不连库）
DATABASE_URL=postgresql://u:p@127.0.0.1:5432/db python -m alembic -c alembic.ini upgrade head --sql
```

不要将本地数据库文件或密钥提交到仓库。

## 发布后检查

```bash
curl --fail --silent https://<service>/healthz
```

返回必须为最小成功信封：`success: true` 且 `data.status: "ok"`。流水线校验的正是这两项，而不是仅看 HTTP 200。管理诊断端点在生产默认返回 404，不应作为公开健康检查或监控目标。

## 回滚

自动回滚在健康检查失败后立即执行，目标是本次发布前的 `live` 部署。人工路径：

1. Render Dashboard → 服务 `trading-toolkit-api` → Deploys → 选中上一个 `live` 部署 → Rollback。
2. 若本次发布含破坏性迁移，先确认可逆（四个迁移版本均实现 `downgrade()`），必要时 `alembic downgrade -1`。
3. 重新发布修正版本：`Backend Deploy to Render` 手动触发即可，默认发布 main 最新提交。

每次发布都会产出 `backend-release-record-<run_id>` 工件，含提交 SHA、回滚目标部署、触发方式、结果与时间戳，用于事后追溯。
