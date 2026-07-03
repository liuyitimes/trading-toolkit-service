# 旺财百宝箱

微信小程序金融投资工具箱，提供可转债分析、LOF 基金套利监控、港股打新资讯。

## 功能

| 模块 | 功能 | 数据源 |
|------|------|--------|
| 可转债 | 实时行情、双低/强赎/折价/下修信号、市场温度 | akshare（新浪+东方财富） |
| LOF 基金 | 实时溢价排行、套利机会、申购状态 | akshare（东方财富） |
| 港股打新 | IPO 列表、申购信息、上市表现 | akshare（同花顺） |
| 市场概览 | 市场情绪、资金流向、板块热度 | akshare（新浪+乐咕） |
| 用户系统 | 自选管理、申购状态跟踪 | SQLite / 本地存储 |

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | 微信小程序原生（WXML / WXSS / JS） |
| 后端 | Python Flask（本地开发） → 微信云函数（上线） |
| 数据源 | akshare（主），efinance / tushare / mock（降级） |
| 缓存 | fakeredis（开发）/ Redis（生产）/ 内存 LRU |
| 数据库 | SQLite（开发）/ PostgreSQL（生产） |

## 快速开始

### 前置依赖

- Python 3.11+
- 微信开发者工具

### 1. 安装后端依赖

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

### 3. 打开小程序

1. 微信开发者工具 → 导入项目 → 选择项目根目录
2. 修改 `miniprogram/config.js`，确认 `currentEnv: 'development'`
3. 开发者工具 → 详情 → 本地设置 → 勾选「不校验合法域名」
4. 编译预览

### 验证接口

```bash
curl http://localhost:8080/api/v1/market/overview
curl http://localhost:8080/api/v1/convertible/list?page=1&page_size=3
curl http://localhost:8080/api/v1/admin/health
```

## 项目结构

```
├── miniprogram/          # 小程序前端
│   ├── pages/            # 页面
│   │   ├── index/        # 首页（市场概览+日历+中签查询）
│   │   ├── convertible/  # 可转债信号
│   │   ├── bondDetail/   # 可转债详情
│   │   ├── lof/          # LOF 基金套利
│   │   ├── hkipo/        # 港股打新
│   │   ├── hkipoDetail/  # 港股打新详情
│   │   ├── quoteManage/  # 语录管理
│   │   └── setting/      # 设置
│   └── utils/            # 工具
│       ├── cloudApi.js   # 数据调用（HTTP→云函数→兜底）
│       ├── format.js     # 格式化
│       └── favoriteManager.js  # 自选管理
├── cloudrun/             # Flask 后端
│   ├── app.py            # 路由入口
│   ├── services/         # 数据源层
│   │   ├── convertible_bond.py  # 可转债数据合并
│   │   ├── lof_fund.py          # LOF 数据
│   │   ├── hk_ipo.py            # 港股 IPO 数据
│   │   ├── akshare_source.py    # akshare 数据源
│   │   ├── efinance_source.py   # efinance 备选源
│   │   ├── tushare_source.py    # tushare 备选源
│   │   ├── mock_source.py       # Mock 兜底
│   │   ├── factory.py           # 工厂+熔断+降级
│   │   ├── cache.py             # 分级缓存
│   │   └── normalizer.py        # 字段标准化
│   ├── models/          # 数据模型
│   ├── utils/           # 工具
│   └── Dockerfile       # 云托管容器镜像
├── cloudfunctions/       # 微信云函数
│   └── market/           # 市场数据云函数
└── .trae/specs/          # 设计规格
    ├── backend-api-design/
    └── frontend-optimization/
```

## 数据降级策略

```
请求 → HTTP (CloudRun)
  → 失败 → 云函数 (Cloud Function)
    → 失败 → Mock 数据
```

数据源降级链：

```
akshare → efinance → tushare → mock
```

熔断器：连续失败 5 次 → 熔断 60 秒

## 接口清单

所有接口统一前缀 `/api/v1/`，返回格式：

```json
{
  "success": true,
  "data": { ... },
  "meta": { "cached": true, "source": "akshare", "update_time": "..." }
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

完整字段映射见 [DATA_GUIDE.md](DATA_GUIDE.md)

## 环境配置

见 [docs/development.md](docs/development.md)

## 风险提示

本工具仅供学习研究，不构成投资建议。数据仅供参考，请以官方渠道为准。
