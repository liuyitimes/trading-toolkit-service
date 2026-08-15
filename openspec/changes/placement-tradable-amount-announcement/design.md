# 设计：公告驱动的首日可交易量

## 数据流

1. 待配债快照刷新线程获取东方财富候选标的。
2. 以候选正股代码定向检索巨潮公告，复用现有 PDF 表格解析器和 `PlacementResult` 持久化。
3. 用本地公告记录覆盖候选标的：`shareholder_amount`、`shareholder_ratio`、`tradable_amount`、来源元数据和缺失状态。
4. 快照持久化后由 Web 读取；用户请求不执行公告网络请求。

## 口径

公告金额单位统一为亿元。只有公告原股东优先配售合计金额可用时，首日可交易量才等于 `issue_size - shareholder_amount`，配售率由该金额和发行规模计算。金额缺失时不得仅凭比例推算，以免 PDF 表格误识别产生伪造的 0 亿结果。

## 缺失状态

`placement_data_status` 使用 `verified`、`unavailable` 两种值；`placement_data_reason` 记录“公告未发布”“公告无可解析表格”或“公告字段缺失”。缺失字段使用 JSON `null`。

## 兼容性

保留现有字段名；新增字段为可选字段。Web 将 `null` 映射为 `--`，不改变已存在的有效公告数据。
