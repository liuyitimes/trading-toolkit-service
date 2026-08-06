# 接口与字段约定

状态：当前实现。本文是 Flask 服务与 Vue Web 应用之间的字段命名参考；支持的 HTTP 契约以 `openspec/specs/api-contracts/spec.md` 为准。

## 先看这三层

```text
后端响应字段（snake_case）
  -> Web Store 归一化（camelCase）
  -> 页面展示值（可能带单位的字符串）
```

- HTTP 请求和响应字段使用 `snake_case`，例如 `stock_code`、`per_share_allocation`。
- Web Store 内部字段使用 `camelCase`，例如 `stockCode`、`perShare`。
- 仅供公式和排序使用的原始数值以 `_xxxRaw` 命名，例如 `_stockPriceRaw`；它不是 HTTP 字段。
- 业务术语统一使用“待发配债候选标的”。“待发转债”“待发/配售转债”和“配售列表”仅在引用历史代码或上游字段时使用。

## 统一响应信封

所有业务 API 使用 `/api/v1/` 前缀，并返回以下结构：

```json
{
  "success": true,
  "data": {},
  "meta": {
    "cached": false,
    "source": "direct",
    "cache_expire_at": null,
    "update_time": "2026-07-24T10:00:00+08:00"
  }
}
```

`data` 是业务数据；`meta` 是响应元数据。Web 的 Axios 拦截器会解包 `data`，因此 Store 和页面不应再读取 `response.data.data`。失败响应使用 `success: false` 和 `error.code`、`error.message`。

## 接口分组

| 领域 | 路径 | Web API 模块 |
| --- | --- | --- |
| 市场概览 | `/api/v1/market/*` | `src/api/market.js` |
| 可转债 | `/api/v1/convertible/*` | `src/api/convertible.js` |
| 配售公告 | `/api/v1/placement/*` | 当前未封装 |
| LOF 基金 | `/api/v1/lof/*` | `src/api/lof.js` |
| 港股 IPO | `/api/v1/hkipo/*` | `src/api/hkipo.js` |
| 封闭式基金 | `/api/v1/closed-end/*` | `src/api/closedEnd.js` |
| 用户数据 | `/api/v1/user/*` | `src/api/user.js` |
| 运维管理 | `/api/v1/admin/*` | 当前未封装 |

## 待发配债候选标的字段

`GET /api/v1/convertible/pending` 返回候选标的数组。以下字段是两端需要保持同义的核心字段：

| 后端字段 | Web 字段 | 面向用户的名称 | 说明 |
| --- | --- | --- | --- |
| `stock_name` | `stockName` | 正股名称 | 可转债对应的正股。 |
| `stock_code` | `stockCode` | 正股代码 | 证券代码字符串，保留前导零。 |
| `bond_name` | `bondName` | 转债名称 | 待发行或待上市的可转债名称。 |
| `bond_code` | `bondCode` | 转债代码 | 转债证券代码字符串。 |
| `stock_price` | `stockPrice` / `_stockPriceRaw` | 正股价 | 前者是展示值，后者是数值。 |
| `per_share_allocation` | `perShare` / `_perShareRaw` | 每股配售额 | 每持有一股正股可获配的可转债面额。 |
| `shares_for_10_lots` | `sharesFor10` | 获配 1,000 元所需股数 | 按配售额度计算。 |
| `cash_ratio` | `cashRatio` | 百元含权 | 每投入 100 元正股市值可获配的可转债面额。 |
| `expected_profit` | `expectedProfit` / `_expectedProfitRaw` | 预估收益 | 基于当前预期上市溢价假设的测算值，不是承诺收益。 |
| `safety_pad` | `safetyPad` / `_safetyPadRaw` | 安全垫 | 预估收益相对持仓成本的缓冲比例。 |
  | `registration_close_price` | `registrationClosePrice` / `_registrationClosePriceRaw` | 股权登记日收盘价 | 使用正股日 K 线中股权登记日当天收盘价；缺失时为 `null`，不得用当前价替代。 |
  | `post_registration_close_price` | `postRegistrationClosePrice` / `_postRegistrationClosePriceRaw` | 登记日后收尾价 | 使用股权登记日之后第一个可验证 A 股交易日收盘价；缺失时为 `null`。 |
| `strategy_score` | `score` | 配债评分 | 供排序和比较使用的综合分。 |
| `strategy_rating` | `rating` | 配债评级 | 例如“推荐”“可关注”“谨慎”。 |

