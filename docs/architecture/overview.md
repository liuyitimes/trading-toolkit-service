# 系统结构与依赖总览

状态：当前实现
适用版本：2026-10-22

本文给出跨仓库的整体结构、模块职责与依赖方向，作为排查与交付的入口。领域细节仍以各自专题文档为准：[数据源与缓存](data-sources.md)、[回测引擎](backtesting.md)。

## 1. 仓库拓扑

```
D:/Develop/GitHub/trading-toolkit        （根目录本身不是 Git 仓库）
├── trading-toolkit-service              独立仓库，Python/Flask，部署 Render 新加坡
└── trading-toolkit-web                  独立仓库，Vue 3 + Vite，部署 Cloudflare Pages
```

两仓库通过单一机器可读契约耦合：服务端 `contracts/http-api.json` 是唯一权威端点矩阵，Web 侧 `src/api/` 的路径与方法必须与之一致，由 Web CI 强制校验。跨仓库变更遵循 **服务先兼容新增 → Web 切换 → 旧能力最后删除**。

## 2. 运行时拓扑

```
浏览器
  └── Cloudflare Pages（静态 dist，哈希化资源，immutable 缓存）
        └── HTTPS + CORS ──> Render Docker Service（gunicorn 2 worker）
                                ├── Flask app
                                ├── 领域服务 ──> 公开 HTTP 上游（东方财富 / 巨潮等）
                                └── SQLAlchemy ──> 托管 PostgreSQL（Alembic 迁移）
```

容器启动顺序固定为：校验 `DATABASE_URL` 协议 → `alembic upgrade head` → `gunicorn`。任一环节失败即终止启动，不允许带着错误结构或错误驱动对外服务。

## 3. 服务端模块职责

| 模块 | 职责 | 依赖方向 |
| --- | --- | --- |
| `cloudrun/app.py` | 路由与请求编排、统一响应信封、CORS、健康检查、管理端点开关 | → services、models、utils |
| `cloudrun/cli.py` | 运维命令入口（回补、刷新、任务接管） | → services、models |
| `cloudrun/services/` | 领域服务：行情、转债、LOF、配债、港股 IPO、封基、公告解析、缓存、限流 | → http_client、models |
| `cloudrun/services/factory.py` | 唯一数据源工厂，仅 `DirectSource`，不保留隐式备用源 | → direct_source |
| `cloudrun/services/http_client.py` | 统一出网客户端：会话、重试、超时、上游限流 | 叶子依赖 |
| `cloudrun/models/` | SQLAlchemy 模型与引擎装配；`database.py` 负责连接串归一化 | → utils.dburl |
| `cloudrun/migrations/` | Alembic 迁移链，基线 `9c3cae4c1a70` 起线性演进，四个版本均实现 `downgrade` | → models |
| `cloudrun/utils/` | 响应信封、日志、限流、类型转换、`dburl` 连接串归一化 | 叶子依赖 |
| `cloudrun/contracts` → 根 `contracts/` | 机器可读端点矩阵，跨仓库契约源 | 无代码依赖 |
| `backtest/` | 独立回测包：分钟 K 线驱动，broker/exchange/portfolio/metrics 分层 | 不依赖 cloudrun |
| `cloudrun/data/`、`.runtime/` | 上游快照与运行期缓存，不入镜像 | 无 |
| `cloudrun/systemd/` | 定时任务单元（LOF 溢价采集与回补） | 无 |

依赖方向严格单向：`app → services → http_client / models → utils`。反向引用会导致循环导入（历史上 `models` 模块级建引擎就在导入期放大过故障面）。

## 4. Web 模块职责

| 模块 | 职责 |
| --- | --- |
| `src/api/` | 按领域拆分的请求层，`contracts.js` 集中导出端点定义供 CI 校验 |
| `src/stores/` | Pinia 状态：`app` 全局、各领域 store、`quote` 行情轮询、`floating` 浮层 |
| `src/views/` | 页面：首页、转债（含详情）、LOF（含详情）、配债、港股 IPO、封基、收藏、设置、API 日志 |
| `src/components/` | 通用与图表组件（仲裁图、情绪仪表、报价轮播等） |
| `src/domain/` | 纯函数领域逻辑，可被 Node 直接单测（新债表现、LOF 溢价） |
| `src/utils/` | 导出、格式化等工具 |
| `tests/` | 契约、导出、浏览器冒烟等验证脚本，按 `package.json` 的 `verify:*` 暴露 |
| `scripts/browser/` | 按需运行的调试与人工核查脚本，不进入 CI 门禁 |
| `scripts/wsl/` | WSL 本地受管交付（生产构建 + Flask 服务） |

`src/domain/` 与 `src/utils/` 被设计为无浏览器依赖，因此 `tests/*.mjs` 能直接用 Node 导入它们；反之 `src/stores/` 只能在浏览器上下文里通过 dev server 的 `/src/...` 路径导入 —— 这决定了浏览器用例必须分成"构建产物冒烟"与"源码级用例"两段。

## 5. 交付链路与门禁

| 阶段 | 服务端 | Web |
| --- | --- | --- |
| 构建 | `docker build` + 容器启动冒烟 | `vite build` + 产物断言 |
| 测试 | 单测（SQLite）+ PostgreSQL 迁移冒烟 + `/healthz` 信封断言 | 格式、契约、导出 + 生产构建浏览器冒烟 + 源码级用例 |
| 部署 | Backend CI 全绿 → Deploy Hook（串行、不取消） | CI 全绿 → `wrangler pages deploy` |
| 验证 | 健康检查校验 `success`/`status` | 生产页面必须引用本次构建独有哈希入口 + immutable 缓存头 |
| 回滚 | 失败自动调 Render rollback 回上一 live 部署；缺凭据降级人工 | 手动指定 ref 重新发布，或 Cloudflare 部署回滚 |

两仓库均产出 `release-record.json` 归档（提交、触发方式、结果、回滚目标、时间戳）。

## 6. 关键约束

1. **生产禁止容器内 SQLite**：容器启动即拒绝，流水线另有专门用例守住这条兜底。
2. **连接串必须显式驱动名**：统一经 `utils.dburl`，不依赖 SQLAlchemy 默认 DBAPI（2026-10-22 发布故障根因）。
3. **测试不得依赖系统时钟**：涉及日期的断言显式传 `now=`。
4. **契约先兼容后切换**：服务端不删除 Web 仍在调用的端点。
5. **中国访问为尽力而为**：不承诺大陆节点、低延迟或 SLA。
