# Cloudflare Pages 与 Render 新加坡的 Demo 交付

状态：已接受。未办理 ICP 备案的 Demo 阶段，由 Cloudflare Pages 托管 Vue Web 应用，并由 Render 新加坡区域托管 Flask 服务；Web 直接请求通过 `VITE_API_BASE_URL` 配置的 Render 地址。该组合保留现有 Flask、Docker 和 Python 依赖，不引入 Worker API 代理。

此方案是面向中国大陆用户的尽力而为访问路径，不承诺大陆节点、低延迟或服务等级。若产品以后需要稳定的中国大陆交付，必须另行选择具备大陆资源和备案支持的中国供应商。依据见 `docs/research/china-mainland-hosting-options.md`。
