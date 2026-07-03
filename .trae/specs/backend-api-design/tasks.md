# 后端 API 架构设计 - 任务列表

## Phase 1: 数据源抽象层 + 分级缓存 + 统一响应

### 阶段目标
实现 akshare + mock 数据源、分级缓存、统一响应格式和字段标准化，不改变前端调用方式。

---

- [x] Task 1: 实现数据源抽象层（akshare + mock）
  - [x] SubTask 1.1: 创建 `services/base.py` — 定义 BaseDataSource 抽象基类（使用 ABC + abstractmethod）
  - [x] SubTask 1.2: 创建 `services/normalizer.py` — 字段标准化映射（中文→英文 snake_case），覆盖可转债和 LOF 字段
  - [x] SubTask 1.3: 创建 `services/mock_source.py` — 将现有 mock_data.py 改造为 MockSource 实现
  - [x] SubTask 1.4: 创建 `services/akshare_source.py` — 将现有 akshare 调用封装为 AkshareSource，输出经 normalizer 标准化的数据
  - [x] SubTask 1.5: 创建 `services/factory.py` — 工厂函数 + 自动降级逻辑（akshare → mock）+ CircuitBreaker 熔断器
  - [x] SubTask 1.6: 在 `app.py` 添加 `/api/v1/admin/switch-source` 和 `/api/v1/admin/health` 路由

- [x] Task 2: 实现分级缓存系统
  - [x] SubTask 2.1: 创建 `services/cache.py` — 实现 `get_cache_ttl()`、`is_trading_hours()`、`build_cache_key()`
  - [x] SubTask 2.2: 实现 `get_with_cache_lock()` — 缓存防穿透（Cache Lock），避免缓存过期时多请求同时回源
  - [x] SubTask 2.3: 本地开发使用 fakeredis，生产用真实 Redis，通过环境变量切换
  - [x] SubTask 2.4: 在各接口路由中集成缓存逻辑，支持 `?refresh=true` 强制刷新

- [x] Task 3: 统一 Flask 后端响应格式
  - [x] SubTask 3.1: 创建 `utils/response.py` — 实现 `api_response()` 和 `api_error()` 工具函数
  - [x] SubTask 3.2: 改造 `app.py` 所有路由，使用 `/api/v1/` 前缀和统一响应格式
  - [x] SubTask 3.3: 实现错误码体系（INVALID_PARAMS / RATE_LIMITED / DATA_SOURCE_ERROR 等）
  - [x] SubTask 3.4: 集成接口限流（公共接口 60/min，写接口 20/min）— 使用自定义 RateLimiter
  - [x] SubTask 3.5: 配置结构化 JSON 日志（JsonFormatter）

- [x] Task 4: 完善可转债数据服务
  - [x] SubTask 4.1: 实现 `get_convertible_detail(code)` — 包含纯债价值、到期收益、评级、转股价修正历史
  - [x] SubTask 4.2: 实现 `get_new_bonds()` — 新债/申购中可转债
  - [x] SubTask 4.3: 列表接口支持筛选参数（exchange, min_price, max_price, max_premium, sort, page）
  - [x] SubTask 4.4: 补充 akshare 获取更完整字段（评级、到期日期、担保方式等）

- [x] Task 5: 实现市场情绪与资金流向
  - [x] SubTask 5.1: 在 AkshareSource 和 MockSource 中实现 `get_market_sentiment()` — 上证/深证评分、成交量、涨跌家数
  - [x] SubTask 5.2: 在 AkshareSource 和 MockSource 中实现 `get_fund_flow()` — 北向资金和主力板块资金流向
  - [x] SubTask 5.3: 在 `app.py` 添加 `/api/v1/market/sentiment` 和 `/api/v1/market/fund-flow` 路由

- [x] Task 6: 扩展云函数 market 的 action
  - [x] SubTask 6.1: 添加 `convertibleDetail` action
  - [x] SubTask 6.2: 添加 `convertibleNewBonds` action
  - [x] SubTask 6.3: 添加 `sentiment` action
  - [x] SubTask 6.4: 添加 `fundFlow` action
  - [x] SubTask 6.5: 完善 `health` action，返回数据源可用状态

- [x] Task 7: 更新 Mock 数据
  - [x] SubTask 7.1: 更新 MockSource 的 market_sentiment 数据（包含 sh_score/sz_score/north 等）
  - [x] SubTask 7.2: 更新 MockSource 的 fund_flow 数据（包含 north/sh/sz）
  - [x] SubTask 7.3: 确保所有 Mock 数据字段与 normalizer 标准化后的真实数据完全一致

---

## Phase 2: CloudRun 接入前端 + efinance 备用源

