// LOF基金数据获取 - 东方财富API
const axios = require('axios')
const mock = require('./mock')

function safeFloat(val, defaultVal = 0) {
  const num = parseFloat(val)
  return isNaN(num) ? defaultVal : num
}

// 从东方财富获取LOF实时行情
async function fetchLofList() {
  // 东方财富LOF列表API
  const url = 'https://push2.eastmoney.com/api/qt/clist/get'
  const params = {
    pn: 1,
    pz: 200,
    po: 1,
    np: 1,
    fltt: 2,
    invt: 2,
    fs: 'b:MK0404',  // LOF基金分类
    fields: 'f12,f14,f2,f3,f6,f152,f161,f168'
  }

  const res = await axios.get(url, { params, timeout: 10000 })
  if (!res.data || !res.data.data || !res.data.data.diff) {
    throw new Error('东方财富LOF API返回数据格式异常')
  }

  const rows = res.data.data.diff
  return rows.map(row => {
    const code = String(row.f12 || '')
    // 判断交易所：5开头=沪，1开头=深
    let exchange = ''
    if (code.startsWith('5')) exchange = '沪'
    else if (code.startsWith('1')) exchange = '深'

    const price = safeFloat(row.f2)
    // f161为基金净值，f168为溢价率
    const valuation = safeFloat(row.f161)
    const premium = safeFloat(row.f168)

    return {
      代码: code,
      名称: String(row.f14 || ''),
      交易所: exchange,
      最新价: price,
      涨跌幅: safeFloat(row.f3),
      估值: valuation,
      溢价率: premium,
      连续溢价: 0,  // 东方财富API不直接提供，需计算
      申购状态: '不限',  // 默认不限，实际需从其他接口获取
      成交量: safeFloat(row.f5),
      成交额: safeFloat(row.f6)
    }
  }).filter(item => item['代码'] && item['名称'])
}

// 获取LOF列表
async function getLofList() {
  try {
    return await fetchLofList()
  } catch (err) {
    console.error('获取LOF列表失败:', err.message)
    return []
  }
}

// 获取LOF套利机会
async function getLofOpportunities() {
  try {
    const list = await fetchLofList()
    if (!list.length) return { premium: [], discount: [] }

    const sortedPremium = [...list].sort((a, b) => b['溢价率'] - a['溢价率']).slice(0, 20)
    const sortedDiscount = [...list].sort((a, b) => a['溢价率'] - b['溢价率']).slice(0, 20)

    return {
      premium: sortedPremium,
      discount: sortedDiscount
    }
  } catch (err) {
    console.error('获取LOF套利机会失败:', err.message)
    return { premium: [], discount: [] }
  }
}

// 获取LOF市场概览
async function getLofMarketSummary() {
  try {
    const list = await fetchLofList()
    if (!list.length) return null

    const premiums = list.map(item => item['溢价率'])
    const positiveCount = premiums.filter(p => p > 0).length
    const pausedCount = list.filter(item => item['申购状态'] === '暂停').length

    return {
      count: list.length,
      premium_avg: Math.round((premiums.reduce((a, b) => a + b, 0) / premiums.length) * 100) / 100,
      top_premium: Math.round(Math.max(...premiums) * 100) / 100,
      positive_count: positiveCount,
      positive_rate: Math.round((positiveCount / list.length) * 1000) / 10,
      paused_count: pausedCount
    }
  } catch (err) {
    console.error('获取LOF市场概览失败:', err.message)
    return null
  }
}

// ==================== Mock回退 ====================

function mockLofSummary() {
  const list = mock.LOF_LIST
  const premiums = list.map(item => item['溢价率'])
  const positiveCount = premiums.filter(p => p > 0).length
  return {
    count: list.length,
    premium_avg: Math.round((premiums.reduce((a, b) => a + b, 0) / premiums.length) * 100) / 100,
    top_premium: Math.max(...premiums),
    positive_count: positiveCount,
    positive_rate: Math.round((positiveCount / list.length) * 1000) / 10,
    paused_count: list.filter(item => item['申购状态'] === '暂停').length
  }
}

module.exports = {
  getLofList,
  getLofOpportunities,
  getLofMarketSummary,
  mockLofSummary
}
