# Trading Toolkit Service — 后端开发文档

> 最后更新：2026-07-09

---

## 1. 项目概述

Python 后端服务，基于 **Flask** 框架，提供可转债、LOF 基金、港股打新、封闭式基金等模块的数据 API。支持多数据源降级、分级缓存、接口限流、结构化日志。

### 技术栈

| 领域 | 选型 |
|------|------|
| Web 框架 | Flask + Flask-CORS |
| 数据处理 | pandas |
| 数据源 | 新浪财经、东方财富（直连 HTTP） |
| 缓存 | fakeredis（本地）/ Redis（生产） |
| 数据库 | SQLite（本地）/ MySQL（生产） |
| 部署 | Docker + Google Cloud Run |

---

## 2. 目录结构

```
cloudrun/
├── app.py                  — Flask 应用入口、路由定义、缓存预热
├── mock_data.py            — Mock 数据生成
├── requirements.txt        — Python 依赖
├── Dockerfile              — Docker 构建文件
├── services/               — 数据服务层
│   ├── base.py             — 数据源基类
│   ├── factory.py          — 数据源工厂（DirectSource 调用门面）
│   ├── cache.py            — 缓存管理器（TTL、SWR、预热）
│   ├── http_client.py      — HTTP 客户端（sina_get、em_get、jsl_post）
│   ├── convertible_bond.py — 可转债数据服务
│   ├── lof_fund.py         — LOF 基金数据服务
│   ├── lof_arbitrage.py    — LOF 套利分析
│   ├── hk_ipo.py           — 港股打新数据服务
│   ├── closed_end.py       — 封闭式基金数据服务
│   ├── direct_source.py    — 直连数据源实现
│   ├── normalizer.py       — 字段标准化
│   └── auth.py             — 认证服务（微信 openid）
├── models/                 — 数据模型
│   ├── database.py         — 数据库连接管理
│   └── user.py             — 用户模型（自选、提醒、设置）
└── utils/                  — 工具模块
    ├── response.py         — 统一响应格式
    ├── convert.py          — 类型转换（safe_float 等）
    ├── limiting.py         — 接口限流
    └── logging.py          — 结构化日志
```

---

## 3. API 端点清单

所有接口统一前缀 `/api/v1/`，返回格式：

```json
{
  "success": true,
  "data": { ... },
  "meta": { "cached": true, "source": "sina+em", "update_time": "..." }
}
```

### 3.1 市场概览

| 方法 | 路径 | 说明 | 缓存 TTL |
|------|------|------|----------|
| GET | `/api/v1/market/overview` | 综合市场概览 | 60s |
| GET | `/api/v1/market/sentiment` | 市场情绪 | 60s |
| GET | `/api/v1/market/fund-flow` | 资金流向 | 60s |

### 3.2 可转债

| 方法 | 路径 | 说明 | 缓存 TTL |
|------|------|------|----------|
| GET | `/api/v1/convertible/list` | 可转债列表（筛选/排序/分页） | 60s |
| GET | `/api/v1/convertible/signals` | 策略信号（双低/强赎/折价/下修） | 60s |
| GET | `/api/v1/convertible/temperature` | 市场温度 | 60s |
| GET | `/api/v1/convertible/detail/<code>` | 单只转债详情 | 43200s |
| GET | `/api/v1/convertible/pending` | **待发/配售转债列表** | **1800s（30分钟）** |

### 3.3 LOF 基金

| 方法 | 路径 | 说明 | 缓存 TTL |
|------|------|------|----------|
| GET | `/api/v1/lof/list` | LOF 基金列表 | 60s |
| GET | `/api/v1/lof/opportunities` | 套利机会 | 60s |
| GET | `/api/v1/lof/summary` | 市场概览 | 1800s |
| GET | `/api/v1/lof/<code>/share-history` | 份额历史（7日） | 不缓存 |
| GET | `/api/v1/lof/<code>/arbitrage-predict` | 套利资金预测 | 不缓存 |

