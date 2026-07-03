# 本地开发指南

## 环境配置

### 环境切换

`miniprogram/config.js` 配置了双环境自动切换：

```javascript
autoSwitch: true  // true=根据小程序版本自动切换
```

| 小程序版本 | 使用环境 | 云环境 ID | CloudRun 地址 |
|-----------|---------|-----------|---------------|
| 开发版（本地预览） | `development` | `cloudbase-d1gurol40225b603e` | `http://localhost:8080` |
| 体验版 | `production` | `cloudbase-d1gurol40225b603e` | 同 development（未部署） |
| 正式版 | `production` | `cloudbase-d1gurol40225b603e` | 同 development（未部署） |

如需手动指定：

```javascript
autoSwitch: false,
currentEnv: 'development'  // 或 'production'
```

### 小程序配置

开发者工具 → 详情 → 本地设置 → 勾选「不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书」

## 启动步骤

### 1. 启动 Flask 后端

```bash
cd cloudrun
pip install -r requirements.txt
python app.py
```

首次启动会自动安装 akshare 等依赖，初次运行因下载数据可能需要等待。启动后输出：

```
后端启动完成，主数据源: akshare，缓存后端: fakeredis
 * Running on http://127.0.0.1:8080
```

### 2. 验证后端

```bash
# 健康检查
curl http://localhost:8080/api/v1/admin/health

# 市场概览
curl http://localhost:8080/api/v1/market/overview

# 可转债列表
curl http://localhost:8080/api/v1/convertible/list?page=1&page_size=3
```

### 3. 启动小程序

1. 微信开发者工具 → 导入项目 → 选择项目根目录
2. 确认 `project.config.json` 中 `appid` 正确
3. 编译预览

### 4. 调试

- **环境信息**：在控制台输入 `getApp().getEnvInfo()` 查看当前环境
- **网络请求**：开发者工具 Network 面板查看 API 调用
- **模拟器**：建议用 iPhone 15 Pro 或 iPhone SE 尺寸测试

## 后端 API 测试

```python
import requests

BASE = 'http://localhost:8080'

# 带排序和筛选
r = requests.get(f'{BASE}/api/v1/convertible/list', params={
    'sort': 'premium_desc',
    'min_price': 100,
    'max_premium': 50,
    'page': 1,
    'page_size': 10
})
data = r.json()
print(f'共 {data["data"]["total"]} 条')

# 可转债详情
r = requests.get(f'{BASE}/api/v1/convertible/detail/110073')
print(r.json()['data'])

# LOF 列表
r = requests.get(f'{BASE}/api/v1/lof/list')
items = r.json()['data']
for item in items[:3]:
    print(f'{item["code"]} {item["name"]}: 溢价率 {item["premium"]}%')

# 强制刷新缓存
requests.post(f'{BASE}/api/v1/admin/cache/clear', json={'module': 'convertible'})
```

## 常见问题

### Flask 启动时报错 `ModuleNotFoundError`

```bash
pip install -r cloudrun/requirements.txt
```

### akshare 数据返回为空

检查网络连接。akshare 需要访问新浪/东方财富的接口。如果被限流，系统会自动降级到 Mock 数据。

### 小程序请求报 `ERR_CERT_AUTHORITY_INVALID`

开发者工具 → 详情 → 本地设置 → 勾选「不校验合法域名」

### 可转债溢价率字段为 0

akshare 的东方财富接口 `bond_zh_cov()` 首次调用需要下载数据（约 10 秒），之后会缓存。如果仍有问题，重启后端并访问 `/api/v1/admin/cache/clear` 清除缓存后重试。

### 缓存问题

本地开发用 `fakeredis` 模拟 Redis，进程重启后缓存自动清空。如需手动清理：

```bash
curl -X POST http://localhost:8080/api/v1/admin/cache/clear -H "Content-Type: application/json" -d '{"module":"all"}'
```

### 在微信开发者工具中使用 HTTP 请求

小程序默认只允许 HTTPS 请求。本地开发需在「详情 → 本地设置」中关闭域名校验，否则无法访问 localhost:8080。
