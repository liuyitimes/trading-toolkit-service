# 部署配置说明

## 当前部署策略

**开发阶段**：本地 Flask 后端

**Demo 上线方案**：Render 新加坡区域的 Docker 服务。中国大陆访问为尽力而为，不承诺大陆节点或低延迟；约束依据见 [中国大陆部署与访问约束](research/china-mainland-hosting-options.md)。

Vue Web 应用由独立的 `trading-toolkit-web` 仓库维护；其 `VITE_API_BASE_URL` 必须指向本服务的公开地址。

## 环境配置

### Flask 后端环境变量 (`cloudrun/`)

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | 数据库连接串 | 本地默认 `sqlite:///trading_toolkit.db`；Render 必填 PostgreSQL URL |
| `CORS_ALLOWED_ORIGINS` | 可跨域调用服务的 Web 来源 | 本地 Vite 地址 |
| `ENABLE_ADMIN_API` | 是否开放管理接口 | `false` |
| `SENTRY_DSN` | Sentry 服务端异常上报地址 | 空，表示不启用 |
| `REDIS_URL` | Redis 连接串（留空用 fakeredis/内存） | 空 |
| `USE_MOCK` | `true` 强制使用 Mock 数据 | `false` |

示例：

```bash
# 使用 PostgreSQL
set DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/trading_toolkit

# 使用 Redis 缓存
set REDIS_URL=redis://localhost:6379/0

# 强制 Mock
set USE_MOCK=true
python app.py
```

## Render 部署

Render 使用根目录 `render.yaml` 和 `cloudrun/Dockerfile`。部署前在 Render 环境变量中设置：

- `DATABASE_URL`：免费托管 PostgreSQL 连接串，不能使用容器 SQLite。
- `CORS_ALLOWED_ORIGINS`：Cloudflare Pages 正式域名，多个来源以英文逗号分隔。
- `ENABLE_ADMIN_API=false`：生产环境保持默认关闭。
- `SENTRY_DSN`：接入 Sentry 时设置；未接入时留空。

Docker 镜像启动时会先运行 `alembic upgrade head`。迁移失败即终止启动，避免带错误结构上线。

GitHub Actions 需要以下 Secrets：

- `RENDER_DEPLOY_HOOK_URL`
- `RENDER_HEALTHCHECK_URL`，值为 Render 服务的 `https://<service>/healthz`

如需手动构建镜像：

```bash
docker build -f cloudrun/Dockerfile -t trading-toolkit-service .
```

> 免费数据库不可用时应停止或回滚发布，不得将 `DATABASE_URL` 改回容器内 SQLite。

## 注意事项

1. **依赖体积**：部署容器时控制第三方依赖体积，并确保网络稳定
2. **数据源限流**：东方财富等公开接口可能限制高频请求，所有请求必须使用统一 HTTP 客户端
3. **缓存预热**：首次部署容器后建议请求一次常用读取接口，避免用户首次访问承担冷启动
4. **费用**：云托管按所选实例和运行时长计费，请以平台账单规则为准