### 3.4 港股打新

| 方法 | 路径 | 说明 | 缓存 TTL |
|------|------|------|----------|
| GET | `/api/v1/hkipo/list` | IPO 列表 | 60s |
| GET | `/api/v1/hkipo/upcoming` | 申购中/即将上市 | 60s |
| GET | `/api/v1/hkipo/summary` | 打新市场概览 | 1800s |
| GET | `/api/v1/hkipo/detail/<code>` | 新股详情 | 60s |

### 3.5 封闭式基金

| 方法 | 路径 | 说明 | 缓存 TTL |
|------|------|------|----------|
| GET | `/api/v1/closed-end/list` | 封闭式基金列表 | 60s |
| GET | `/api/v1/closed-end/summary` | 市场概览 | 1800s |

### 3.6 用户系统

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/user/login` | 登录（获取 openid） |
| GET/POST/DELETE | `/api/v1/user/favorites` | 自选管理 |
| GET/POST/PUT/DELETE | `/api/v1/user/reminders` | 提醒管理 |
| GET/PUT | `/api/v1/user/settings` | 用户设置 |

### 3.7 管理接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/admin/health` | 健康检查 |
| POST | `/api/v1/admin/cache/clear` | 清除缓存 |
| POST | `/api/v1/admin/switch-source` | 切换数据源 |
| GET | `/api/v1/admin/api-logs` | 查询接口日志 |
| POST | `/api/v1/admin/api-logs/clear` | 清空接口日志 |

---

## 4. 数据源说明

### 4.1 可转债数据源

| 数据源 | 用途 | 接口 |
|--------|------|------|
| 新浪财经 | 实时转债行情（价格、涨跌幅） | `vip.stock.finance.sina.com.cn` |
| 东方财富 | 转股指标（溢价率、转股价值、评级） | `datacenter-web.eastmoney.com` |
| 新浪财经 | 正股实时行情（待发债正股报价） | `hq.sinajs.cn` |
| 东方财富 | 待发/配售转债数据 | `datacenter-web.eastmoney.com`（RPT_BOND_CB_LIST） |
| 东方财富 | PB / 总股本 | `datacenter-web.eastmoney.com`（RPT_VALUEANALYSIS_DET） |
| 东方财富 | MA20 均线 | `push2his.eastmoney.com`（日K线） |

### 4.2 待发/配售可转债数据对接

**函数**：`_fetch_em_pending_bonds()`（`services/convertible_bond.py`）

```python
def _fetch_em_pending_bonds():
    params = {
        "reportName": "RPT_BOND_CB_LIST", "columns": "ALL",
        "source": "WEB", "client": "WEB", "pageSize": "500",
        "sortColumns": "PUBLIC_START_DATE", "sortTypes": "-1",
    }
    resp = em_get(_EM_BOND_LIST_URL, params=params, timeout=15)
    # 筛选 LISTING_DATE 为空的债券（尚未上市）
    pending = [b for b in all_bonds if not b.get('LISTING_DATE')]
```

**东财原始字段映射**：

| 东财字段 | 后端输出字段 | 说明 |
|-----------|-------------|------|
| `CONVERT_STOCK_CODE` | `stock_code` | 正股代码 |
| `SECURITY_SHORT_NAME` | `stock_name` | 正股名称 |
| `SECURITY_CODE` | `bond_code` | 转债代码 |
| `CORRECODE_NAME_ABBR` | `bond_name` | 转债名称 |
| `ACTUAL_ISSUE_SCALE` | `issue_size` | 发行规模（亿） |
| `INITIAL_TRANSFER_PRICE` | `conversion_price` | 转股价 |
| `FIRST_PER_PREPLACING` | `per_share_allocation` | 每股配售额（元/股） |
| `RATING` | `rating` | 信用评级 |
| `PUBLIC_START_DATE` | `apply_date` | 申购日期 |
| `SECURITY_START_DATE` | `registration_date` | 股权登记日 |
| `CORRECODE` | `apply_code` | 申购代码 |
| `ONLINE_GENERAL_LWR` | `win_rate` | 中签率 |
| 新浪 `hq.sinajs.cn` | `stock_price` | 正股实时价格 |
| 新浪 `hq.sinajs.cn` | `stock_change` | 正股涨跌幅 |
| `PB_MRQ`（RPT_VALUEANALYSIS_DET） | `pb` | 市净率 |
| K线 API（push2his） | `ma20_price` | 20日均线 |

