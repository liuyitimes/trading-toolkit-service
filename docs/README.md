# 文档索引

本目录只保存与当前代码或可追溯决策有关的工程文档；一次性的 IDE、AI 会话和验收清单不纳入版本库。

## 工程治理

- [问题跟踪规则](agents/issue-tracker.md)：本地问题、规格和路线图的存放方式。
- [分诊标签](agents/triage-labels.md)：规范分诊角色与标签映射。
- [领域文档规则](agents/domain.md)：领域资料的阅读顺序与维护约定。

## 当前架构

- [数据源与缓存](architecture/data-sources.md)：上游、缓存状态和失败处理。
- [回测引擎](architecture/backtesting.md)：模块职责及已实现的 A 股交易规则。
- [可转债抢权配售字段](domain/convertible-placement.md)：字段语义、计算口径与待完成的兼容修复。
- [套利策略的可执行性校验](domain/arbitrage-strategy-validation.md)：可转债优配、封闭式基金折价与港股 IPO 的证据字段和失效条件。

## 研究

- [港股打新公开数据源验证](research/hk-ipo-data-sources.md)：HKEXnews 披露链、已验证请求和字段采集边界。

## 开发与交付

- [本地开发](development.md)
- [部署说明](deployment.md)
- [后端 CI/CD](BACKEND_CICD_GUIDE.md)
- [接口与数据字段](DATA_GUIDE.md)

本地测试使用 `pip install -r cloudrun/requirements-dev.txt`，随后执行 `python -m pytest cloudrun/tests backtest/tests`。

## 规划与历史

- [项目计划](project-plan.md)：历史规划，不作为当前架构依据。

## 维护约定

- 架构和领域术语发生变化时，先更新本目录中的相应文档。
- 新的长期技术决策使用描述性英文文件名，放在相应的 `architecture/` 或 `domain/` 子目录。
- 不提交 `.trae/`、`.mimocode/`、`.codegraph/` 等本地工具的过程文件。
