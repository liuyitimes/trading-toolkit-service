// 可转债数据获取 - 东方财富API
const axios = require('axios')
const mock = require('./mock')

// 根据正股代码判断交易所
function getExchangeByCode(code) {
  const codeStr = String(code)
  if (codeStr.startsWith('6') || codeStr.startsWith('5') || codeStr.startsWith('9') || codeStr.startsWith('11') || codeStr.startsWith('13')) {
    return '沪'
  } else if (codeStr.startsWith('0') || codeStr.startsWith('1') || codeStr.startsWith('2') || codeStr.startsWith('3') || codeStr.startsWith('12')) {
    return '深'
  } else if (codeStr.startsWith('4') || codeStr.startsWith('8')) {
    return '北'
  }
  return ''
}

function safeFloat(val, defaultVal = 0) {
  const num = parseFloat(val)
  return isNaN(num) ? defaultVal : num
}

// 从东方财富获取可转债数据
async function fetchConvertibleBonds() {
  const url = 'https://datacenter-web.eastmoney.com/api/data/v1/get'
  const params = {
    reportName: 'RPT_BOND_CB_LIST',
    columns: 'ALL',
    pageSize: 500,
    pageNumber: 1,
    sortColumns: 'DOUBLE_LOW',
    sortTypes: 1,
    source: 'WEB',
    client: 'WEB'
  }

  const res = await axios.get(url, { params, timeout: 10000 })
  if (!res.data || !res.data.success || !res.data.result || !res.data.result.data) {
    throw new Error('东方财富API返回数据格式异常')
  }

  const rows = res.data.result.data
  return rows.map(row => ({
    转债代码: String(row.BOND_CODE || ''),
    转债名称: String(row.BOND_NAME || ''),
    转债价格: safeFloat(row.PRICE),
    正股名称: String(row.SECURITY_NAME || ''),
    正股代码: String(row.SECURITY_CODE || ''),
    交易所: getExchangeByCode(row.SECURITY_CODE),
    转股价值: safeFloat(row.CONVERSION_VALUE),
    转股溢价率: safeFloat(row.PREMIUM_RATIO),
    双低: safeFloat(row.DOUBLE_LOW)
  }))
}

// 获取市场温度
async function getMarketTemperature() {
  try {
    const bonds = await fetchConvertibleBonds()
    if (!bonds.length) return null

    const prices = bonds.map(b => b['转债价格']).filter(p => p > 0)
    const premiums = bonds.map(b => b['转股溢价率']).filter(p => p !== 0)
    const doubleLows = bonds.map(b => b['双低']).filter(d => d > 0)

    const median = arr => {
      const sorted = [...arr].sort((a, b) => a - b)
      return sorted[Math.floor(sorted.length / 2)]
    }

    const priceMedian = median(prices)
    const premiumMedian = median(premiums)
    const doubleLowMedian = median(doubleLows)

    let marketStatus = '偏高，需谨慎'
    if (doubleLowMedian < 150) marketStatus = '偏低，可关注'
    else if (doubleLowMedian < 180) marketStatus = '合理，可适当关注'

    return {
      count: bonds.length,
      price_min: Math.min(...prices),
      price_max: Math.max(...prices),
      price_median: Math.round(priceMedian * 100) / 100,
      premium_median: Math.round(premiumMedian * 100) / 100,
      double_low_median: Math.round(doubleLowMedian * 10) / 10,
      market_status: marketStatus
    }
  } catch (err) {
    console.error('获取可转债市场温度失败:', err.message)
    return null
  }
}

// 获取可转债列表
async function getConvertibleBondList() {
  try {
    return await fetchConvertibleBonds()
  } catch (err) {
    console.error('获取可转债列表失败:', err.message)
    return []
  }
}

// 获取可转债信号
async function getConvertibleBondSignals() {
  try {
    const bonds = await fetchConvertibleBonds()
    if (!bonds.length) return null

    const doubleLow = [...bonds].sort((a, b) => a['双低'] - b['双低']).slice(0, 20)
    const forceRedeem = bonds.filter(b => b['转股溢价率'] < 10 && b['转债价格'] >= 105 && b['转债价格'] <= 140).slice(0, 10)
    const discount = bonds.filter(b => b['转股溢价率'] < 0).slice(0, 10)
    const downRevised = bonds.filter(b => b['转股溢价率'] > 50 && b['转债价格'] < 115).slice(0, 10)

    return {
      double_low: doubleLow,
      force_redeem: forceRedeem,
      discount: discount,
      down_revised: downRevised
    }
  } catch (err) {
    console.error('获取可转债信号失败:', err.message)
    return null
  }
}

// ==================== Mock回退 ====================

function mockMarketTemperature() {
  const bonds = mock.CONVERTIBLE_BOND_LIST
  const prices = bonds.map(b => b['转债价格'])
  const premiums = bonds.map(b => b['转股溢价率'])
  const doubleLows = bonds.map(b => b['双低'])

  const priceMedian = prices.sort((a, b) => a - b)[Math.floor(prices.length / 2)]
  const premiumMedian = premiums.sort((a, b) => a - b)[Math.floor(premiums.length / 2)]
  const doubleLowMedian = doubleLows.sort((a, b) => a - b)[Math.floor(doubleLows.length / 2)]

  let marketStatus = '偏高，需谨慎'
  if (doubleLowMedian < 150) marketStatus = '偏低，可关注'
  else if (doubleLowMedian < 180) marketStatus = '合理，可适当关注'

  return {
    count: bonds.length,
    price_min: Math.min(...prices),
    price_max: Math.max(...prices),
    price_median: Math.round(priceMedian * 100) / 100,
    premium_median: Math.round(premiumMedian * 100) / 100,
    double_low_median: Math.round(doubleLowMedian * 10) / 10,
    market_status: marketStatus
  }
}

function mockCbSignals() {
  const data = mock.CONVERTIBLE_BOND_LIST.map(item => ({
    ...item,
    交易所: item['交易所'] || getExchangeByCode(item['正股代码'])
  }))

  return {
    double_low: [...data].sort((a, b) => a['双低'] - b['双低']).slice(0, 20),
    force_redeem: data.filter(b => b['转股溢价率'] < 10 && b['转债价格'] >= 105 && b['转债价格'] <= 140).slice(0, 10),
    discount: data.filter(b => b['转股溢价率'] < 0).slice(0, 10),
    down_revised: data.filter(b => b['转股溢价率'] > 50 && b['转债价格'] < 115).slice(0, 10)
  }
}

module.exports = {
  getMarketTemperature,
  getConvertibleBondList,
  getConvertibleBondSignals,
  mockMarketTemperature,
  mockCbSignals,
  getExchangeByCode
}