**辅助函数**：
- `_fetch_sina_stock_quotes()` — 批量获取正股实时行情（新浪）
- `_fetch_stock_fundamentals()` — 批量获取 PB / 总股本（东财）
- `_fetch_stock_ma20()` — 获取单只股票 20 日均线（东财K线）

**注**：东方财富仅覆盖已进入发行阶段的债券（已公告发行 → 上市），早期流程债券（董事会预案 → 上市委通过）暂不提供。

---

## 5. 数据归一化逻辑

### 5.1 `_fetch_em_pending_bonds()` 数据组装

**位置**：`services/convertible_bond.py`

该函数从东方财富获取待发转债数据，并配合新浪/东财辅助接口组装完整字段：

1. **东财债券列表**：`RPT_BOND_CB_LIST` → 筛选 `LISTING_DATE` 为空的未上市债券
2. **正股行情**：新浪 `hq.sinajs.cn` 批量获取实时价格、涨跌幅
3. **PB / 总股本**：东财 `RPT_VALUEANALYSIS_DET` 批量获取估值数据
4. **MA20 均线**：东财 K线 API 获取最近 20 日收盘价均值
5. **衍生指标计算**：
   - `shares_for_10_lots` = `1000 / per_share_allocation`
   - `safety_pad` = `expected_profit / (shares_for_10_lots * stock_price) * 100`
   - `expected_profit` = 固定 `1000 * 0.2 = 200` 元（假设上市溢价 20%）
   - `stock_trend` = `(stock_price - ma20_price) / ma20_price * 100`
   - `stock_cash_ratio` = `总市值(亿) / 发行规模(亿)`
   - `strategy_score` = `_calc_placement_score(issue_size, tradable_amount, safety_pad)` → 0-100
   - `strategy_rating`：≥70 推荐、≥40 可关注、<40 谨慎
   - `risk_level`：安全垫 <3% 高风险、>8% 低风险、其余中风险
   - `status`：根据申购日期推导（`_get_status_from_dates()`）
6. **本地公告数据补充**：`_enrich_with_local_placement()` 用配售公告覆盖预估数据

### 5.2 缓存机制

- **配售数据 TTL**：1800 秒（30 分钟），因为待发转债数据变化不频繁
- **缓存后端**：本地 fakeredis / 生产 Redis
- **SWR 模式**：缓存命中时立即返回旧数据，后台异步刷新
- **手动刷新**：`GET /api/v1/convertible/pending?refresh=true`

---

## 6. 部署说明

### 6.1 Docker 构建

```bash
cd cloudrun
docker build -t trading-toolkit-service .
docker run -p 8080:8080 trading-toolkit-service
```

### 6.2 Google Cloud Run

项目使用 GitHub Actions 自动部署到 Cloud Run：
- CI：`.github/workflows/backend-ci.yml`
- 部署：`.github/workflows/backend-deploy.yml`

### 6.3 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `USE_MOCK` | 是否使用 Mock 数据 | `false` |
| `DATABASE_URL` | 数据库连接 | SQLite |
| `REDIS_URL` | Redis 连接 | fakeredis |

---

## 7. 开发环境搭建

```bash
cd cloudrun
pip install -r requirements.txt
python app.py
```

启动后输出：
```
后端启动完成，主数据源: direct，缓存后端: fakeredis
 * Running on http://127.0.0.1:8080
```

### 验证

