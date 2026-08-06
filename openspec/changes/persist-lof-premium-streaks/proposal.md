## Why

LOF 列表当前不返回连续正溢价字段，Web 只能将缺失值显示为 `0 天`，无法区分真实非正溢价、历史覆盖不足和当日数据不可比。需要以可审计的日度观测提供连续正溢价，而不是从缓存或页面访问推断历史。

## What Changes

- 新增 PostgreSQL LOF 溢价日度观测、A 股交易日历和任务进度持久化。
- 新增可断点续跑的当前年度历史回补与收盘后日度采集任务；任务由外部调度器执行并使用数据库互斥锁。
- 新增同日价格与已公布单位净值配对、修订、缺口和连续正溢价计算规则。
- 修改 `/api/v1/lof/list`，为每项返回带状态、日期和原因的 `premium_persistence` 对象。
- 修正实时 LOF 路径，保留上游实际净值日期，不以行情时间伪造净值日期。

## Capabilities

### New Capabilities

- `lof-premium-observation-persistence`：持久化、回补、采集和计算可审计的 LOF 溢价日度观测。

### Modified Capabilities

- `lof-funds`：LOF 列表向配套 Web 变更提供连续正溢价持续性契约和不可用语义。

## Impact

- 影响 `cloudrun/services/lof_fund.py`、新增持久化服务和 SQLAlchemy 模型、Alembic 迁移、Flask CLI 任务以及部署定时器示例。
- `/api/v1/lof/list` 增加非破坏性的 `premium_persistence` 字段；配套变更为 `trading-toolkit-web/persist-lof-premium-streaks`。
- 使用现有 PostgreSQL/Alembic、东方财富历史单位净值和腾讯日 K 线；读取接口继续使用既有缓存但不再写入历史。
- 回滚时停止外部任务并移除新增字段的消费；保留观测表以避免破坏已采集的数据。
