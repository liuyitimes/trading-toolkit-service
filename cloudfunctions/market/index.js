// 市场数据云函数
const cb = require('./data/convertible')
const lof = require('./data/lof')
const hkipo = require('./data/hkipo')
const mock = require('./data/mock')

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

      default:
        return { success: false, error: `未知action: ${action}` }
    }
  } catch (err) {
    console.error('云函数执行失败:', err)
    return { success: false, error: err.message }
  }
}