`cash_ratio` 只表示百元含权。`stock_cash_ratio` 是“正股总市值 / 转债发行规模”的策略评分指标，不能替代或展示为百元含权。完整计算口径见 [可转债抢权配售字段](domain/convertible-placement.md)。

  配债参与后总收益由 Web 基于历史事实和用户选择的预期上市溢价率派生：

```text
正股段收益 = (登记日后收尾价 - 股权登记日收盘价) × 获配 1,000 元面值所需的实际正股股数
转债预期收益 = 1,000 × 预期上市溢价率
配债参与后总收益 = 正股段收益 + 转债预期收益
```

如果 `registration_close_price` 或 `post_registration_close_price` 缺失，Web 必须显示“--”，不得用正股当前价推断真实复盘收益。

## 今年上市新债表现字段

`GET /api/v1/convertible/new-listed` 返回当前中国时区自然年内上市的新债数组。以下字段用于“今年新债”Tab：

| 后端字段 | Web 字段 | 面向用户的名称 | 说明 |
| --- | --- | --- | --- |
| `bond_code` | `bondCode` | 转债代码 | 可转债证券代码字符串。 |
| `bond_name` | `bondName` | 转债名称 | 可转债名称。 |
| `stock_code` | `stockCode` | 正股代码 | 对应正股代码。 |
| `stock_name` | `stockName` | 正股名称 | 对应正股名称。 |
| `list_date` | `listDate` | 上市日 | 当前自然年内的上市日期。 |
| `latest_close` | `latestClose` | 最新收盘价 | 最新可验证交易日收盘价；当日仅有实时行情时可由 `price` 辅助展示。 |
| `listing_close` | `listingClose` | 上市日收盘价 | “上市以来”涨幅基准。 |
| `month_base_close` | `monthBaseClose` | 本月基准收盘价 | 本月首个可验证交易日收盘价。 |
| `three_day_price` | `threeDayPrice` | 前三日阶段价 | 上市后第 1 / 2 / 3 个交易日中已完成阶段的收盘价。 |
| `three_day_stage` | `threeDayStage` | 前三日阶段 | 取值 1、2、3；上市未满三个交易日时展示已完成交易日阶段。 |
| `gain_since_listing` | `gainSinceListing` | 上市以来涨幅 | 以上市日收盘价为基准，单位为百分比数值。 |
| `month_gain` | `monthGain` | 本月涨幅 | 以本月首个交易日收盘价为基准，单位为百分比数值；基准不可验证时为 `null`。 |
| `three_day_gain` | `threeDayGain` | 前三日涨幅 | 以 100 元面值为基准，按已完成的第 1 / 2 / 3 个交易日阶段计算。 |

## LOF 连续正溢价持续性

`/api/v1/lof/list` 每项返回 `premium_persistence` 对象，描述连续正溢价的已观测天数与可信度：

| 字段 | 说明 |
| --- | --- |
| `consecutive_positive_sessions` | 已观测连续正溢价天数；不可用时为 `null`，不得用零值替代。 |
| `status` | `complete`（观测完整）、`partial`（历史不足/存在缺口）、`unavailable`（当前交易日无同日可比观测）。 |
| `as_of` | 结果对应的最近交易日（中国时区）。 |
| `history_started_on` | 历史覆盖起点；`partial` 因触及覆盖边界时披露，否则为 `null`。 |
| `reason` | 不可用或历史不足的具体原因；`complete` 时为 `null`。 |

口径：

- 当前交易日同日可比且溢价不为正时返回 `0` 且状态为 `complete`，该零是业务事实。
- 历史不足或缺口返回 `partial`，天数仅表示已观测下界，Web 显示“至少 N 天”并披露原因。
- 观测由 `cli.py` 回补/采集写入 PostgreSQL（开发环境 SQLite），失败不得以缓存、零值或推断替代。

## 配债来源信息

`placement_provenance` 是待发配债候选标的的可选来源信息对象，面向读者统一称为“配债来源信息”。Web 归一化后命名为 `placementProvenance`。

- 对象缺失或键缺失表示服务没有已采集且可信的事实；客户端必须显示“不可用”，不得推断。
- `placement_evidence` 和裸 `provenance` 不是该对象的兼容别名。
- 该字段的服务端实现仍在配套 OpenSpec 变更中；在实际响应提供前，客户端必须兼容其缺失。

## 数据来源

```text
Flask 路由
  -> DataSourceFactory / DirectSource
  -> 领域服务
  -> 新浪财经、东方财富、同花顺或乐咕公开接口
  -> 缓存与统一响应
```

运行时不使用 akshare、efinance 或 tushare。上游请求由 `services/http_client.py` 统一处理会话、超时、重试和限流；数据源和缓存细节见 [数据源与缓存](architecture/data-sources.md)。
