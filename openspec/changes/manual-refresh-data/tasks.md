# 任务

## 1. 综合概览刷新

- [x] 1.1 解析综合概览请求中的 `refresh=true`。
- [x] 1.2 将强制刷新传递给四个组成数据的 `fetch_with_cache` 调用。

## 2. 验证

- [x] 2.1 增加综合概览强制刷新调用参数验证。
- [ ] 2.2 运行服务端 HTTP 契约测试和 OpenSpec 校验（当前环境缺少 `flask`/`pytest`，仅完成 OpenSpec 校验）。
