# 03 — 服务端 GitHub 发布治理

**What to build:** 让服务端主分支在验证、部署与健康检查全部成功后才发布，并通过 GitHub 分支治理阻止未经审查的变更。

**Blocked by:** 02 — Render 服务与数据库配置。

**Status:** ready-for-agent

- [ ] Render 部署凭据与健康检查地址作为 GitHub Secrets 配置。
- [ ] 主分支要求服务验证与代码扫描通过，并要求拉取请求审查。
- [ ] 一次主分支发布可完成验证、部署触发和健康检查。
