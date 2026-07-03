# 旺财百宝箱 - 后端 API 架构设计规范

## Why

当前项目采用"微信云函数 + 本地 Flask 后端 + akshare 数据源"的混合架构：
- 云函数 `market` 封装了 akshare 调用，提供 Mock 数据兜底
- `cloudrun/` 下 Flask 服务作为云托管后端，提供 HTTP REST API
- `cloudApi.js` 通过 `wx.cloud.callFunction` 调用云函数

但当前架构存在以下问题：
1. **数据源分散**：可转债用 akshare 的 `bond_cb_jsl`，LOF 用 `fund_lof_spot_em`，港股IPO用 `stock_hk_ipo_info_em`，各模块独立获取数据，没有统一的数据层
2. **缓存缺失**：每次请求都实时爬取，无缓存机制，响应慢且容易被限流
3. **缺少用户数据层**：自选、提醒等数据仅存在小程序本地Storage，无法跨设备同步
4. **CloudRun 接口未接入前端**：前端实际只走云函数，CloudRun 的 `/api/*` 接口未被调用
5. **错误处理不一致**：Mock 数据的 fallback 逻辑散落在各页面和各层
6. **市场情绪/资金流向等数据缺失**：首页展示的 `market_sentiment`、`fund_flow` 目前是写死的 Mock 数据
7. **字段命名混乱**：部分接口返回中文 key（`转债价格`、`转股溢价率`），部分返回英文 key（`price`、`premium_rate`），前端需要大量兼容逻辑

## What Changes

### 1. 数据层架构

```
┌─────────────────────────────────────────────────────┐
│                    前端 (微信小程序)                    │
│  cloudApi.js / wx.cloud.callFunction / wx.request   │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP / 云函数
┌──────────────────────▼──────────────────────────────┐
│               API 网关层 (Flask)                      │
│   /api/v1/market/*  /api/v1/convertible/*           │
│   /api/v1/lof/*     /api/v1/hkipo/*                 │
│   /api/v1/user/*    /api/v1/stock/*                 │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│              数据服务层 (Services)                     │
│   base.py (抽象基类)                                  │
│   akshare_source.py  mock_source.py                  │
│   factory.py (工厂 + 自动降级 + 熔断)                  │
│   normalizer.py (字段标准化)                          │
└──────────────────────┬──────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                              │
┌───────▼────────┐          ┌──────────▼────────┐
│  数据源 (akshare) │          │   Redis Cache     │
│  + 免费数据接口   │          │  (分级 TTL)       │
└─────────────────┘          └───────────────────┘
        │
┌───────▼────────────────────────────────────────┐
│              用户数据 (MySQL)                      │
│   user_favorites  user_reminders  user_settings │
└─────────────────────────────────────────────────┘
```

### 2. API 版本管理

所有接口统一添加 `/api/v1/` 前缀，便于未来不兼容升级：

```
/api/v1/convertible/list    ← 当前版本
/api/v2/convertible/list    ← 未来大版本升级
```

云函数 action 保持不变（`convertibleList` 等），通过 `cloudApi.js` 内部映射到对应的 HTTP 路径。

### 3. 接口模块规划

#### 3.1 市场概览 API (`/api/v1/market/`)

| 接口 | 方法 | 说明 | 缓存 TTL |
|------|------|------|----------|
| `/api/v1/market/overview` | GET | 综合市场概览（可转债+LOF+港股+情绪+资金流向） | 5min |
| `/api/v1/market/sentiment` | GET | A股市场情绪（上证/深证/北向资金/板块流向） | 5min |
| `/api/v1/market/fund-flow` | GET | 主力资金流向（板块/北向/南北向） | 5min |
| `/api/v1/market/hot-sectors` | GET | 热门板块排行 | 10min |

#### 3.2 可转债 API (`/api/v1/convertible/`)

| 接口 | 方法 | 说明 | 缓存 TTL |
|------|------|------|----------|
| `/api/v1/convertible/list` | GET | 可转债完整列表（支持分页、筛选、排序） | 15min |
| `/api/v1/convertible/signals` | GET | 可转债信号（双低/强赎/折价/下修博弈） | 15min |
| `/api/v1/convertible/temperature` | GET | 可转债市场温度（价格/溢价率/双低中位数） | 15min |
| `/api/v1/convertible/detail/<code>` | GET | 单只可转债详情 | 12h |
| `/api/v1/convertible/new-bonds` | GET | 新上市/申购中可转债 | 5min |

