# Trading Toolkit Service（后端服务）

金融投资工具箱后端服务，提供可转债分析、LOF 基金套利监控、港股打新资讯的 API 接口。

> 小程序前端已独立为单独仓库 `trading-toolkit-mp`（微信小程序原生）。

## 功能

| 模块 | 功能 | 数据源 |
|------|------|--------|
| 可转债 | 实时行情、双低/强赎/折价/下修信号、市场温度、待发/配售 | 新浪财经 + 东方财富（直连 HTTP） |
| LOF 基金 | 实时溢价排行、套利机会、申购状态 | 东方财富公开接口 |
| 港股打新 | IPO 列表、申购信息、上市表现 | 同花顺公开接口 |
| 市场概览 | 市场情绪、资金流向、板块热度 | 新浪财经、乐咕、东方财富公开接口 |
| 用户系统 | 自选管理、申购状态跟踪 | SQLite / PostgreSQL |

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python Flask |
| 数据源 | 直连公开 HTTP API（按上游域限流、重试和缓存） |
| 缓存 | fakeredis（开发）/ Redis（生产）/ 内存 LRU |
| 数据库 | SQLite（开发）/ PostgreSQL（生产） |
| 部署 | Docker（云托管容器镜像） |

## 快速开始

### 前置依赖

- Python 3.11+

### 1. 安装依赖

```bash
cd cloudrun
pip install -r requirements.txt
```

### 2. 启动 Flask 后端

```bash
cd cloudrun
python app.py
```

后端运行在 `http://localhost:8080`

### 验证接口

```bash
curl http://localhost:8080/api/v1/market/overview
curl http://localhost:8080/api/v1/convertible/list?page=1&page_size=3
curl http://localhost:8080/api/v1/admin/health
```

## 项目结构

```
├── cloudrun/                # Flask 后端
│   ├── app.py               # 路由入口
│   ├── services/            # 数据源层
│   │   ├── convertible_bond.py   # 可转债数据合并
│   │   ├── lof_fund.py           # LOF 数据
│   │   ├── hk_ipo.py            # 港股 IPO 数据
│   │   ├── direct_source.py      # 直连数据源门面
│   │   ├── http_client.py        # 上游 session、重试和限流
│   │   ├── factory.py            # 单源工厂（兼容现有调用）
│   │   ├── cache.py              # 分级缓存
│   │   └── normalizer.py         # 字段标准化
│   ├── models/              # 数据模型
│   ├── utils/               # 工具
│   └── Dockerfile           # 云托管容器镜像
├── backtest/                # 回测框架
└── docs/                    # 架构、领域与交付文档
```

## 数据可靠性

服务直接请求新浪财经、东方财富、同花顺和乐咕等公开接口。对单源端点，回源失败时优先返回带 `data_status: "stale"` 的上次成功缓存；无缓存时返回不可用状态，不以 Mock 数据伪装实时结果。详见 [数据源与缓存](docs/architecture/data-sources.md)。

## 接口清单

所有接口统一前缀 `/api/v1/`，返回格式：

```json
{
  "success": true,
  "data": { ... },
  "meta": { "cached": true, "source": "direct", "update_time": "..." }
}
```

| 接口 | 说明 |
|------|------|
| `GET /api/v1/market/overview` | 综合市场概览 |
| `GET /api/v1/market/sentiment` | 市场情绪 |
| `GET /api/v1/market/fund-flow` | 资金流向 |
| `GET /api/v1/convertible/list` | 可转债列表（支持筛选/排序/分页） |
| `GET /api/v1/convertible/signals` | 可转债信号 |
| `GET /api/v1/convertible/temperature` | 可转债市场温度 |
| `GET /api/v1/convertible/detail/<code>` | 可转债详情 |
| `GET /api/v1/lof/list` | LOF 基金列表 |
| `GET /api/v1/lof/opportunities` | LOF 套利机会 |
| `GET /api/v1/hkipo/list` | 港股 IPO 列表 |
| `GET /api/v1/hkipo/upcoming` | 申购中 IPO |
| `GET/POST/DELETE /api/v1/user/favorites` | 用户自选管理 |

完整字段映射见 [docs/DATA_GUIDE.md](docs/DATA_GUIDE.md)，文档索引见 [docs/README.md](docs/README.md)。

## 部署

后端通过 Docker 容器部署到云托管（如腾讯云 CloudBase）。详见 [docs/BACKEND_CICD_GUIDE.md](docs/BACKEND_CICD_GUIDE.md)。

## 环境配置

见 [docs/development.md](docs/development.md)

## 风险提示

本工具仅供学习研究，不构成投资建议。数据仅供参考，请以官方渠道为准。
