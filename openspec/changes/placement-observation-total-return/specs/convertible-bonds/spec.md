## MODIFIED Requirements

### Requirement: 待发配债观察范围和登记日状态

服务 MUST 在 `/api/v1/convertible/pending` 中返回未上市且已进入“上市委通过”“同意注册”或后续登记、申购、待上市阶段的标的。服务 MUST NOT 因股权登记日已过而删除标的。

每个候选标的 MAY 提供 `placement_observation_state`：登记日今天或未来为 `eligible`，登记日未知为 `registration_unknown`，登记日早于当前中国日期为 `expired`。

#### Scenario: 已过登记日但债券尚未上市

- **GIVEN** 候选标的尚未上市且登记日早于当前日期
- **WHEN** 用户请求待发配债列表
- **THEN** 服务仍返回该标的
- **AND THEN** `placement_observation_state` 为 `expired`

#### Scenario: 早期审批标的

- **GIVEN** 候选标的尚未上市但只有董事会预案、股东大会批准或交易所受理节点
- **WHEN** 用户请求待发配债列表
- **THEN** 服务不将该标的纳入观察列表

#### Scenario: 缺失登记日

- **GIVEN** 候选标的已进入末段审批但没有可靠登记日
- **WHEN** 用户请求待发配债列表
- **THEN** 服务保留该标的
- **AND THEN** 状态为 `registration_unknown` 或省略状态但不得伪造日期