```bash
# 健康检查
curl http://localhost:8080/api/v1/admin/health

# 配售数据
curl http://localhost:8080/api/v1/convertible/pending

# 可转债列表
curl http://localhost:8080/api/v1/convertible/list?page=1&page_size=3
```

### 常见问题

- **ModuleNotFoundError**：执行 `pip install -r requirements.txt`
- **数据返回为空**：检查网络和上游公开接口；无可用缓存时接口会返回不可用状态
- **缓存清理**：`curl -X POST http://localhost:8080/api/v1/admin/cache/clear -H "Content-Type: application/json" -d '{"module":"all"}'`
# 本地开发指南

## 环境配置

### 客户端边界

微信小程序的配置、云函数和静态资源由独立的 `trading-toolkit-mp` 仓库维护。本仓库只包含 CloudRun 服务、回测框架和服务端文档。

## 启动步骤

### 1. 启动 Flask 后端

```bash
cd cloudrun
pip install -r requirements.txt
python app.py
```

首次启动会安装 Python 依赖，初次请求外部数据源可能需要等待。启动后输出：

```
后端启动完成，主数据源: direct，缓存后端: fakeredis
 * Running on http://127.0.0.1:8080
```

### 2. 验证后端

```bash
# 健康检查
curl http://localhost:8080/api/v1/admin/health

# 市场概览
curl http://localhost:8080/api/v1/market/overview

# 可转债列表
curl http://localhost:8080/api/v1/convertible/list?page=1&page_size=3
```

### 3. 启动客户端

小程序启动和开发者工具配置请在 `trading-toolkit-mp` 仓库中完成。

### 4. 调试

- **环境信息**：在控制台输入 `getApp().getEnvInfo()` 查看当前环境
- **网络请求**：开发者工具 Network 面板查看 API 调用
- **模拟器**：建议用 iPhone 15 Pro 或 iPhone SE 尺寸测试

## 后端 API 测试

```python
import requests

BASE = 'http://localhost:8080'

# 带排序和筛选
r = requests.get(f'{BASE}/api/v1/convertible/list', params={
    'sort': 'premium_desc',
    'min_price': 100,
    'max_premium': 50,
    'page': 1,
    'page_size': 10
})
data = r.json()
print(f'共 {data["data"]["total"]} 条')

# 可转债详情
r = requests.get(f'{BASE}/api/v1/convertible/detail/110073')
print(r.json()['data'])

# LOF 列表
r = requests.get(f'{BASE}/api/v1/lof/list')
items = r.json()['data']
for item in items[:3]:
    print(f'{item["code"]} {item["name"]}: 溢价率 {item["premium"]}%')

# 强制刷新缓存
requests.post(f'{BASE}/api/v1/admin/cache/clear', json={'module': 'convertible'})
```

## 常见问题

### Flask 启动时报错 `ModuleNotFoundError`

```bash
pip install -r cloudrun/requirements.txt
```

### 公开数据源返回为空

检查网络连接和上游接口可用性。服务在有上次成功缓存时会返回 `data_status: "stale"`；无缓存时会返回不可用状态。

### 小程序请求报 `ERR_CERT_AUTHORITY_INVALID`

开发者工具 → 详情 → 本地设置 → 勾选「不校验合法域名」

### 可转债溢价率字段为 0

东方财富接口首次请求可能较慢，之后会命中缓存。如果仍有问题，重启后端并访问 `/api/v1/admin/cache/clear` 清除缓存后重试。

### 缓存问题

本地开发用 `fakeredis` 模拟 Redis，进程重启后缓存自动清空。如需手动清理：

```bash
curl -X POST http://localhost:8080/api/v1/admin/cache/clear -H "Content-Type: application/json" -d '{"module":"all"}'
```

### 在微信开发者工具中使用 HTTP 请求

小程序默认只允许 HTTPS 请求。本地开发需在「详情 → 本地设置」中关闭域名校验，否则无法访问 localhost:8080。
