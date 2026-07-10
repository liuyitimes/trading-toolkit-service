const { runAllTests, runSingleTest, getTestCases } = require('../../utils/testRunner')

Page({
  data: {
    tests: [],
    results: [],
    running: false,
    runAllBtnText: '运行全部测试',
    summary: {
      total: 0,
      pass: 0,
      fail: 0,
      error: 0,
      duration: 0
    }
  },

  onLoad() {
    const tests = getTestCases().map(t => ({
      ...t,
      status: 'pending',
      duration: 0,
      error: null,
      dataSample: null
    }))
    this.setData({
      tests,
      'summary.total': tests.length
    })
  },

  async onRunAll() {
    if (this.data.running) return

    this.setData({
      running: true,
      runAllBtnText: '测试中...',
      results: []
    })

    const allResults = []
    const startTime = Date.now()
    let pass = 0, fail = 0, error = 0

    for (let i = 0; i < this.data.tests.length; i++) {
      const testCase = this.data.tests[i]
      const key = `tests[${i}]`

      this.setData({
        [`${key}.status`]: 'running'
      })

      const result = await runSingleTest(testCase)

      this.setData({
        [`${key}.status`]: result.status,
        [`${key}.duration`]: result.duration,
        [`${key}.error`]: result.error,
        [`${key}.dataSample`]: result.dataSample
      })

      allResults.push(result)
      if (result.status === 'pass') pass++
      else if (result.status === 'fail') fail++
      else error++
    }

    const totalDuration = Date.now() - startTime

    this.setData({
      running: false,
      runAllBtnText: '重新运行全部测试',
      results: allResults,
      summary: {
        total: this.data.tests.length,
        pass,
        fail,
        error,
        duration: totalDuration
      }
    })
  },

  async onRunSingle(e) {
    if (this.data.running) return

    const { id, index } = e.currentTarget.dataset
    const key = `tests[${index}]`

    this.setData({
      [`${key}.status`]: 'running',
      [`${key}.duration`]: 0,
      [`${key}.error`]: null,
      [`${key}.dataSample`]: null
    })

    const testCase = this.data.tests[index]
    const result = await runSingleTest(testCase)

    this.setData({
      [`${key}.status`]: result.status,
      [`${key}.duration`]: result.duration,
      [`${key}.error`]: result.error,
      [`${key}.dataSample`]: result.dataSample
    })
  },

  onCopyLog(e) {
    const { index } = e.currentTarget.dataset
    const test = this.data.tests[index]
    const log = `
[${test.status.toUpperCase()}] ${test.name}
action: ${test.action}
耗时: ${test.duration}ms
${test.error ? '错误: ' + test.error : ''}
${test.dataSample ? '数据样例: ' + test.dataSample : ''}
    `.trim()
    wx.setClipboardData({
      data: log,
      success: () => {
        wx.showToast({ title: '已复制', icon: 'success' })
      }
    })
  },

  onExportAll() {
    const lines = this.data.tests.map(t => {
      const icon = t.status === 'pass' ? '✅' : t.status === 'fail' ? '❌' : t.status === 'error' ? '💥' : '⏳'
      return `${icon} ${t.name} (${t.action}) - ${t.duration}ms${t.error ? '\n   ' + t.error : ''}`
    })

    const summary = `
=== 测试报告 ===
总计: ${this.data.summary.total}
通过: ${this.data.summary.pass}
失败: ${this.data.summary.fail}
错误: ${this.data.summary.error}
总耗时: ${this.data.summary.duration}ms
    `.trim()

    const fullLog = summary + '\n\n' + lines.join('\n')

    wx.setClipboardData({
      data: fullLog,
      success: () => {
        wx.showToast({ title: '测试报告已复制', icon: 'success' })
      }
    })
  }
})
