# 港股打新公开数据源验证

状态：研究结论（2026-07-12）

目标是为“当前可申购 / 即将上市”的港股公开发售建立可追溯的一手数据链。结论是：**HKEXnews 可作为优先的一手发现和披露来源；每只标的仍必须以其 Global Offering / Prospectus PDF 和 Allotment Results PDF 为准。** 当前同花顺聚合表不能作为可执行事实源。

## 推荐来源与覆盖范围

| 来源 | 认证与请求 | 可获取的事实 | 何时可用 | 限制 |
| --- | --- | --- | --- | --- |
| HKEXnews 标题检索 | 公开、无登录；`GET https://www1.hkexnews.hk/search/titleSearchServlet.do` | 发布时点、股份代码/简称、文件标题、文件类型、官方 PDF 相对路径 | 发行文件、最终定价和配发结果公告发布后 | 未公开承诺的 API；只作发现/索引，不把它本身当字段真值。 |
| HKEXnews `GLOBAL OFFERING` / `Offer for Subscription` PDF | 上一端点返回的 `FILE_LINK` 加 `https://www1.hkexnews.hk` | 公开发售期、价格区间、每手股数、发售股份数、预计上市日、申请渠道、超额配售权条款 | 发售文件发布时 | 字段在 PDF 中，需逐文件解析；标题搜索会混入旧股的 Global Offering、Formal Notice，必须按文件分类过滤。 |
| HKEXnews `FINAL OFFER PRICE` / `ALLOTMENT RESULTS` PDF | 同上 | 最终发行价、公开发售认购倍数、回拨/重新分配后公开发售股份数、配发基准、退款安排、最终上市日期 | 配发结果公告发布后 | 是事后确认，不能预测个人获配数量。 |
| HKEX Newly Listed Securities | [公开 HTML 页](https://www.hkex.com.hk/Services/Trading/Securities/Trading-News/Newly-Listed-Securities?sc_lang=en) | 已列/拟列日期、证券代码、每手股数、状态和更新时间 | 临近上市及之后 | 不是当前公开发售清单；`*` 表示暂定日期。 |
| 券商或托管人 | 非公开、账户侧 | 渠道是否开放、实际截止、可用 HKD/融资额度、申请是否已提交和冻结金额 | 申购前/申购中 | 没有公共 HKEX API；不可用行情或招股书推断。 |

HKEX 明确要求投资者从 HKEXnews 的 Listed Company Information 查询招股书和公告；电子申请要经 White Form eIPO 服务商或券商/托管人经 HKSCC 的 FINI EIPO Channel 进行。[HKEX Equity Securities FAQ](https://www.hkex.com.hk/Global/Exchange/FAQ/Products/Securities/Equity-Securites?sc_lang=en)

## 已验证的真实请求

以下在 2026-07-12 以未认证 `GET` 实测返回 `200 application/json; charset=utf-8`。查询窗口受 HKEXnews 页面限制，未按证券筛选时最多一个月；生产采集应按日或滚动 30 天增量查询。

将同一请求的 `market` 改为 `GEM` 也实测返回相同 JSON 合约（该窗口 `recordCnt: 0`），因此主板和 GEM 应独立轮询，而非把 `SEHK` 空结果解释为全市场无发行。

```text
https://www1.hkexnews.hk/search/titleSearchServlet.do
  ?sortDir=0
  &sortByOptions=DateTime
  &category=0
  &market=SEHK
  &stockId=
  &documentType=
  &fromDate=20260612
  &toDate=20260712
  &title=GLOBAL%20OFFERING
  &searchType=0
  &t1code=
  &t2Gcode=
  &t2code=
  &rowRange=100
  &lang=E
```

实测响应含 `recordCnt: 70`，记录字段包括 `DATE_TIME`、`STOCK_CODE`、`STOCK_NAME`、`TITLE`、`LONG_TEXT`、`FILE_TYPE` 和 `FILE_LINK`。其中一条一手发售文件记录为：

```json
{
  "STOCK_NAME": "NEXCHIP",
  "STOCK_CODE": "02249",
  "TITLE": "GLOBAL OFFERING",
  "LONG_TEXT": "Listing Documents - [Offer for Subscription]",
  "DATE_TIME": "30/06/2026 06:34",
  "FILE_TYPE": "PDF",
  "FILE_LINK": "/listedco/listconews/sehk/2026/0630/2026063000123.pdf"
}
```

对应的一手文件为：<https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0630/2026063000123.pdf>。

以同一端点和 `title=FINAL%20OFFER%20PRICE` 查询，实测响应含 `recordCnt: 17`；其中 NEXCHIP 的正式配发结果公告为：

```json
{
  "STOCK_NAME": "NEXCHIP",
  "STOCK_CODE": "02249",
  "TITLE": "ANNOUNCEMENT OF FINAL OFFER PRICE AND ALLOTMENT RESULTS",
  "LONG_TEXT": "Announcements and Notices - [Allotment Results]",
  "DATE_TIME": "09/07/2026 21:56",
  "FILE_LINK": "/listedco/listconews/sehk/2026/0709/2026070901289.pdf"
}
```

对应的一手文件为：<https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0709/2026070901289.pdf>。

这验证了可复现的披露链：`Global Offering` 文件出现时创建/更新“可申购候选”，`Allotment Results` 出现时确认最终价、认购倍数、回拨和配发状态。HKEX 官方 FAQ 同时说明配发基准取决于有效申请数，超额认购时会依招股书的回拨机制调整公开发售部分；因此不可在结果公告前生成个人获配率或收益。[HKEX FAQ：Allotment basis](https://www.hkex.com.hk/Global/Exchange/FAQ/Products/Securities/Equity-Securites?sc_lang=en#collapse-6)

## 采集与字段校验设计

### 1. 发现候选

每日用 `GLOBAL OFFERING`、`OFFER FOR SUBSCRIPTION`、`PROSPECTUS`、`FINAL OFFER PRICE` 和 `ALLOTMENT RESULTS` 做标题检索。只保留：

- `market=SEHK`（GEM 发行需以 `market=GEM` 单独查询，不能遗漏）；
- `FILE_TYPE=PDF` 或 HTML 附件；
- `LONG_TEXT` 表明 `Listing Documents - [Offer for Subscription]` 的发售文件，或 `Announcements and Notices - [Allotment Results]` 的结果文件；
- 有完整 `STOCK_CODE`、`DATE_TIME`、`FILE_LINK`。

`GLOBAL OFFERING` 也会命中权利发行、旧股公告和“不继续上市”的更新，因而只匹配标题绝不能进入可申购列表。

### 2. 从 Global Offering / Prospectus 取得可申购字段

PDF 解析器应提取原文片段和页码，字段包括：

```text
issuer_name, stock_code, prospectus_url, published_at,
offer_open_at, offer_close_at, broker_cutoff_at (nullable),
price_low_hkd, price_high_hkd, final_price_hkd (nullable),
board_lot_shares, entry_fee_hkd, public_offer_shares_initial,
offer_size_total, expected_listing_at, offer_type,
green_shoe_terms, source_page, source_excerpt
```

校验：`offer_open_at < offer_close_at < expected_listing_at`；`price_low_hkd <= price_high_hkd`；每手成本只可计算为 `board_lot_shares * price_high_hkd`（若有官方 entry fee 则优先展示它）。价格区间、预计上市日或每手股数缺失时，不能标“可申购”。券商截点通常早于公开发售截点，且不在 HKEX 文件中时保持 `nullable`。

### 3. 从 Allotment Results 确认结果

结果 PDF 应提取：

```text
final_price_hkd, public_offer_subscriptions_multiple,
clawback_or_reallocation_percent, public_offer_shares_final,
allocation_basis_url, allocation_basis_page,
refund_arrangement, listing_at_confirmed, source_page, source_excerpt
```

这些字段只在结果公告后写入。它们可以证明市场整体的认购倍数和最终回拨，却不能替代某个用户的券商回执或实际获配手数。

### 4. 即将上市交叉验证

在发售结束/结果公告后，用 HKEX 的 [Newly Listed Securities](https://www.hkex.com.hk/Services/Trading/Securities/Trading-News/Newly-Listed-Securities?sc_lang=en) 交叉检查 `stock_code`、`board_lot_shares` 和上市日期。该页面实测于 2026-07-10 更新，HTML 行包含日期、代码、每手股数和 `New Listing` 描述；它只能补强交易可用日，不能替代结果公告。

## 状态与有效性

| 状态 | 准入条件 | 不应显示的内容 |
| --- | --- | --- |
| `观察` | 有 Application Proof/PHIP 或不完整发售文件 | “申购中”、一手成本、预期收益。 |
| `待账户核验` | 已有完整 Global Offering 字段，尚无用户券商渠道、账户或 HKD/融资确认 | “可执行”、用户可申请金额。 |
| `可申购` | 发售窗口仍有效，且账户渠道开放、实际券商截止和资金状态均已由用户/券商确认 | 获配数量、确定收益。 |
| `待结果` | 用户已提交申请 | 可卖数量、个人中签率。 |
| `已获配/待上市` | 有券商回执与官方 Allotment Results | 不能用市场整体配发基准替代用户获配手数。 |
| `可交易` | 官方结果公告/交易所页面确认上市日，且账户股份可用 | 不保证流动性或收益。 |

同一受益人多重申请会被拒绝，账户数不能用于扩张可执行额度。[HKEX FAQ：Multiple applications](https://www.hkex.com.hk/Global/Exchange/FAQ/Products/Securities/Equity-Securites?sc_lang=en#collapse-4)

## 不采用的来源与结论

- 不使用同花顺的港股 IPO 聚合表作为执行事实：其 `apply_limit`、`top_value`、申购代码和行业 PE 并非 HKEX 公开发售所需的每手、价格区间、渠道截止或实际配发字段。
- 不把 Application Proof 或 PHIP 当作可申购通知。HKEX 明示它们不是最终上市文件，投资决定必须以随后发布的最终文件和公告为准。[HKEX FAQ：planning to list](https://www.hkex.com.hk/Global/Exchange/FAQ/Products/Securities/Equity-Securites?sc_lang=en#collapse-1)
- 不尝试从 HKEX 公共数据推断券商可申购状态、资金冻结、融资利率、账户适当性或个人获配；这些属于用户账户/券商数据，必须单独确认。

## 实施结论

可以用 HKEXnews 的官方检索端点替换当前的港股 IPO 列表发现源，并将 PDF 原件链接、发布日期、页码和摘录随字段保存。由于该 JSON 端点未在公开 API 合约中承诺，采集层应保留 HTTP 状态、原始响应哈希、限速、失败后 `unavailable/stale` 状态，并对关键字段以 PDF 原文解析结果为准。
