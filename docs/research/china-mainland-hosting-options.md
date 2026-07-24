# 中国大陆部署与访问约束

状态：研究结论（2026-07-24）

本说明只核对当前候选方案 `Cloudflare Pages -> Render Flask -> 托管 PostgreSQL` 能否在中国大陆部署或获得大陆加速。这里的“可访问”不等同于“在中国大陆托管”或“低延迟”。

## 结论

- **Render 不能部署到中国大陆。** Render 官方当前列出的服务和数据存储区域只有美国 Oregon、Ohio、Virginia，德国 Frankfurt 和新加坡；不包含中国大陆。若继续使用 Render，应选新加坡，并让生产数据库与服务同区域，避免 API 到数据库的额外跨区跳转。
- **免费 Cloudflare Pages 不能承诺中国大陆托管或加速。** Pages 官方只承诺部署到 Cloudflare 的 global network；这不是 Cloudflare China Network，也没有说明免费 Pages 会使用大陆节点。
- **Cloudflare 的大陆网络是企业级独立服务。** China Network 由京东云运营大陆数据中心，需 Enterprise 计划加购、每个顶级域名具备有效 ICP 备案/许可证，并接受内容审核和补充条款；首次域名接入约需 24--48 小时。
- **因此，当前 Demo 可采用 Cloudflare Pages + Render Singapore，但其中国大陆访问质量是尽力而为，不能作为 SLA 或“大幅加速”的承诺。** 若产品目标是稳定的大陆低延迟，必须另选具有大陆资源、备案支持和明确跨境连通方案的 Web/API/数据库提供方，并单独推进 ICP 合规流程。

## 对本项目的执行约束

1. 在部署文档和产品文案中称 Cloudflare Pages 为“全球边缘静态托管”，不得称为“中国大陆托管”或“大陆 CDN 加速”。
2. Render 服务和生产 PostgreSQL 固定在同一地区；当前可选的最接近大陆的 Render 区域是新加坡。Render 不支持原地更改已有服务或数据库的区域，迁移需创建新资源并迁移配置与数据。
3. 需要大陆节点时，先完成域名 ICP、内容审核和供应商合同评估；不要把 Cloudflare China Network 当作免费 Pages 的升级开关。Cloudflare 的可用产品清单也应在采购前逐项复核，不能仅凭“Cloudflare”品牌推断 Pages 已纳入 China Network。

## 官方来源

| 主题 | 官方资料 | 可核对事实 |
| --- | --- | --- |
| Render 区域 | [Render Regions](https://render.com/docs/regions) | 当前可部署区域列表不含中国大陆；静态站点使用全球 CDN；已有服务或数据库不能原地改区域。 |
| Pages 定位 | [Cloudflare Pages Overview](https://developers.cloudflare.com/pages/) | Pages 部署到 Cloudflare global network。 |
| 中国大陆网络与套餐 | [Cloudflare China Network Overview](https://developers.cloudflare.com/china-network/) | 大陆内容交付依赖位于大陆的基础设施；China Network 是 Enterprise 客户的独立订阅，需 ICP，且并非所有产品可用。 |
| 接入要求 | [Cloudflare China Network: Get started](https://developers.cloudflare.com/china-network/get-started/) | 需要 Enterprise、China Network 加购、补充条款、ICP、京东云内容审核；首次接入约 24--48 小时。 |
| 产品支持范围 | [China Network available products and features](https://developers.cloudflare.com/china-network/reference/available-products/) | China Network 的产品支持范围需逐项确认，不能从普通 Cloudflare 产品可用性推断。 |
| ICP 适用范围 | [Cloudflare ICP concept](https://developers.cloudflare.com/china-network/concepts/icp/) | 通过 CDN 向中国访客交付的网站也在 ICP 规则说明的适用范围内。 |
