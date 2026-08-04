## 设计

服务读取所有未上市记录，使用已持久化的公告时间线识别 `上市委通过`、`同意注册`，并与登记、申购、待上市阶段合并为观察范围。时间线缺失时后台补齐，读取请求不扫描公告。响应使用 `placement_observation_state` 表达 `eligible`、`registration_unknown` 或 `expired`，前端不得自行从日期重算资格。

登记日仍在当天或未来为 `eligible`；缺失或不可解析为 `registration_unknown`；其余为 `expired`。已有快照继续保留并遵循 30 天清理策略。