**筛选参数**：
- `sort`: `double_low` / `price` / `premium` / `premium_desc`
- `exchange`: `sh` / `sz` / `bj`
- `min_price` / `max_price`: 价格区间
- `max_premium`: 最高溢价率
- `page` / `page_size`: 分页
- `refresh`: `true` 时强制刷新绕过缓存

#### 3.3 LOF基金 API (`/api/v1/lof/`)

| 接口 | 方法 | 说明 | 缓存 TTL |
|------|------|------|----------|
| `/api/v1/lof/list` | GET | LOF基金列表（溢价率排序） | 15min |
| `/api/v1/lof/opportunities` | GET | LOF套利机会（高溢价/折价） | 15min |
| `/api/v1/lof/summary` | GET | LOF市场概览 | 15min |
| `/api/v1/lof/detail/<code>` | GET | 单只LOF详情 | 12h |

#### 3.4 港股IPO API (`/api/v1/hkipo/`)

| 接口 | 方法 | 说明 | 缓存 TTL |
|------|------|------|----------|
| `/api/v1/hkipo/list` | GET | 港股IPO完整列表 | 30min |
| `/api/v1/hkipo/upcoming` | GET | 申购中/即将上市 | 30min |
| `/api/v1/hkipo/summary` | GET | 港股打新市场概览 | 30min |
| `/api/v1/hkipo/detail/<code>` | GET | 单只IPO详情 | 12h |

#### 3.5 用户数据 API (`/api/v1/user/`)

| 接口 | 方法 | 说明 | 数据存储 |
|------|------|------|----------|
| `/api/v1/user/login` | POST | 小程序登录（获取openid） | MySQL |
| `/api/v1/user/favorites` | GET/POST/DELETE | 自选股管理 | MySQL |
| `/api/v1/user/reminders` | GET/POST/PUT/DELETE | 申购提醒管理 | MySQL |
| `/api/v1/user/settings` | GET/PUT | 用户设置（主题/默认页/提醒偏好） | MySQL |

#### 3.6 正股/行情 API (`/api/v1/stock/`)

| 接口 | 方法 | 说明 | 缓存 TTL |
|------|------|------|----------|
| `/api/v1/stock/profile/<code>` | GET | 正股基本信息 | 24h |
| `/api/v1/stock/quote/<code>` | GET | 正股实时行情 | 1min |

#### 3.7 管理接口 (`/api/v1/admin/`)

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/admin/switch-source` | POST | 切换数据源（需鉴权） |
| `/api/v1/admin/cache/clear` | POST | 清除指定模块缓存 |
| `/api/v1/admin/health` | GET | 详细健康检查（各数据源状态 + 缓存状态） |

### 4. 统一响应格式

```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "cached": true,
    "cache_expire_at": "2026-06-24T10:30:00+08:00",
    "source": "akshare",
    "update_time": "2026-06-24T10:25:00+08:00"
  }
}
```

错误响应：
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "DATA_SOURCE_ERROR",
    "message": "数据源暂时不可用"
  }
}
```

#### 错误码体系

| 错误码 | HTTP 状态 | 说明 |
|--------|-----------|------|
| `INVALID_PARAMS` | 400 | 请求参数错误 |
| `UNAUTHORIZED` | 401 | 未授权（缺少 openid 或 token 无效） |
| `RATE_LIMITED` | 429 | 请求过于频繁，被限流 |
| `DATA_SOURCE_ERROR` | 502 | 数据源请求失败 |
| `DATA_SOURCE_TIMEOUT` | 504 | 数据源响应超时 |
| `INTERNAL_ERROR` | 500 | 服务器内部错误 |
| `NOT_FOUND` | 404 | 请求的资源不存在 |

### 5. 字段命名规范

**统一使用英文 snake_case**，后端负责将数据源的中文字段标准化为英文。

#### 可转债字段映射

| 数据源原始字段（中文） | 标准化字段（英文） | 类型 | 说明 |
|------------------------|---------------------|------|------|
| 转债代码 | bond_code | string | |
| 转债名称 | bond_name | string | |
| 转债价格 | price | float | |
| 正股代码 | stock_code | string | |
| 正股名称 | stock_name | string | |
| 转股价值 | conversion_value | float | |
| 转股溢价率 | premium_rate | float | 百分比 |
| 双低 | double_low | float | |
| 纯债价值 | pure_bond_value | float | |
| 转股价 | conversion_price | float | |
| 正股价 | stock_price | float | |
| 交易所 | exchange | string | sh/sz/bj |
| 评级 | rating | string | |
| 到期日期 | maturity_date | string | YYYY-MM-DD |