### 阶段目标
前端调用 CloudRun HTTP API，云函数降级；增加 efinance 作为 akshare 备用源。

---

- [x] Task 8: 重构 cloudApi.js 调用链
  - [x] SubTask 8.1: 添加 HTTP 调用逻辑（优先 CloudRun `/api/v1/` 接口）
  - [x] SubTask 8.2: 实现自动降级链：HTTP（5s 超时）→ 云函数 → 本地 Mock
  - [x] SubTask 8.3: 透传 `meta.source` 标记供前端展示数据来源

- [x] Task 9: 增加 efinance 备用数据源
  - [x] SubTask 9.1: 创建 `services/efinance_source.py` — 实现 EfinanceSource
  - [x] SubTask 9.2: 在 factory.py 中将 efinance 加入降级链：akshare → efinance → mock
  - [x] SubTask 9.3: 为 efinance 添加 CircuitBreaker 熔断器

- [x] Task 10: 前端适配统一响应格式
  - [x] SubTask 10.1: 更新首页 index.js 识别 `meta.source`，显示数据来源标识
  - [x] SubTask 10.2: 更新 convertible/index.js 适配新响应格式和英文字段名
  - [x] SubTask 10.3: 更新 lof/index.js 和 hkipo/index.js 适配新响应格式
  - [x] SubTask 10.4: 移除各页面内的 `loadMockData()` 硬编码

- [x] Task 11: CloudRun 部署配置
  - [x] SubTask 11.1: 更新 Dockerfile 优化镜像大小
  - [x] SubTask 11.2: 更新 requirements.txt 锁定版本
  - [x] SubTask 11.3: 添加 `/api/v1/admin/health` 端点
  - [x] SubTask 11.4: 更新 uploadCloudFunction.sh 脚本

---

## Phase 3: 用户数据持久化 + tushare 数据源（可选）

### 阶段目标
接入 MySQL 存储用户数据，实现 openid 鉴权；增加 tushare 数据源。

---

- [x] Task 12: 数据库设计与用户认证
  - [x] SubTask 12.1: 设计 MySQL 表（user_favorites / user_reminders / user_settings）+ 迁移脚本
  - [x] SubTask 12.2: 添加数据库连接池（SQLAlchemy）
  - [x] SubTask 12.3: 实现 `/api/v1/user/login`（微信 code2Session 获取 openid）
  - [x] SubTask 12.4: 中间件鉴权：所有 `/api/v1/user/*` 接口需带 openid

- [x] Task 13: 用户数据 CRUD API
  - [x] SubTask 13.1: 实现 `/api/v1/user/favorites` 增删改查
  - [x] SubTask 13.2: 实现 `/api/v1/user/reminders` 增删改查
  - [x] SubTask 13.3: 实现 `/api/v1/user/settings` 读写
  - [x] SubTask 13.4: 前端 favoriteManager.js 改造为调用后端 API（新增 Async 版本，优先调用后端，失败时 fallback 到本地缓存）

- [x] Task 14: 增加 tushare 数据源
  - [x] SubTask 14.1: 创建 `services/tushare_source.py` — 实现 TushareSource（需 token）
  - [x] SubTask 14.2: 在 factory.py 中将 tushare 加入降级链
  - [x] SubTask 14.3: 环境变量配置 tushare token

---

## 开发调试指南（开发完成后提供）

> 以下为开发完成后的调试指导，不属于开发任务，在 Phase 1/2 完成后提供：
> - 本地开发环境搭建（Python 3.10+ / fakeredis / Flask debug 模式）
> - 数据源切换调试（环境变量 `DATA_SOURCE=mock python app.py`）
> - 云函数上传与调试（uploadCloudFunction.sh / 微信开发者工具云端调试）
> - CloudRun 部署（Docker 构建 / 腾讯云控制台 / 环境变量配置）
> - 小程序联调（Network 面板 / 域名校验 / 降级链验证）

---

## Task Dependencies

```
Phase 1:
  Task 1 (数据源抽象层) ──→ Task 4 (可转债完善) ──→ Task 6 (云函数扩展)
      │                    ──→ Task 5 (市场情绪) ──↗
  Task 2 (分级缓存)    ──→ Task 4, Task 5
  Task 3 (统一响应)    ──→ Task 4, Task 5
  Task 6 (云函数)      ──→ Task 7 (Mock更新) ──→ Phase 2

Phase 2:
  Task 11 (CloudRun部署) ──→ Task 8 (cloudApi重构) ──→ Task 10 (前端适配)
  Task 9 (efinance源)   ──→ 独立，可与 Task 8 并行

Phase 3 (可选):
  Task 12 ──→ Task 13
  Task 14 (tushare) ──→ 独立
```
