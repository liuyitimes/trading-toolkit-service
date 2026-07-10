// 市场数据云函数
const cb = require('./data/convertible')
const lof = require('./data/lof')
const hkipo = require('./data/hkipo')
const mock = require('./data/mock')
const axios = require('axios')

// 云托管后端地址（优先从环境变量获取）
const CLOUDRUN_BASE_URL = process.env.CLOUDRUN_BASE_URL || 'http://localhost:8080'

// 调用云托管后端接口，失败返回 null
async function callCloudRun(path, params = {}) {
  try {
    const url = `${CLOUDRUN_BASE_URL}${path}`
    const res = await axios.get(url, { params, timeout: 8000 })
    if (res.data && res.data.success !== false) {
      return res.data.data || res.data
    }
    return null
  } catch (err) {
    console.error(`云托管调用失败 ${path}:`, err.message)
    return null
  }
}

exports.main = async (event, context) => {
  const { action } = event

  try {
    switch (action) {
      // ==================== 市场概览 ====================
      case 'overview': {
        let cbTemp = await cb.getMarketTemperature()
        if (!cbTemp) cbTemp = cb.mockMarketTemperature()

        let lofSummary = await lof.getLofMarketSummary()
        if (!lofSummary) lofSummary = lof.mockLofSummary()

        const hkSummary = hkipo.getHkIpoSummary()

        return {
          success: true,
          data: {
            convertible_bond: cbTemp,
            lof_fund: lofSummary,
            hk_ipo: hkSummary,
            market_sentiment: mock.MARKET_SENTIMENT,
            fund_flow: mock.FUND_FLOW
          }
        }
      }

      // ==================== 可转债 ====================
      case 'convertibleList': {
        const data = await cb.getConvertibleBondList()
        if (!data.length) {
          return { success: true, data: mock.CONVERTIBLE_BOND_LIST }
        }
        return { success: true, data }
      }

      case 'convertibleSignals': {
        const data = await cb.getConvertibleBondSignals()
        if (!data) {
          return { success: true, data: cb.mockCbSignals() }
        }
        return { success: true, data }
      }

      // ==================== LOF基金 ====================
      case 'lofList': {
        const data = await lof.getLofList()
        if (!data.length) {
          return { success: true, data: mock.LOF_LIST }
        }
        return { success: true, data }
      }

      case 'lofOpportunities': {
        const data = await lof.getLofOpportunities()
        if (!data.premium.length && !data.discount.length) {
          const sorted = [...mock.LOF_LIST].sort((a, b) => b['溢价率'] - a['溢价率'])
          return {
            success: true,
            data: {
              premium: sorted.slice(0, 20),
              discount: [...sorted].reverse().slice(0, 20)
            }
          }
        }
        return { success: true, data }
      }

      // ==================== 港股IPO ====================
      case 'hkipoList': {
        return { success: true, data: hkipo.getHkIpoList() }
      }

      case 'hkipoUpcoming': {
        return { success: true, data: hkipo.getHkIpoUpcoming() }
      }

      // ==================== 健康检查 ====================
      case 'health': {
        return {
          success: true,
          data: {
            status: 'ok',
            time: new Date().toISOString()
          }
        }
      }

      // ==================== 可转债待发/配售 ====================
      case 'convertiblePending': {
        // 先尝试调用云托管后端
        const pendingData = await callCloudRun('/api/v1/convertible/pending')
        if (pendingData) {
          return { success: true, data: pendingData, source: 'cloudrun' }
        }
        return { success: true, data: [], source: 'none' }
      }

      // ==================== 可转债详情（云托管） ====================
      case 'convertibleDetail': {
        const bondCode = event.code || event.bondCode || ''
        if (!bondCode) {
          return { success: false, error: '缺少可转债代码参数' }
        }

        // 先尝试调用云托管后端
        const backendData = await callCloudRun(`/api/v1/convertible/detail/${bondCode}`)
        if (backendData) {
          return { success: true, data: backendData, source: 'cloudrun' }
        }

        // 云托管失败时，使用本地 mock 数据兜底
        const mockBond = mock.CONVERTIBLE_BOND_LIST.find(
          b => String(b['转债代码']) === String(bondCode)
        )
        if (mockBond) {
          const codeHash = String(bondCode).split('').reduce((sum, c) => sum + c.charCodeAt(0), 0)
          const price = mockBond['转债价格'] || 0
          const cv = mockBond['转股价值'] || 0
          return {
            success: true,
            data: {
              ...mockBond,
              pure_bond_value: Math.round((90 + (codeHash % 100) / 10) * 100) / 100,
              conversion_price: cv > 0 ? Math.round(100 * price / cv * 100) / 100 : 0,
              rating: price >= 150 ? 'A+' : price >= 120 ? 'AA' : price >= 100 ? 'AA+' : 'AAA',
              maturity_date: `${2028 + (codeHash % 5)}-${String(1 + (codeHash % 12)).padStart(2, '0')}-${String(1 + (codeHash % 28)).padStart(2, '0')}`
            },
            source: 'mock'
          }
        }
        return { success: false, error: `可转债 ${bondCode} 不存在` }
      }

      // ==================== 新债列表（云托管） ====================
      case 'convertibleNewBonds': {
        // 先尝试调用云托管后端
        const backendData = await callCloudRun('/api/v1/convertible/list', { new_bonds: true })
        if (backendData) {
          return { success: true, data: backendData, source: 'cloudrun' }
        }

        // 云托管失败时，使用本地 mock 数据兜底
        // 筛选价格接近100的新债（通常新上市可转债价格在100附近）
        const newBonds = mock.CONVERTIBLE_BOND_LIST
          .filter(b => b['转债价格'] <= 105 && b['转债价格'] >= 95)
          .sort((a, b) => a['转债价格'] - b['转债价格'])
        return {
          success: true,
          data: {
            total: newBonds.length,
            page: 1,
            page_size: 100,
            items: newBonds
          },
          source: 'mock'
        }
      }

      // ==================== 市场情绪（云托管） ====================
      case 'sentiment': {
        // 先尝试调用云托管后端
        const backendData = await callCloudRun('/api/v1/market/sentiment')
        if (backendData) {
          return { success: true, data: backendData, source: 'cloudrun' }
        }

        // 云托管失败时，使用本地 mock 数据兜底
        return { success: true, data: mock.MARKET_SENTIMENT, source: 'mock' }
      }

      // ==================== 资金流向（云托管） ====================
      case 'fundFlow': {
        // 先尝试调用云托管后端
        const backendData = await callCloudRun('/api/v1/market/fund-flow')
        if (backendData) {
          return { success: true, data: backendData, source: 'cloudrun' }
        }

        // 云托管失败时，使用本地 mock 数据兜底
        return { success: true, data: mock.FUND_FLOW, source: 'mock' }
      }

      default:
        return { success: false, error: `未知action: ${action}` }
    }
  } catch (err) {
    console.error('云函数执行失败:', err)
    return { success: false, error: err.message }
  }
}
