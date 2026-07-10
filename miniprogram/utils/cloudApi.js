// 云函数 & CloudRun HTTP 调用工具类
// 降级链：HTTP 优先 → 云函数 → 兜底数据

const config = require('../config')

// 开发环境判断：优先用 config 中的 currentEnv
const env = config.autoSwitch ? 'development' : (config.currentEnv || 'development')
// 兜底 BASE_URL（仅当 app 未初始化或未配置 cloudRunUrl 时使用）
const FALLBACK_BASE_URL = config[env].baseUrl

// 运行时获取 BASE_URL：优先用 app.getCloudRunUrl()（用户在设置页配置的地址），
// 回退到 config.js 的默认值。app 在模块加载时可能尚未初始化，故延迟到调用时获取。
function getBaseUrl() {
  try {
    const app = getApp()
    if (app && typeof app.getCloudRunUrl === 'function') {
      const url = app.getCloudRunUrl()
      if (url) return url.replace(/\/+$/, '')  // 去掉末尾斜杠
    }
  } catch (e) {
    // app 未初始化，忽略
  }
  return FALLBACK_BASE_URL
}

console.log(`[cloudApi] 环境: ${env}, 默认 BASE_URL: ${FALLBACK_BASE_URL}`)

// action → API 路径映射表
const ACTION_TO_API = {
  'overview': '/api/v1/market/overview',
  'convertibleList': '/api/v1/convertible/list',
  'convertibleSignals': '/api/v1/convertible/signals',
  'convertibleTemperature': '/api/v1/convertible/temperature',
  'convertibleDetail': '/api/v1/convertible/detail',
  'convertibleNewBonds': '/api/v1/convertible/list?new_bonds=true',
  'convertiblePending': '/api/v1/convertible/pending',
  'lofList': '/api/v1/lof/list',
  'lofOpportunities': '/api/v1/lof/opportunities',
  'lofSummary': '/api/v1/lof/summary',
  'hkipoList': '/api/v1/hkipo/list',
  'hkipoUpcoming': '/api/v1/hkipo/upcoming',
  'hkipoSummary': '/api/v1/hkipo/summary',
  'sentiment': '/api/v1/market/sentiment',
  'fundFlow': '/api/v1/market/fund-flow',
  'health': '/api/v1/admin/health',
  'apiLogs': '/api/v1/admin/api-logs',
  'apiLogsClear': '/api/v1/admin/api-logs/clear'
}

/**
 * HTTP 调用 CloudRun
 * @param {string} action - 操作类型
 * @param {object} data - 请求参数
 * @returns {Promise<{data: *, source: string}>}
 */
function callHttp(action, data = {}) {
  return new Promise((resolve, reject) => {
    const apiPath = ACTION_TO_API[action]
    if (!apiPath) {
      reject(new Error(`未知 action: ${action}`))
      return
    }

    const BASE_URL = getBaseUrl()
    let url = BASE_URL + apiPath
    // 对于 convertibleDetail，需要拼接 code 参数到路径
    if (action === 'convertibleDetail' && data.code) {
      url += '/' + data.code
    }
    // 对于其他有参数的接口，追加 query string
    const params = { ...data }
    if (action === 'convertibleDetail') delete params.code
    const qs = Object.entries(params)
      .filter(([_, v]) => v !== undefined && v !== null)
      .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
      .join('&')
    if (qs) url += (url.includes('?') ? '&' : '?') + qs

    console.log(`[cloudApi] 请求: ${url}`)
    wx.request({
      url,
      method: 'GET',
      timeout: 30000,
      success: (res) => {
        console.log(`[cloudApi] ${action} 响应: ${res.statusCode}`)
        if (res.statusCode === 200 && res.data && res.data.success) {
          resolve({ data: res.data.data, source: res.data.meta?.source || 'http' })
        } else {
          reject(new Error(`HTTP 响应异常: ${res.statusCode}, data=${JSON.stringify(res.data).slice(0, 200)}`))
        }
      },
      fail: (err) => {
        console.error(`[cloudApi] ${action} 请求失败: ${err.errMsg}`)
        reject(new Error(`HTTP 请求失败: ${err.errMsg || 'unknown'}, url=${url}`))
      }
    })
  })
}

/**
 * 云函数调用（带 source 标记）
 * @param {string} action - 操作类型
 * @param {object} data - 额外参数
 * @returns {Promise<{data: *, source: string}>}
 */
function callCloud(action, data = {}) {
  return new Promise((resolve, reject) => {
    wx.cloud.callFunction({
      name: 'market',
      data: { action, ...data },
      success: res => {
        if (res.result && res.result.success) {
          resolve({ data: res.result.data, source: 'cloud' })
        } else {
          reject(new Error(res.result ? res.result.error : '云函数返回异常'))
        }
      },
      fail: err => {
        reject(err)
      }
    })
  })
}

/**
 * 降级调用链：HTTP → 云函数 → 兜底数据
 * @param {string} action - 操作类型
 * @param {object} data - 额外参数
 * @param {*} fallback - 兜底数据
 * @returns {Promise<*>}
 */
async function callMarketSafe(action, data = {}, fallback = null) {
  // 第一优先：HTTP 调用 CloudRun
  try {
    const result = await callHttp(action, data)
    console.log(`[${action}] HTTP 调用成功, source=${result.source}`)
    return result.data
  } catch (httpErr) {
    console.warn(`[${action}] HTTP 调用失败: ${httpErr.message}，降级到云函数`)
  }

  // 第二优先：云函数
  try {
    const result = await callCloud(action, data)
    console.log(`[${action}] 云函数调用成功`)
    return result.data
  } catch (cloudErr) {
    console.warn(`[${action}] 云函数调用失败: ${cloudErr.message}，使用兜底数据`)
  }

  // 第三优先：兜底数据
  return fallback
}

/**
 * 调用market云函数（向后兼容，内部走 callMarketSafe 降级链）
 * @param {string} action - 操作类型
 * @param {object} data - 额外参数
 * @returns {Promise<*>}
 */
async function callMarket(action, data = {}) {
  const result = await callMarketSafe(action, data)
  if (result === null) {
    throw new Error(`所有调用方式均失败: ${action}`)
  }
  return result
}

module.exports = { callMarket, callMarketSafe, callHttp }
