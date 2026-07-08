# 数据源稳定性加固重构 — ADR + 术语表

> 生成时间：2026-07-08
> 来源：grill-with-docs 会话（6 轮 grilling 收敛）
> 参考技能：`a-stock-data` V3.3.0（直连 HTTP + 移除 akshare 设计）

---

## 决策摘要表

| 决策点 | 选择 | 风险/约束 |
|---|---|---|
| akshare 处置 | 全量直连移除 | **预防性重写，非实测驱动**（崩溃为听说，未亲历） |
| 降级分组 | 按上游域（sina/eastmoney/ths/legu） | 6/7 端点单源，降级链对单源无效 |
| 熔断器 | 移除，靠限流 + 降级 | 单源端点失败靠 stale cache 兜 |
| 超时 | 单层（单请求级 10s） | 串行叠加靠 SWR 缓存化解 |
| 单源端点失败 | stale cache + 「数据延迟」徽章 | 符合工程纪律（陈旧数据必须标注） |
| 串行叠加 | 方法内部调用走 SWR 缓存 | 依赖缓存命中率，冷启动仍慢 |
| observability | 结构化日志 | 无 Prometheus 指标，无告警 |
| 伪造数据 | 删除，返回缺失 | EfinanceSource 退役 |
| 迁移路径 | Big bang 一次性 | 风险集中 |
| 验证方式 | 集成测试打真实上游 | CI 可能受上游风控影响 |
| akshare 退役 | akshare + efinance + tushare 一起删 | 无回退 |

---

## ADR-001: 移除 akshare，全量直连 HTTP API

**状态**：Accepted（带风险标注）

**背景**：
- `cloudrun/services/` 全量依赖 akshare（12 个 `ak.*` 函数，分布在 convertible_bond.py / lof_fund.py / hk_ipo.py / closed_end.py / akshare_source.py）
- `a-stock-data` 技能 V3.0 已做出同样决定，理由：akshare 本质是东财/同花顺/新浪公开 API 的封装，中间层增加故障点（版本兼容 bug、pandas 3.0 ArrowInvalid 等）
- 用户反馈驱动症状："akshare 版本升级导致崩溃" + "超时/慢，无降级"

**决策**：
- 新建 HTTP 基础设施层（统一 client：限流 + 重试 + session 复用 + 超时 + 结构化日志）
- 重写所有 12 个端点为直连 HTTP，移除 `import akshare`
- 新建按上游域命名的 source：`sina_source` / `em_source` / `ths_source` / `legu_source`
- 删除 `akshare_source.py` / `efinance_source.py` / `tushare_source.py`
- 从 `requirements.txt` 移除 akshare / efinance / tushare 依赖

**风险标注**：
> **此决策为预防性重写，非实测驱动。** 用户明确表示 akshare 崩溃为"听说的，预防性"，未亲历具体崩溃。与用户工程纪律"运行时验证为唯一通过标准"存在张力。若重写后实测发现 akshare 端点稳定，此决策的 ROI 需复盘。

**迁移**：Big bang 一次性迁移（一个 PR），集成测试打真实上游验证字段一致性。

---

## ADR-002: 按上游域分组 session，移除熔断器

**状态**：Accepted

**背景**：
- 现有降级链 `akshare → efinance → tushare` 同源同崩（akshare 和 efinance 都打东财）
- 现有 `CircuitBreaker` 在 source 级（5 次失败熔断 60s），粒度太粗——akshare 熔断后所有 12 端点全断
- `a-stock-data` 的设计：`em_get()` 串行限流（1s + 随机抖动）+ `HTTPAdapter` + `Retry`（429/5xx 指数退避）+ 端点级 try/except + 多服务器探测，无显式熔断器

**决策**：
- HTTP client 按上游域名维护独立 session（Keep-Alive 复用）：
  - `sina_session` — 新浪财经（不封 IP）
  - `em_session` — 东方财富（封 IP 风险，内置限流 1s + 抖动）
  - `ths_session` — 同花顺（不封 IP）
  - `legu_session` — 乐咕（不封 IP）
- 每个 session 独立配置：超时、重试策略、UA、Referer
- **移除 `CircuitBreaker` 类**，靠 `em_get()` 等限流入口 + 端点级降级兜底
- 东财系所有请求走 `em_get()`（限流 + session 复用 + 429/5xx 重试），与 `a-stock-data` 一致

**端点 → 上游域映射**：

