/**
 * 接口测试脚本 - Node.js 环境运行
 * 用法: node test-api.js [cloudrun-url]
 * 示例: node test-api.js http://localhost:8080
 */

const axios = require('axios')

const BASE_URL = process.argv[2] || 'http://localhost:8080'

const TEST_CASES = [
  {
    id: 'health',
    name: '健康检查',
    path: '/api/health',
    check: (data) => {
      const errors = []
      if (!data) errors.push('返回空')
      if (data && !data.status) errors.push('缺少 status 字段')
      return errors
    }
  },
  {
    id: 'overview',
    name: '市场概览',
    path: '/api/market/overview',
    check: (data) => {
      const errors = []
      if (!data) return ['返回空']
      if (!data.convertible_bond) errors.push('缺少 convertible_bond')
      if (!data.lof_fund) errors.push('缺少 lof_fund')
      if (!data.hk_ipo) errors.push('缺少 hk_ipo')
      if (!data.market_sentiment) errors.push('缺少 market_sentiment')
      if (!data.fund_flow) errors.push('缺少 fund_flow')
      return errors
    }
  },
  {
    id: 'convertibleList',
    name: '可转债列表',
    path: '/api/convertible/list',
    check: (data) => {
      const errors = []
      if (!data) return ['返回空']
      if (!Array.isArray(data)) return ['不是数组']
      if (data.length === 0) errors.push('数组为空')
      if (data.length > 0) {
        const item = data[0]
        const fields = ['转债代码', '转债名称', '转债价格']
        fields.forEach(f => {
          if (item[f] === undefined) errors.push('缺少字段: ' + f)
        })
      }
      return errors
    }
  },
  {
    id: 'convertibleSignals',
    name: '可转债信号',
    path: '/api/convertible/signals',
    check: (data) => {
      const errors = []
      if (!data) return ['返回空']
      const signals = ['double_low', 'force_redeem', 'discount', 'down_revised']
      signals.forEach(s => {
        if (!data[s]) errors.push('缺少 ' + s)
        else if (!Array.isArray(data[s])) errors.push(s + ' 不是数组')
      })
      return errors
    }
  },
  {
    id: 'lofList',
    name: 'LOF基金列表',
    path: '/api/lof/list',
    check: (data) => {
      const errors = []
      if (!data) return ['返回空']
      if (!Array.isArray(data)) return ['不是数组']
      if (data.length === 0) errors.push('数组为空')
      return errors
    }
  },
  {
    id: 'lofOpportunities',
    name: 'LOF套利机会',
    path: '/api/lof/opportunities',
    check: (data) => {
      const errors = []
      if (!data) return ['返回空']
      if (!data.premium) errors.push('缺少 premium')
      if (!data.discount) errors.push('缺少 discount')
      return errors
    }
  },
  {
    id: 'hkipoList',
    name: '港股IPO列表',
    path: '/api/hkipo/list',
    check: (data) => {
      const errors = []
      if (!data) return ['返回空']
      if (!Array.isArray(data)) return ['不是数组']
      return errors
    }
  },
  {
    id: 'hkipoUpcoming',
    name: '即将上市IPO',
    path: '/api/hkipo/upcoming',
    check: (data) => {
      const errors = []
      if (!data) return ['返回空']
      if (!Array.isArray(data)) return ['不是数组']
      return errors
    }
  }
]

async function runTest(testCase) {
  const url = BASE_URL + testCase.path
  const startTime = Date.now()
  let data = null
  let error = null
  let status = 'pending'
  let httpStatus = null

  try {
    const response = await axios.get(url, { timeout: 10000 })
    httpStatus = response.status
    data = response.data
    const checkErrors = testCase.check(data)
    if (checkErrors.length === 0) {
      status = 'pass'
    } else {
      status = 'fail'
      error = checkErrors.join('; ')
    }
  } catch (err) {
    status = 'error'
    if (err.response) {
      httpStatus = err.response.status
      error = `HTTP ${err.response.status}: ${err.response.statusText}`
    } else if (err.code === 'ECONNREFUSED') {
      error = '连接被拒绝，请确认服务已启动'
    } else if (err.code === 'ETIMEDOUT') {
      error = '请求超时'
    } else {
      error = err.message
    }
  }

  const duration = Date.now() - startTime

  return {
    id: testCase.id,
    name: testCase.name,
    path: testCase.path,
    status,
    httpStatus,
    error,
    duration,
    dataSample: data ? JSON.stringify(data).substring(0, 150) : null
  }
}

async function main() {
  console.log('='.repeat(60))
  console.log('  接口自动化测试')
  console.log('  目标地址: ' + BASE_URL)
  console.log('='.repeat(60))
  console.log()

  let pass = 0, fail = 0, error = 0
  const allStart = Date.now()

  for (let i = 0; i < TEST_CASES.length; i++) {
    const tc = TEST_CASES[i]
    const index = String(i + 1).padStart(2, '0')

    process.stdout.write(`[${index}/${TEST_CASES.length}] 测试 ${tc.name} ... `)
    const result = await runTest(tc)

    const icon = result.status === 'pass' ? '✅' : result.status === 'fail' ? '❌' : '💥'
    console.log(`${icon} ${result.duration}ms`)

    if (result.status === 'pass') pass++
    else if (result.status === 'fail') fail++
    else error++

    if (result.error) {
      console.log('       错误: ' + result.error)
    }
    if (result.dataSample) {
      console.log('       样例: ' + result.dataSample + (result.dataSample.length >= 150 ? '...' : ''))
    }
    console.log()
  }

  const totalDuration = Date.now() - allStart

  console.log('='.repeat(60))
  console.log('  测试结果汇总')
  console.log('='.repeat(60))
  console.log(`  总计:   ${TEST_CASES.length}`)
  console.log(`  通过:   ${pass}  ✅`)
  console.log(`  失败:   ${fail}  ❌`)
  console.log(`  错误:   ${error}  💥`)
  console.log(`  耗时:   ${totalDuration}ms`)
  console.log()

  if (fail + error > 0) {
    console.log('  ❌ 测试不通过！请检查上述错误。')
    process.exit(1)
  } else {
    console.log('  ✅ 全部测试通过！')
    process.exit(0)
  }
}

main().catch(err => {
  console.error('测试运行失败:', err)
  process.exit(2)
})
