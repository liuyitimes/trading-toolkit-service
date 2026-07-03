---
name: "wechat-miniprogram-finance"
description: "微信小程序金融投资应用全栈开发助手，涵盖前端页面、云函数后端、云数据库、金融数据处理。Invoke when developing WeChat Mini Program finance apps, adding pages/features, or working with cloud functions/database."
---

# WeChat Mini Program Finance Developer

微信小程序金融投资应用全栈开发技能，支持前端页面开发、云函数后端、云数据库操作、金融数据处理等一体化开发。

## 项目结构规范

```
miniprogram-1/
├── miniprogram/              # 小程序前端
│   ├── pages/                # 页面
│   │   └── <page-name>/
│   │       ├── index.js
│   │       ├── index.json
│   │       ├── index.wxml
│   │       └── index.wxss
│   ├── components/           # 组件
│   ├── utils/                # 工具函数
│   ├── images/               # 图片资源
│   ├── data/                 # 静态数据
│   ├── app.js
│   ├── app.json
│   └── app.wxss
├── cloudfunctions/           # 云函数（Node.js）
│   └── <function-name>/
│       ├── index.js
│       └── package.json
├── cloudrun/                 # 云托管（可选）
└── project.config.json
```

## 前端页面开发

### 新建页面流程

1. 在 `miniprogram/pages/` 下创建页面目录
2. 创建四个文件：`.js`、`.json`、`.wxml`、`.wxss`
3. 在 `app.json` 的 `pages` 数组中注册页面路径

### 页面 JS 模板

```javascript
const app = getApp()
const { callMarketSafe } = require('../../utils/cloudApi')

Page({
  data: {
    loading: true,
    list: [],
  },

  onLoad(options) {
    this.loadData()
  },

  onPullDownRefresh() {
    this.loadData().finally(() => {
      wx.stopPullDownRefresh()
    })
  },

  async loadData() {
    this.setData({ loading: true })
    try {
      const data = await callMarketSafe('actionName', {}, [])
      this.setData({ list: data })
    } catch (err) {
      console.error('加载失败:', err)
      wx.showToast({ title: '加载失败', icon: 'none' })
    } finally {
      this.setData({ loading: false })
    }
  },

  onItemTap(e) {
    const { index } = e.currentTarget.dataset
    const item = this.data.list[index]
    // 处理点击事件
  },
})
```

### 页面 JSON 配置

```json
{
  "navigationBarTitleText": "页面标题",
  "enablePullDownRefresh": true,
  "backgroundTextStyle": "dark",
  "usingComponents": {}
}
```

### WXML 编写规范

- 使用 `wx:for` 遍历列表，必须指定 `wx:key`
- 使用 `wx:if` / `wx:else` 条件渲染
- 绑定事件用 `bindtap`，传参用 `data-*` 属性
- 金额数字统一保留 2 位小数

### WXSS 样式规范

- 使用 rpx 单位适配不同屏幕
- 主题色：`#1E3A5F`（深蓝）、`#6B7280`（灰）、`#F5F6FA`（背景）
- 涨跌色：涨用红色 `#E53935`，跌用绿色 `#43A047`
- 卡片样式：白色背景、圆角 16rpx、阴影

## 云函数后端开发

### 云函数结构

每个云函数目录包含：
- `index.js` - 主入口文件
- `package.json` - 依赖配置

### 云函数模板

```javascript
exports.main = async (event, context) => {
  const { action } = event

  try {
    switch (action) {
      case 'actionName':
        return { success: true, data: await handleAction(event) }
      case 'health':
        return { success: true, data: { status: 'ok', time: new Date().toISOString() } }
      default:
        return { success: false, error: `未知action: ${action}` }
    }
  } catch (err) {
    console.error('云函数执行失败:', err)
    return { success: false, error: err.message }
  }
}

async function handleAction(event) {
  // 业务逻辑
  return result
}
```

### 云函数调用（前端）

统一使用 `utils/cloudApi.js` 中的封装：

```javascript
const { callMarket, callMarketSafe } = require('../../utils/cloudApi')

// 正常调用
const data = await callMarket('actionName', { param: 'value' })

// 带容错调用，失败返回 fallback
const data = await callMarketSafe('actionName', { param: 'value' }, fallbackData)
```

