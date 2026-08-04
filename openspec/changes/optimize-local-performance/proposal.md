## Why

本地 Ubuntu 服务冷缓存时将多个上游 HTTP 请求放在用户读取路径中。实测 `/api/v1/market/overview` 为 11.59 秒、`/api/v1/convertible/list` 为 8.80 秒，页面无法在一秒内完成主要数据读取。

## What Changes

- 为服务缓存增加上次成功快照，进程重启后仍可立即返回可观察的陈旧数据。
- 常规读取缓存未命中时只启动单飞后台刷新，不在 HTTP 请求中等待上游。
- 市场概览并发读取其独立数据域；页面并发加载互不依赖的数据。
- 保留 `refresh=true` 的显式同步刷新语义，并增加接口耗时回归验证。

## Impact

影响 Flask 缓存、概览端点、服务启动方式和 Vue 首页加载编排。配套 Web 变更为 `trading-toolkit-web/optimize-local-performance`。
