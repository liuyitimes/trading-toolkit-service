## ADDED Requirements

### Requirement: LOF 列表连续正溢价契约

`/api/v1/lof/list` 返回的每项 LOF MUST（必须）包含 `premium_persistence` 对象，其中包括 `consecutive_positive_sessions`、`status`、`as_of`、`history_started_on` 和 `reason`。`status` 必须为 `complete`、`partial` 或 `unavailable`；不可用时天数必须为 `null`，不得用零值替代。

#### Scenario: 当前观测为非正溢价

- **当**：当前交易日存在同日可比观测且溢价为零或负数
- **则**：列表必须返回 `consecutive_positive_sessions: 0` 和 `status: complete`
- **并且**：`reason` 必须为 `null`

#### Scenario: 当前观测不可用

- **当**：当前交易日不存在同日可比观测
- **则**：列表必须返回 `consecutive_positive_sessions: null` 和 `status: unavailable`
- **并且**：`reason` 必须说明不可用原因
