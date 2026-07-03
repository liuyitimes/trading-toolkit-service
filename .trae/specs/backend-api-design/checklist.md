# 后端 API 架构设计 - 验收清单

## Phase 1 验收

### 数据源抽象层
- [x] `services/base.py` 使用 ABC 定义 BaseDataSource，所有方法有 @abstractmethod 装饰
- [x] `services/normalizer.py` 包含可转债和 LOF 的完整字段映射表（中文→英文 snake_case）
- [x] `services/mock_source.py` 实现 BaseDataSource 全部方法，字段与 normalizer 标准一致
- [x] `services/akshare_source.py` 实现 BaseDataSource 全部方法，输出经 normalizer 标准化
- [x] `services/factory.py` 实现 `create_default_factory()` 工厂函数，支持 akshare/mock 切换
- [x] factory.py 实现自动降级：akshare 失败时自动切换到 efinance/tushare/mock
- [x] factory.py 实现 CircuitBreaker 熔断器（连续失败 5 次熔断 60 秒）
- [x] `/api/v1/admin/switch-source` 支持手动切换数据源
- [x] `/api/v1/admin/health` 返回各数据源可用状态和缓存状态
- [x] 所有数据源实现 `health_check()` 方法

### 分级缓存系统
- [x] `services/cache.py` 的 `get_cache_ttl()` 按数据类型返回不同 TTL
- [x] `is_trading_hours()` 正确判断 A 股交易时间（工作日 9:15-11:30, 13:00-15:05）
- [x] 非交易时段自动延长缓存 TTL（日线数据 15min → 4h）
- [x] `build_cache_key()` 统一格式 `module:action:param=val`，参数排序保证一致性
- [x] `get_with_cache_lock()` 实现缓存防穿透：缓存未命中时只有一个请求回源
- [x] 所有接口支持 `?refresh=true` 强制刷新绕过缓存
- [x] 本地开发使用 fakeredis，不依赖真实 Redis 服务
- [ ] **性能指标**：缓存命中时响应时间 < 50ms（需实际部署验证）

### 统一响应格式
- [x] 所有 `/api/v1/*` 路由返回 `{ success, data, meta }` 三字段结构
- [x] `meta.source` 正确标记为 `akshare` / `cache` / `mock`
- [x] `meta.cached` 布尔值标识是否来自缓存
- [x] `meta.cache_expire_at` 存在且格式为 ISO8601（带时区 +08:00）
- [x] 错误响应格式为 `{ success: false, data: null, error: { code, message } }`
- [x] 错误码体系完整：INVALID_PARAMS(400) / UNAUTHORIZED(401) / RATE_LIMITED(429) / DATA_SOURCE_ERROR(502) / DATA_SOURCE_TIMEOUT(504) / INTERNAL_ERROR(500) / NOT_FOUND(404)
- [x] 接口限流生效：公共接口 60/min，写接口 20/min（使用自定义 RateLimiter，非 flask-limiter）
- [x] 超出限流返回 429 + `RATE_LIMITED` 错误码
- [x] 结构化 JSON 日志正常输出（包含 timestamp/level/message/module）

### 字段命名标准化
- [x] 可转债接口返回英文字段：bond_code, bond_name, price, premium_rate, double_low, conversion_value 等
- [x] LOF 接口返回英文字段：code, name, price, change_pct, premium, consecutive_premium 等
- [x] 不再出现中文字段名（如 `转债代码`、`转股溢价率`）— normalizer 统一转换
- [x] exchange 字段统一为 sh/sz/bj（非"沪"/"深"/"京"）

### 可转债数据服务
- [x] `get_convertible_detail(code)` 返回完整详情（含评级/纯债价值/到期收益/转股价）
- [x] `get_new_bonds()` 返回当前申购中/新上市的可转债
- [x] 列表接口支持 exchange、min_price、max_price、max_premium 筛选
- [x] 列表接口支持 double_low / price / premium / premium_desc 排序
- [x] 列表接口支持 page + page_size 分页
- [ ] **性能指标**：akshare 回源响应时间 < 3s（需实际部署验证）