| 端点 | 上游域 | 封 IP 风险 | 是否单源 |
|---|---|---|---|
| 可转债实时行情 | sina | 低 | 多源（sina + em） |
| 可转债转股指标 | em | 中 | **单源** |
| LOF/ETF 行情 | em | 中 | **单源** |
| 封闭式基金行情 | sina | 低 | **单源** |
| 行业资金流 | em | 中 | **单源** |
| 港股 IPO | ths | 低 | **单源** |
| 涨跌家数 | legu | 低 | **单源** |
| 指数实时 | sina | 低 | **单源** |
| 指数日线 | sina | 低 | **单源** |
| 可转债详情补充 | em | 中 | **单源** |
| 基金净值 | em | 中 | **单源** |
| 健康检查 | jsl | 低 | **单源** |

**注意**：7 个端点中 6 个单源，"靠降级"对它们无效。单源端点失败行为见 ADR-003。

---

## ADR-003: 单源端点失败 → stale cache + 「数据延迟」徽章

**状态**：Accepted

**背景**：
- 6/7 端点为单源，上游失败时无降级目标
- 用户工程纪律："Mock 兜底必须显式标注"，"禁止用 mock 静默冒充真实链路通过"
- `a-stock-data` 对北向资金的解法：本地 CSV 自缓存，每次拉实时数据后写本地，上游断供时读本地历史

**决策**：
- 所有单源端点的数据写入持久化缓存（现有 `CacheManager` + redis/fakeredis/memory 后端）
- 单源端点上游失败时，返回上次成功的缓存数据（stale cache）
- 响应中附加 `data_status: "stale"` 字段 + `data_fetched_at: <ISO8601>` 字段
- 前端检测到 `data_status: "stale"` 时显示「数据延迟」徽章
- 不做静默降级——徽章是硬约束

**实现要点**：
- 现有 `get_with_swr` 返回缓存时不区分"新鲜缓存"和"过期缓存"。需要扩展为：
  - 上游成功 → 写缓存 + 返回 `data_status: "fresh"`
  - 上游失败 + 有缓存 → 返回缓存 + `data_status: "stale"`
  - 上游失败 + 无缓存 → 返回空 + `data_status: "unavailable"`

---

## ADR-004: 移除 EfinanceSource 伪造数据

**状态**：Accepted

**背景**：
- `efinance_source.py:215-239` 用 `code_hash` 伪造 `rating` / `maturity_date` / `pure_bond_value`
- 违反用户工程纪律："Mock 兜底必须显式标注"
- efinance 本身是东财的封装，与 akshare 同源，重写后无存在必要

**决策**：
- 删除 `efinance_source.py` 整个文件
- 删除 `tushare_source.py` 整个文件（未实际配置 token，一直是空实现）
- 删除 `akshare_source.py` 整个文件
- 删除 `mock_source.py`（如存在）
- 新建按上游域命名的 source 文件
- 任何字段拿不到就返回 `None` / 缺失，前端显示「—」
- **禁止在真实数据源里用 hash/随机数生成字段值**

---

## ADR-005: 串行叠加靠 SWR 缓存化解

**状态**：Accepted

**背景**：
- `get_market_sentiment` 一个方法内串行调 6 个上游（新浪指数 + 乐咕涨跌家数 + 日线算量能 + 北交所推算）
- 单层超时 10s × 6 = 最坏 60s，撞 Flask worker timeout
- 用户选"单层超时"但未选"并发"

**决策**：
- 方法内部每个上游调用走 `get_with_swr` 缓存
- 正常运行时大部分调用走缓存（毫秒级），只有过期那个走上游（10s）
- 最坏情况：所有缓存同时过期，6 × 10s = 60s（可接受，依赖 Flask worker timeout 兜底）
- 冷启动（缓存全空）仍可能慢，依赖缓存预热（现有 `warmup_cache`）

**约束**：
- 重写时必须确保每个方法内部的子调用都走 `get_with_swr`，不能裸调 HTTP client
- 新增方法若需多上游调用，必须拆分为子函数各自走 SWR

---

## ADR-006: Big bang 迁移 + 集成测试打真实上游

**状态**：Accepted

**背景**：
- 12 端点 + 5 domain service + factory + app.py
- 用户工程纪律："运行时验证为唯一通过标准"，"禁止用语：应该/理论上/代码逻辑上"
- `app.py` 有 8 处 `factory.get_with_fallback(method_name)` 调用

**决策**：
- 一次性重写所有 source + domain service，保持 `app.py` 的 `factory.get_with_fallback` 接口不变
- `factory.py` 重构：注册新 source（sina/em/ths/legu），移除旧 source 注册
- `BaseDataSource` 抽象基类保留，新 source 继承
- 集成测试打真实上游，断言：
  - 响应非空
  - 关键字段存在且类型正确
  - 字段值与旧实现一致（迁移期可临时保留旧实现做影子对比）

