## MODIFIED Requirements

### Requirement: 待发配债来源信息契约

服务 MUST 在 `GET /api/v1/convertible/pending` 的单个待发配债候选标的上，只通过可选 `placement_provenance` 字段提供配债来源信息。该对象仅包含已采集或已核验的参与资格、股权登记日、配售条款、缴款时点、公告日期、公告 URL、核验时间、核验状态和需复核状态。服务 MUST NOT 输出 `placement_evidence` 或裸 `provenance` 作为同一概念的替代字段。

#### Scenario: 返回有完整来源信息的候选标的

- **GIVEN** 服务已关联候选标的的可信公告或核验记录
- **WHEN** 用户请求待发配债数据
- **THEN** 候选标的可包含 `placement_provenance`
- **AND THEN** 其中的公告日期、公告 URL 和核验状态必须与已关联记录一致。

#### Scenario: 来源信息缺失或不完整

- **GIVEN** 服务没有可验证的候选标的来源记录，或记录缺少某项事实
- **WHEN** 用户请求待发配债数据
- **THEN** 服务必须省略整个 `placement_provenance` 对象或缺失的键
- **AND THEN** 服务不得用市场观察、估算值或旧字段名填充它。

#### Scenario: 响应形式保持兼容

- **GIVEN** 调用方使用既有待发配债数组或响应信封
- **WHEN** 服务增加可选配债来源信息
- **THEN** 既有响应结构必须保持可用
- **AND THEN** `placement_provenance` 只作为单项的可选扩展出现。