#### LOF 字段映射

| 原始字段 | 标准化字段 | 类型 |
|----------|------------|------|
| 代码 | code | string |
| 名称 | name | string |
| 最新价 | price | float |
| 涨跌幅 | change_pct | float |
| 估值 | valuation | float |
| 溢价率 | premium | float |
| 连续溢价天数 | consecutive_premium | int |
| 申购状态 | limit_status | string |

**标准化层**（`services/normalizer.py`）负责将各数据源返回的字段统一映射为上述标准字段，前端只需对接一套字段名。

### 6. 分级缓存策略

#### 数据分级表

| 数据类型 | 示例 | 更新频率 | 交易时段 TTL | 非交易时段 TTL |
|----------|------|----------|--------------|----------------|
| **T+0 实时** | 正股实时行情、可转债现价 | 秒级~1分钟 | 30-60s | 4h |
| **日内快照** | 市场情绪、资金流向、板块热度 | 每5分钟 | 3-5min | 4h |
| **日线数据** | 可转债列表、LOF基金列表、港股IPO | 交易日收盘后 | 15-30min | 4h |
| **日终数据** | 市场温度、可转债信号、LOF套利机会 | 每日收盘后 | 4-8h | 8h |
| **低频数据** | 可转债详情（条款）、正股基本信息 | 几天~几周 | 12h | 12h |

#### 智能缓存刷新

```python
from datetime import datetime, time

CACHE_TTL_CONFIG = {
    # T+0 实时数据
    'stock_quote':           30,
    'convertible_quote':     60,

    # 日内快照
    'market_sentiment':      300,
    'fund_flow':             300,
    'hot_sectors':           600,

    # 日线数据
    'convertible_list':      900,
    'lof_list':              900,
    'hk_ipo_list':           1800,

    # 日终数据
    'convertible_temperature': 28800,
    'convertible_signals':     28800,
    'lof_opportunities':       28800,

    # 低频数据
    'convertible_detail':    43200,
    'lof_summary':           28800,
    'hk_ipo_summary':        43200,
    'stock_profile':         86400,
}

def is_trading_hours():
    """判断是否在 A 股交易时间内"""
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    current_time = now.time()
    morning = time(9, 15) <= current_time <= time(11, 30)
    afternoon = time(13, 0) <= current_time <= time(15, 5)
    return morning or afternoon

def get_cache_ttl(data_type: str) -> int:
    """根据数据类型和交易时段返回合适的 TTL"""
    base_ttl = CACHE_TTL_CONFIG.get(data_type, 300)
    if not is_trading_hours():
        # 非交易时段：日线及日终数据延长到 4h
        if data_type in ['convertible_list', 'lof_list', 'convertible_temperature',
                         'convertible_signals', 'lof_opportunities', 'market_sentiment',
                         'fund_flow', 'hot_sectors']:
            return min(base_ttl * 4, 14400)
    return base_ttl
```

#### 缓存 Key 设计

```python
def build_cache_key(module: str, action: str, **params) -> str:
    """统一缓存 Key 格式: module:action:param1=val1:param2=val2"""
    parts = [module, action]
    if params:
        sorted_params = sorted(params.items())
        param_str = ':'.join(f"{k}={v}" for k, v in sorted_params if v is not None)
        if param_str:
            parts.append(param_str)
    return ':'.join(parts)

# 示例: 'convertible:list:exchange=sh:sort=double_low:page=1'
```

#### 缓存防穿透（Cache Lock）

当缓存过期时，多个请求同时回源会导致数据源压力骤增。使用简单的锁机制：

```python
import threading
import time

_cache_locks = {}
_cache_locks_guard = threading.Lock()

def get_with_cache_lock(cache_key, fetch_func, ttl):
    """带缓存锁的获取数据：缓存未命中时只允许一个请求回源"""
    cached = cache.get(cache_key)
    if cached:
        return cached, True  # data, from_cache

    # 获取锁
    with _cache_locks_guard:
        if cache_key not in _cache_locks:
            _cache_locks[cache_key] = threading.Lock()
        lock = _cache_locks[cache_key]

    if lock.acquire(blocking=False):
        try:
            # 双重检查：可能其他线程已经更新了缓存
            cached = cache.get(cache_key)
            if cached:
                return cached, True
            # 回源获取数据
            data = fetch_func()
            cache.set(cache_key, data, ttl)
            return data, False
        finally:
            lock.release()
    else:
        # 等待其他线程完成（最多等 3 秒）
        for _ in range(30):
            time.sleep(0.1)
            cached = cache.get(cache_key)
            if cached:
                return cached, True
        # 超时仍无数据，直接回源（降级处理）
        data = fetch_func()
        cache.set(cache_key, data, ttl)
        return data, False
```

