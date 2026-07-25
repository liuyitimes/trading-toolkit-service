## 背景

Web 配债详情导出需要展示候选标的的可追溯依据，但现有待发配债响应没有稳定、易理解的来源信息字段。此前讨论中出现过 `placement_evidence` 和裸 `provenance` 等叫法，容易让前后端和使用者误以为它们可以互换。

## 变更内容

- 为 `GET /api/v1/convertible/pending` 约定唯一的可选来源字段 `placement_provenance`，面向读者统一称为“配债来源信息”。
- 规定该对象仅承载已采集或已核验的参与资格、登记日、配售条款、缴款时点、公告日期、公告链接、核验时间和需复核状态；缺失时不得编造或推断。
- 不输出 `placement_evidence` 或裸 `provenance` 作为同一概念的替代字段。
- 与 `trading-toolkit-web` 中同名 `placement-document-export` 变更保持 HTTP 契约一致。

## 能力

### 新增能力

- `placement-document-export`：为待发配债响应提供可选且可追溯的配债来源信息。

### 修改能力

- `convertible-bonds`：明确待发配债响应的配债来源信息字段和缺失数据语义。

## 影响

- 服务模块：`cloudrun/services/convertible_bond.py` 的待发配债结果组装和相关数据源适配。
- HTTP 契约：`GET /api/v1/convertible/pending` 的单个候选标的可增加 `placement_provenance`。
- 数据源与持久化：只有能关联到公告或已核验数据的字段才能写入该对象；当前数据不足时省略该对象，不新增不可信回退源。
- 回滚：停止输出可选对象即可，既有数组和响应信封形式不变。