**验证清单（每个端点）**：
1. 集成测试打真实上游，HTTP 200 + 非空响应
2. 关键字段存在 + 类型正确
3. `data_status` 字段存在（fresh/stale/unavailable）
4. 结构化日志含 URL + 耗时 + 状态码
5. 单源端点模拟上游失败时返回 stale cache + 徽章字段

---

## 术语表（Glossary）

| 术语 | 定义 |
|---|---|
| **上游域**（upstream domain） | 数据来源的 HTTP 域名，如 `qt.gtimg.cn`（腾讯）、`push2.eastmoney.com`（东财）、`hq.sinajs.cn`（新浪）。按域分组 session，独立限流/重试。 |
| **单源端点**（single-source endpoint） | 只有一个上游域提供该数据的端点（如 LOF 行情只有东财）。失败时无降级目标，靠 stale cache 兜底。 |
| **多源端点**（multi-source endpoint） | 有 2+ 上游域可提供该数据的端点（如可转债行情有新浪 + 东财）。失败时可降级到备用上游。 |
| **stale cache** | 上游失败时返回的上次成功缓存数据。响应标记 `data_status: "stale"`，前端显示「数据延迟」徽章。 |
| **SWR**（stale-while-revalidate） | 现有缓存策略：有缓存直接返回（即使过期），后台异步刷新。本次扩展为方法内部子调用也走 SWR，化解串行叠加。 |
| **「数据延迟」徽章** | 前端检测到 `data_status: "stale"` 时显示的标识，符合"陈旧/mock 数据必须显式标注"工程纪律。 |
| **em_get()** | 东财系请求的统一限流入口（1s 间隔 + 随机抖动 + session 复用 + 429/5xx 重试），对标 `a-stock-data` 的 `em_get()`。 |
| **直连 HTTP** | 不经 akshare/efinance/tushare 等中间封装库，直接用 `requests` 调上游 HTTP API。对标 `a-stock-data` V3.0。 |
| **Big bang 迁移** | 一次性重写所有 12 端点，一个 PR 上线，非增量迁移。 |
| **集成测试打真实上游** | 测试用例打真实 HTTP 上游（不 mock），断言字段一致性。CI 可能受上游风控影响，需重试机制。 |
| **data_status** | 新增响应字段，枚举值 `fresh`（上游成功）/ `stale`（上游失败但有缓存）/ `unavailable`（上游失败且无缓存）。 |

---

## 端点重写清单（实施时对照）

| # | 端点 | 旧 ak.* | 新直连 | 上游域 | 单源 |
|---|---|---|---|---|---|
| 1 | 可转债实时行情 | `ak.bond_zh_hs_cov_spot()` | 新浪可转债行情 HTTP | sina | 否 |
| 2 | 可转债转股指标 | `ak.bond_zh_cov()` | 东财可转债 HTTP | em | 是 |
| 3 | 可转债详情补充 | `ak.bond_zh_cov()` | 东财可转债 HTTP | em | 是 |
| 4 | LOF/ETF 行情 | `ak.fund_etf_spot_em()` / `ak.fund_lof_spot_em()` | 东财基金行情 HTTP | em | 是 |
| 5 | 封闭式基金行情 | `ak.fund_etf_category_sina()` | 新浪封闭式基金 HTTP | sina | 是 |
| 6 | 基金净值 | `ak.fund_open_fund_info_em()` | 东财基金净值 HTTP | em | 是 |
| 7 | 指数实时 | `ak.stock_zh_index_spot_sina()` | 新浪指数 HTTP | sina | 是 |
| 8 | 指数日线 | `ak.stock_zh_index_daily()` | 新浪指数日线 HTTP | sina | 是 |
| 9 | 涨跌家数 | `ak.stock_market_activity_legu()` | 乐咕 HTTP | legu | 是 |
| 10 | 行业资金流 | `ak.stock_fund_flow_industry()` | 东财行业资金流 HTTP | em | 是 |
| 11 | 港股 IPO | `ak.stock_ipo_hk_ths()` | 同花顺港股 IPO HTTP | ths | 是 |
| 12 | 健康检查 | `ak.bond_cb_jsl()` | 集思录 HTTP | jsl | 是 |

---

## 未决问题（实施时需确认）

1. **东财封 IP 的实测阈值**：a-stock-data 给的是社区数据（5次/秒、200次/分钟）。trading-toolkit 部署环境的实际阈值需实测确认，调整 `EM_MIN_INTERVAL`。
2. **stale cache 的 TTL 上限**：stale 数据放多久后视为不可用？建议 24h（一个交易日）。
3. **集成测试的 CI 稳定性**：真实上游可能封 CI 服务器 IP。需考虑：CI 重试机制 / 本地跑集成测试 / 录制 fixture 作为 fallback。
4. **冷启动性能**：SWR 缓存全空时 `get_market_sentiment` 仍可能 60s。是否需要启动时强制预热？