#### 强制刷新

前端下拉刷新时传 `?refresh=true`，后端绕过缓存直接回源。

### 7. 多数据源切换机制

#### 分阶段实现策略

| 阶段 | 实现的数据源 | 说明 |
|------|-------------|------|
| Phase 1 | `akshare` + `mock` | 先跑通核心链路，akshare 为主，mock 兜底 |
| Phase 2 | 增加 `efinance` | 作为 akshare 的备用源，akshare 限流时自动切换 |
| Phase 3 | 增加 `tushare` | 需 token，作为高级数据源补充 |

#### 数据源对比

| 数据源 | 可转债 | LOF | 港股IPO | 市场情绪 | 资金流向 | 是否需Token |
|--------|--------|-----|---------|----------|----------|-------------|
| `akshare` | ✅ bond_cb_jsl | ✅ fund_lof_spot_em | ✅ stock_hk_ipo_info_em | ✅ | ✅ | 否 |
| `efinance` | ✅ | ✅ | ✅ | ✅ | ✅ | 否 |
| `tushare` | ✅ cb_basic | ✅ | ✅ | ✅ | ✅ | 是 |
| `mock` | ✅ | ✅ | ✅ | ✅ | ✅ | 否 |

#### 数据源选择方式

```python
# 环境变量
DATA_SOURCE = os.environ.get('DATA_SOURCE', 'akshare')
FALLBACK_SOURCE = os.environ.get('FALLBACK_SOURCE', 'efinance')
```

#### 架构

```
services/
├── base.py              # 抽象基类 BaseDataSource
├── akshare_source.py    # akshare 实现
├── efinance_source.py   # efinance 实现（Phase 2）
├── tushare_source.py    # tushare 实现（Phase 3）
├── mock_source.py       # Mock 实现
├── normalizer.py        # 字段标准化（中文→英文 snake_case）
└── factory.py           # 工厂 + 自动降级 + 熔断
```

#### 统一数据源接口

```python
from abc import ABC, abstractmethod

class BaseDataSource(ABC):
    """数据源抽象基类，所有数据源必须实现此接口"""

    @abstractmethod
    def get_convertible_list(self, **kwargs) -> list:
        pass

    @abstractmethod
    def get_convertible_signals(self) -> dict:
        pass

    @abstractmethod
    def get_convertible_detail(self, code: str) -> dict:
        pass

    @abstractmethod
    def get_convertible_temperature(self) -> dict:
        pass

    @abstractmethod
    def get_lof_list(self, **kwargs) -> list:
        pass

    @abstractmethod
    def get_lof_opportunities(self) -> dict:
        pass

    @abstractmethod
    def get_hk_ipo_list(self, **kwargs) -> list:
        pass

    @abstractmethod
    def get_hk_ipo_upcoming(self) -> list:
        pass

    @abstractmethod
    def get_market_sentiment(self) -> dict:
        pass

    @abstractmethod
    def get_fund_flow(self) -> dict:
        pass

    @abstractmethod
    def health_check(self) -> dict:
        pass
```

#### 自动降级 + 熔断

```
请求 → Primary 数据源 → 成功 → 返回
                    ↓ (失败/超时)
            Fallback 数据源 → 成功 → 返回
                    ↓ (失败)
            Mock 数据 → 返回 + 标记 source=mock
```

**熔断机制**：当某数据源连续失败 5 次，标记为"熔断"状态（持续 60 秒），期间直接跳过该源，避免无效等待。

```python
class CircuitBreaker:
    """简单的熔断器"""
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = None
        self.state = 'closed'  # closed / open / half_open

    def can_call(self):
        if self.state == 'open':
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = 'half_open'
                return True
            return False
        return True

    def record_success(self):
        self.failure_count = 0
        self.state = 'closed'

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = 'open'
```

### 8. 接口限流

保护数据源和服务器，对 API 进行限流：

```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# 公共数据接口：每分钟 60 次
@app.route('/api/v1/convertible/list')
@limiter.limit('60/minute')
def convertible_list():
    ...

# 实时行情接口：每分钟 120 次
@app.route('/api/v1/stock/quote/<code>')
@limiter.limit('120/minute')
def stock_quote(code):
    ...

# 用户写接口：每分钟 20 次
@app.route('/api/v1/user/favorites', methods=['POST'])
@limiter.limit('20/minute')
def add_favorite():
    ...
```