### 云数据库操作

在云函数中使用：

```javascript
const cloud = require('wx-server-sdk')
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })
const db = cloud.database()
const _ = db.command

// 查询
const res = await db.collection('collectionName')
  .where({ field: 'value' })
  .orderBy('createdAt', 'desc')
  .limit(20)
  .get()

// 新增
await db.collection('collectionName').add({
  data: { field: 'value', createdAt: db.serverDate() }
})

// 更新
await db.collection('collectionName').doc(id).update({
  data: { field: 'newValue' }
})
```

## 金融数据处理规范

### 数值格式化

```javascript
// 保留2位小数
function formatNumber(num, digits = 2) {
  if (typeof num !== 'number') return '--'
  return num.toFixed(digits)
}

// 百分比格式化
function formatPercent(num, digits = 2) {
  if (typeof num !== 'number') return '--'
  return (num > 0 ? '+' : '') + num.toFixed(digits) + '%'
}

// 金额格式化（千分位）
function formatMoney(num) {
  if (typeof num !== 'number') return '--'
  return num.toLocaleString('zh-CN', { minimumFractionDigits: 2 })
}
```

### 涨跌判断

- 正数 → 红色（上涨）
- 负数 → 绿色（下跌）
- 零 → 灰色

### 常见金融指标

| 指标 | 说明 |
|------|------|
| 转股溢价率 | (转债价格/转股价值 - 1) × 100% |
| 双低 | 转债价格 + 转股溢价率 × 100 |
| 折价率 | 负的溢价率 |
| 年化收益率 | (到期收益/当前价格) × (365/剩余天数) |

## 组件开发规范

### 组件结构

```
components/
└── <component-name>/
    ├── index.js
    ├── index.json
    ├── index.wxml
    └── index.wxss
```

### 组件 JS 模板

```javascript
Component({
  properties: {
    title: { type: String, value: '' },
    data: { type: Array, value: [] }
  },

  data: {},

  methods: {
    onTap(e) {
      this.triggerEvent('tap', { item: e.currentTarget.dataset.item })
    }
  }
})
```

### 使用组件

在页面 JSON 中注册：
```json
{
  "usingComponents": {
    "my-component": "/components/my-component/index"
  }
}
```

## TabBar 配置

在 `app.json` 中配置底部导航，图标放在 `miniprogram/images/icons/` 目录。

## 常用 API

### 页面跳转

```javascript
wx.navigateTo({ url: '/pages/detail/index?id=123' })  // 保留当前页
wx.redirectTo({ url: '/pages/login/index' })         // 替换当前页
wx.switchTab({ url: '/pages/index/index' })          // 切换 TabBar 页面
wx.navigateBack()                                    // 返回上一页
```

### 交互反馈

```javascript
wx.showToast({ title: '成功', icon: 'success' })
wx.showToast({ title: '加载中', icon: 'loading' })
wx.showLoading({ title: '加载中...' })
wx.hideLoading()
wx.showModal({ title: '提示', content: '确认删除？' })
```

### 下拉刷新

在页面 JSON 中启用：
```json
{ "enablePullDownRefresh": true }
```

在 JS 中处理：
```javascript
onPullDownRefresh() {
  this.loadData().finally(() => wx.stopPullDownRefresh())
}
```

## 云开发初始化

`app.js` 中初始化云开发：

```javascript
App({
  onLaunch() {
    if (wx.cloud) {
      wx.cloud.init({
        env: 'your-env-id',
        traceUser: true
      })
    }
  }
})
```

## 开发最佳实践

1. **数据容错**：所有云函数调用都使用 `callMarketSafe`，提供 mock 回退数据
2. **加载状态**：页面加载时显示 loading 状态，避免空白
3. **错误处理**：统一错误捕获，用户友好的错误提示
4. **下拉刷新**：列表页支持下拉刷新
5. **图片资源**：图标使用 PNG，小图标放 icons 目录
6. **代码复用**：通用逻辑抽离到 utils，通用 UI 封装为组件
7. **命名规范**：文件和目录用小写连字符，JS 变量用驼峰命名
