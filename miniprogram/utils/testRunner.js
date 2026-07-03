const { callMarket } = require('./cloudApi')

const TEST_CASES = [
  {
    id: 'overview',
    name: '市场概览接口',
    action: 'overview',
    check: (data) => {
      const errors = []
      if (!data) return ['返回数据为空']
      if (!data.convertible_bond) errors.push('缺少 convertible_bond 字段')
      if (!data.lof_fund) errors.push('缺少 lof_fund 字段')
      if (!data.hk_ipo) errors.push('缺少 hk_ipo 字段')
      if (!data.market_sentiment) errors.push('缺少 market_sentiment 字段')
      if (!data.fund_flow) errors.push('缺少 fund_flow 字段')
      if (data.convertible_bond) {
        if (typeof data.convertible_bond.count !== 'number') errors.push('convertible_bond.count 不是数字')
      }
      return errors
    }
  },
  {
    id: 'convertibleList',
    name: '可转债列表接口',
    action: 'convertibleList',
    check: (data) => {
      const errors = []
      if (!data) return ['返回数据为空']
      if (!Array.isArray(data)) return ['返回数据不是数组']
      if (data.length === 0) errors.push('数组为空')
      if (data.length > 0) {
        const item = data[0]
        const requiredFields = ['转债代码', '转债名称', '转债价格', '转股溢价率']
        requiredFields.forEach(f => {
          if (item[f] === undefined) errors.push(`缺少字段: ${f}`)
        })
      }
      return errors
    }
  },
  {
    id: 'convertibleSignals',
    name: '可转债信号接口',
    action: 'convertibleSignals',
    check: (data) => {
      const errors = []
      if (!data) return ['返回数据为空']
      const signals = ['double_low', 'force_redeem', 'discount', 'down_revised']
      signals.forEach(s => {
        if (!data[s]) errors.push(`缺少 ${s} 信号`)
        else if (!Array.isArray(data[s])) errors.push(`${s} 不是数组`)
        else if (data[s].length === 0) errors.push(`${s} 数组为空`)
      })
      return errors
    }
  },
  {
    id: 'lofList',
    name: 'LOF基金列表接口',
    action: 'lofList',
    check: (data) => {
      const errors = []
      if (!data) return ['返回数据为空']
      if (!Array.isArray(data)) return ['返回数据不是数组']
      if (data.length === 0) errors.push('数组为空')
      if (data.length > 0) {
        const item = data[0]
        const hasName = item.name || item['基金名称'] || item.f14
        const hasCode = item.code || item['基金代码'] || item.f12
        if (!hasName) errors.push('缺少名称字段')
        if (!hasCode) errors.push('缺少代码字段')
      }
      return errors
    }
  },
  {
    id: 'lofOpportunities',
    name: 'LOF套利机会接口',
    action: 'lofOpportunities',
    check: (data) => {
      const errors = []
      if (!data) return ['返回数据为空']
      if (!data.premium) errors.push('缺少 premium 字段')
      if (!data.discount) errors.push('缺少 discount 字段')
      if (data.premium && !Array.isArray(data.premium)) errors.push('premium 不是数组')
      if (data.discount && !Array.isArray(data.discount)) errors.push('discount 不是数组')
      return errors
    }
  },
  {
    id: 'hkipoList',
    name: '港股IPO列表接口',
    action: 'hkipoList',
    check: (data) => {
      const errors = []
      if (!data) return ['返回数据为空']
      if (!Array.isArray(data)) return ['返回数据不是数组']
      if (data.length > 0) {
        const item = data[0]
        if (!item.name && !item.stock_name) errors.push('缺少名称字段')
        if (!item.code && !item.stock_code) errors.push('缺少代码字段')
      }
      return errors
    }
  },
  {
    id: 'hkipoUpcoming',
    name: '即将上市IPO接口',
    action: 'hkipoUpcoming',
    check: (data) => {
      const errors = []
      if (!data) return ['返回数据为空']
      if (!Array.isArray(data)) return ['返回数据不是数组']
      return errors
    }
  },
  {
    id: 'health',
    name: '健康检查接口',
    action: 'health',
    check: (data) => {
      const errors = []
      if (!data) return ['返回数据为空']
      if (!data.status) errors.push('缺少 status 字段')
      return errors
    }
  }
]

async function runAllTests() {
  const results = []
  for (const testCase of TEST_CASES) {
    const result = await runSingleTest(testCase)
    results.push(result)
  }
  return results
}

async function runSingleTest(testCase) {
  const startTime = Date.now()
  let data = null
  let error = null
  let status = 'pending'

  try {
    data = await callMarket(testCase.action)
    const checkErrors = testCase.check(data)
    if (checkErrors.length === 0) {
      status = 'pass'
    } else {
      status = 'fail'
      error = checkErrors.join('; ')
    }
  } catch (err) {
    status = 'error'
    error = err.message || String(err)
  }

  const duration = Date.now() - startTime

  return {
    id: testCase.id,
    name: testCase.name,
    action: testCase.action,
    status,
    error,
    duration,
    dataSample: data ? JSON.stringify(data).substring(0, 200) : null
  }
}

function getTestCases() {
  return TEST_CASES.map(t => ({ id: t.id, name: t.name, action: t.action }))
}

module.exports = {
  runAllTests,
  runSingleTest,
  getTestCases,
  TEST_CASES
}