### 9. 结构化日志

```python
import logging
import json

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'message': record.getMessage(),
            'module': record.module,
            'line': record.lineno,
        }
        if hasattr(record, 'extra_data'):
            log_data.update(record.extra_data)
        return json.dumps(log_data, ensure_ascii=False)

# 使用示例
logging.info('数据源切换', extra={'extra_data': {
    'source': 'akshare',
    'reason': 'circuit_breaker_open',
    'fallback': 'efinance'
}})
```

### 10. 现有架构迁移策略

**Phase 1（后端增强，不改变前端调用方式）**：
- 实现数据源抽象层（akshare + mock）
- 实现分级缓存系统
- 统一响应格式和字段命名
- 补充市场情绪、资金流向真实数据
- 扩展云函数 action

**Phase 2（CloudRun 接入前端）**：
- `cloudApi.js` 优先 HTTP 调用 CloudRun，降级到云函数
- 前端适配统一响应格式
- 增加 efinance 备用数据源

**Phase 3（数据持久化）**：
- 接入 MySQL 存储用户数据
- 实现 openid 鉴权
- 增加 tushare 数据源

## Impact

- **Affected specs**: 后端接口规范、数据缓存策略、字段命名规范、Mock 数据策略
- **Affected code**:
  - `cloudrun/app.py` - 新增路由、统一响应、限流
  - `cloudrun/services/*.py` - 数据源抽象层、缓存、标准化
  - `cloudfunctions/market/index.js` - 增加 action
  - `miniprogram/utils/cloudApi.js` - 支持 HTTP 降级
  - `miniprogram/config.js` - 云托管地址配置
  - 所有前端页面 - 字段名适配（中文→英文）

## ADDED Requirements

### Requirement: 统一响应格式

所有 API 必须返回标准化 JSON 结构，包含 `success`、`data`、`meta` 字段。

#### Scenario: 成功响应
- **WHEN** 前端请求 `/api/v1/convertible/list`
- **THEN** 返回 `{ success: true, data: {...}, meta: { source: "akshare", cached: false } }`

#### Scenario: 数据源失败回退
- **WHEN** akshare 请求失败时
- **THEN** 自动尝试备用数据源，所有源失败时返回 Mock 数据，`meta.source` 标记为 `"mock"`

### Requirement: 分级缓存机制

所有数据接口必须实现 Redis 缓存，按数据类型和交易时段设置不同 TTL。

#### Scenario: 缓存命中
- **WHEN** 请求数据且 Redis 中有未过期缓存
- **THEN** 直接返回缓存数据，`meta.cached = true`

#### Scenario: 缓存防穿透
- **WHEN** 缓存过期，多个请求同时到达
- **THEN** 只有一个请求回源，其余请求等待缓存更新后返回

#### Scenario: 非交易时段延长缓存
- **WHEN** 非交易时段请求可转债列表
- **THEN** 缓存 TTL 从 15 分钟延长到 4 小时

### Requirement: 字段命名标准化

后端统一返回英文 snake_case 字段名，通过标准化层将数据源中文字段映射为英文。

#### Scenario: 可转债列表字段
- **WHEN** 请求 `/api/v1/convertible/list`
- **THEN** 返回 `bond_code`、`bond_name`、`price`、`premium_rate` 等英文字段，而非 `转债代码`、`转债名称` 等中文字段

### Requirement: 数据源熔断

当某数据源连续失败超过阈值时，自动熔断该源，避免无效等待。

#### Scenario: 熔断触发
- **WHEN** akshare 连续失败 5 次
- **THEN** 标记为熔断状态（60 秒），期间直接使用备用源或 Mock

### Requirement: 接口限流

对 API 进行限流，保护数据源和服务器。

#### Scenario: 超出限流
- **WHEN** 单 IP 每分钟请求超过 60 次
- **THEN** 返回 429 状态码和 `RATE_LIMITED` 错误码

### Requirement: 可转债详情接口

云函数需新增 `convertibleDetail` action，返回单只可转债完整信息。

#### Scenario: 请求可转债详情
- **WHEN** 前端调用 `callMarket('convertibleDetail', { code: '118070' })`
- **THEN** 返回包含转股价、纯债价值、到期收益、评级等完整信息

### Requirement: 市场情绪数据

