# 部署配置说明

## 当前部署策略

**开发阶段**：本地 Flask 后端

**上线方案**：CloudRun 容器部署

小程序端的发布配置由独立的 `trading-toolkit-mp` 仓库维护。

## 环境配置

### Flask 后端环境变量 (`cloudrun/`)

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | 数据库连接串 | `sqlite:///trading_toolkit.db` |
| `REDIS_URL` | Redis 连接串（留空用 fakeredis/内存） | 空 |
| `USE_MOCK` | `true` 强制使用 Mock 数据 | `false` |

示例：

```bash
# 使用 PostgreSQL
set DATABASE_URL=postgresql://user:pass@localhost:5432/trading_toolkit

# 使用 Redis 缓存
set REDIS_URL=redis://localhost:6379/0

# 强制 Mock
set USE_MOCK=true
python app.py
```

## Docker 云托管部署

当前 CloudRun（`cloudrun/Dockerfile`）已配置但**未部署**。如需使用：

```bash
# 1. 云开发控制台 → 云托管 → 新建服务
# 2. 获取镜像仓库地址后在本地构建推送
docker build -t trading-toolkit-service ./cloudrun
docker tag trading-toolkit-service ccr.ccs.tencentyun.com/<env-id>/trading-toolkit-service
docker push ccr.ccs.tencentyun.com/<env-id>/trading-toolkit-service
# 3. 在云托管控制台创建版本并部署
```

> ❗ 云托管需要按实例时长付费（最低约 30-100 元/月），当前阶段推荐先用本地 Flask 开发。

## 注意事项

1. **依赖体积**：部署云函数时控制第三方依赖体积，并确保网络稳定
2. **数据源限流**：东方财富等公开接口可能限制高频请求，所有请求必须使用统一 HTTP 客户端
3. **缓存预热**：首次部署云函数后建议手动触发一次各 action，避免用户首次访问冷启动
4. **费用**：云函数按月免费额度（40 万次/月）足够个人项目使用
