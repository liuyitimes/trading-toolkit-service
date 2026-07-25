# 后端开发指南

> 最后更新：2026-07-24

本仓库只包含 Flask 服务、回测框架和服务端文档。浏览器端位于独立仓库 `trading-toolkit-web`，两端通过 `/api/v1/` HTTP API 协作。

## 启动服务

```bash
cd cloudrun
pip install -r requirements.txt
python app.py
```

服务默认监听 `http://localhost:8080`。开发测试依赖使用 `requirements-dev.txt`：

```bash
pip install -r cloudrun/requirements-dev.txt
python -m pytest cloudrun/tests backtest/tests
```

## 验证接口

```bash
curl http://localhost:8080/healthz
curl http://localhost:8080/api/v1/market/overview
curl "http://localhost:8080/api/v1/convertible/list?page=1&page_size=3"
curl http://localhost:8080/api/v1/convertible/pending
```

读取型市场接口可以增加 `?refresh=true` 请求刷新。不要将该参数用于高频轮询。

## 目录职责

| 路径 | 职责 |
| --- | --- |
| `cloudrun/app.py` | Flask 路由、请求参数和响应编排。 |
| `cloudrun/services/` | 数据源访问、缓存、归一化和领域计算。 |
| `cloudrun/models/` | 持久化模型与数据库访问。 |
| `cloudrun/utils/response.py` | 成功与失败响应信封。 |
| `cloudrun/tests/` | 服务与接口测试。 |
| `backtest/` | 回测引擎与规则测试。 |
| `docs/` | 架构、领域、部署和接口文档。 |

## 客户端协作约定

- 后端 HTTP 字段使用 `snake_case`；Web Store 映射为 `camelCase`；展示层可另保留带单位字符串。
- 后端成功响应始终返回 `{ success, data, meta }`。Web Axios 客户端会解包 `data`。
- “待发配债候选标的”是 `/api/v1/convertible/pending` 返回项的统一名称。
- `cash_ratio` 表示百元含权；不得与评分指标 `stock_cash_ratio` 混用。
- 可选的 `placement_provenance` 统一称为“配债来源信息”。缺失表示不可用，不能用推断值补齐。

字段表、兼容边界和响应示例见 [接口与字段约定](DATA_GUIDE.md)。变更后端行为前，先阅读 `openspec/README.md` 与相关基线规格。

## 环境变量

| 变量 | 用途 | 默认行为 |
| --- | --- | --- |
| `DATABASE_URL` | 数据库连接串 | 使用本地 SQLite。 |
| `REDIS_URL` | Redis 连接串 | 未配置时使用 fakeredis 或内存缓存。 |
| `USE_MOCK` | 是否强制使用 Mock 数据 | 默认 `false`。 |
| `CORS_ALLOWED_ORIGINS` | 允许跨域访问的来源列表 | 本地 Vite 地址。 |
| `ENABLE_ADMIN_API` | 是否开放管理接口 | 默认关闭；本地诊断时设为 `true`。 |
| `SENTRY_DSN` | Sentry 异常上报地址 | 留空则不初始化。 |

## 常见问题

| 现象 | 处理方式 |
| --- | --- |
| `ModuleNotFoundError` | 在当前 Python 环境安装对应的 `requirements*.txt`。 |
| 数据为空或请求失败 | 检查网络、上游公开接口；本地可在 `ENABLE_ADMIN_API=true` 时检查 `admin/health` 输出。 |
| 数据看起来过期 | 先核对响应 `meta.update_time` 和 `meta.cached`，再按需用 `refresh=true` 触发刷新。 |
| Web 无法请求服务 | 确认 `trading-toolkit-web/.env.development` 的 `VITE_API_BASE_URL` 为服务地址。 |