需实现真实的市场情绪数据接口，替代现有的写死 Mock 数据。

#### Scenario: 获取市场情绪
- **WHEN** 请求 `/api/v1/market/sentiment`
- **THEN** 返回上证/深证的情绪评分、成交量、涨跌家数、北向资金等

## MODIFIED Requirements

### Requirement: 云函数 action 扩展

**原状态**：云函数 `market` 只有 `overview`、`convertibleList`、`convertibleSignals`、`lofList`、`lofOpportunities`、`hkipoList`、`hkipoUpcoming` 这些 action。

**修改为**：增加以下 action：
- `convertibleDetail` - 可转债详情
- `convertibleNewBonds` - 新债/申购中
- `sentiment` - 市场情绪
- `fundFlow` - 资金流向
- `health` - 健康检查

### Requirement: 前端调用链优化

**原状态**：`cloudApi.js` 只调用云函数。

**修改为**：
```
callMarketSafe(action, data)
  → 先调用 CloudRun HTTP API (/api/v1/convertible/list 等)
  → 超时/失败时降级到 wx.cloud.callFunction
  → 云函数失败时使用本地 Mock 数据
```

## REMOVED Requirements

### Requirement: 页面内嵌 Mock 数据

**Reason**：各页面（index、convertible、lof、hkipo）内部都有大量 Mock 数据 fallback 逻辑，迁移后应统一由后端提供，前端只做展示。

**Migration**：将前端 `loadMockData()` 中的数据结构迁移到 `cloudrun/mock_data.py`，前端仅在完全无法获取数据时显示提示。

## 接口详细设计

### 1. `/api/v1/market/overview` 响应

```json
{
  "success": true,
  "data": {
    "convertible_bond": {
      "count": 520,
      "price_median": 129.40,
      "premium_median": 5.25,
      "double_low_median": 133.5,
      "market_status": "合理，可适当关注"
    },
    "lof_fund": {
      "count": 45,
      "premium_avg": 5.37,
      "top_premium": 15.67,
      "positive_count": 42,
      "positive_rate": 93.3,
      "paused_count": 12
    },
    "hk_ipo": {
      "upcoming_count": 3,
      "recent_count": 15,
      "avg_return": 18.5
    },
    "market_sentiment": {
      "sh_score": 58,
      "sz_score": 52,
      "north": 32.56,
      "sh_volume": 3256,
      "sz_volume": 4128
    },
    "fund_flow": {
      "north": 32.56,
      "sh": 18.32,
      "sz": 14.24
    }
  },
  "meta": {
    "cached": false,
    "source": "akshare",
    "update_time": "2026-06-24T10:25:00+08:00"
  }
}
```

### 2. `/api/v1/convertible/list` 响应

```json
{
  "success": true,
  "data": {
    "total": 520,
    "page": 1,
    "page_size": 100,
    "items": [
      {
        "bond_code": "118070",
        "bond_name": "南芯转债",
        "stock_code": "688484",
        "stock_name": "南芯科技",
        "exchange": "sh",
        "price": 100.00,
        "conversion_value": 122.95,
        "premium_rate": -18.66,
        "double_low": 81.34,
        "pure_bond_value": 95.50,
        "conversion_price": 83.28,
        "rating": "A+",
        "remaining_size": 9.85,
        "maturity_date": "2030-05-20"
      }
    ]
  },
  "meta": {
    "cached": true,
    "cache_expire_at": "2026-06-24T10:40:00+08:00",
    "source": "akshare"
  }
}
```

### 3. `/api/v1/convertible/signals` 响应

```json
{
  "success": true,
  "data": {
    "double_low": [],
    "force_redeem": [],
    "discount": [],
    "down_revised": []
  },
  "meta": {
    "cached": false,
    "source": "akshare",
    "update_time": "2026-06-24T10:25:00+08:00"
  }
}
```

### 4. `/api/v1/user/favorites` 接口

```
GET /api/v1/user/favorites?openid=xxx
POST /api/v1/user/favorites
Body: { "openid": "xxx", "code": "118070", "name": "南芯转债", "type": "bond", "price": 100.00, "premium_rate": -18.66 }
DELETE /api/v1/user/favorites?openid=xxx&code=118070&type=bond
```

响应：
```json
{
  "success": true,
  "data": {
    "total": 15,
    "items": [
      { "code": "118070", "name": "南芯转债", "type": "bond", "added_at": "2026-06-20T10:00:00+08:00" }
    ]
  }
}
```