### 市场情绪与资金流向
- [x] AkshareSource 的 `get_market_sentiment()` 从 akshare 获取上证/深证情绪评分
- [x] AkshareSource 的 `get_fund_flow()` 从 akshare 获取北向资金数据
- [x] `/api/v1/market/sentiment` 路由返回 sh_score, sz_score, sh_volume, sz_volume, north
- [x] `/api/v1/market/fund-flow` 路由返回 north, sh, sz

### 云函数扩展
- [x] `market` 云函数支持 `convertibleDetail` action
- [x] `market` 云函数支持 `convertibleNewBonds` action
- [x] `market` 云函数支持 `sentiment` action
- [x] `market` 云函数支持 `fundFlow` action
- [x] `health` action 返回数据源可用状态

### Mock 数据
- [x] MockSource 的 market_sentiment 包含 sh_score, sz_score, sh_volume, sz_volume, north
- [x] MockSource 的 fund_flow 包含 north, sh, sz
- [x] 所有 Mock 数据字段与 normalizer 标准化后的真实数据完全一致

## Phase 2 验收

### cloudApi.js 重构
- [x] HTTP 调用优先（CloudRun `/api/v1/` 接口），5s 超时自动降级
- [x] HTTP 失败后调用云函数
- [x] 云函数失败后使用本地 Mock 数据
- [x] 响应中携带 `meta.source` 标记，前端可识别数据来源
- [ ] 微信开发者工具控制台不报 "不在合法域名列表中" 错误（需在开发者工具中验证）

### efinance 备用数据源
- [x] `services/efinance_source.py` 实现 BaseDataSource 全部方法
- [x] factory.py 降级链为：akshare → efinance → tushare → mock
- [x] efinance 有独立的 CircuitBreaker 熔断器
- [x] akshare 熔断时自动切换到 efinance

### 前端适配
- [x] 首页 index.js 正确展示数据来源标识（真实数据 / 缓存 / Mock 兜底）
- [x] convertible/index.js 使用英文字段名（bond_code, price, premium_rate 等）
- [x] lof/index.js 和 hkipo/index.js 使用英文字段名
- [x] 各页面不再有硬编码的 `loadMockData()` 作为主要数据源

### CloudRun 部署
- [x] Dockerfile 存在且配置合理
- [x] requirements.txt 锁定关键依赖版本（flask, akshare, redis）
- [x] `/api/v1/admin/health` 端点返回 `{ status, sources, cache }` 状态
- [x] `uploadCloudFunction.sh` 可一键部署云函数
- [ ] **性能指标**：CloudRun 冷启动 < 5s，热请求 < 200ms（需实际部署验证）

## Phase 3 验收

### 数据库设计
- [x] user_favorites 表含 openid, code, name, type, added_at，openid+code+type 有唯一索引
- [x] user_reminders 表含 openid, code, type, remind_time, enabled
- [x] user_settings 表含 openid, theme, default_tab, remind_preferences

### 用户认证
- [x] `/api/v1/user/login` 通过微信 code2Session 获取 openid
- [x] 所有 `/api/v1/user/*` 接口正确校验 openid
- [x] 未携带 openid 返回 401 + `UNAUTHORIZED` 错误码

### 用户数据 API
- [x] 自选股增删改查功能正常
- [x] 提醒管理增删改查功能正常
- [x] 用户设置读写功能正常
- [x] favoriteManager.js 改造后调用后端 API（新增 Async 版本，优先调用后端，失败时 fallback 到本地缓存）

### tushare 数据源
- [x] `services/tushare_source.py` 实现 BaseDataSource 全部方法
- [x] tushare token 通过环境变量配置，不硬编码
- [x] factory.py 降级链为：akshare → efinance → tushare → mock
