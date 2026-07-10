const config = require('../../config')
const env = config.autoSwitch ? 'development' : (config.currentEnv || 'development')
const FALLBACK_BASE_URL = config[env].baseUrl

// 运行时获取 BASE_URL：优先用 app.getCloudRunUrl()（用户在设置页配置的地址）
function getBaseUrl() {
  try {
    const app = getApp()
    if (app && typeof app.getCloudRunUrl === 'function') {
      const url = app.getCloudRunUrl()
      if (url) return url.replace(/\/+$/, '')
    }
  } catch (e) {}
  return FALLBACK_BASE_URL
}

// 检测后端地址是否为占位符/无效配置
function analyzeBaseUrl(url) {
  if (!url) return { valid: false, type: 'empty', hint: '后端地址为空，请先到「设置」页配置云托管地址' }
  if (url.indexOf('your-service-id') !== -1 || url.indexOf('example.com') !== -1) {
    return { valid: false, type: 'placeholder', hint: '后端地址为占位符，请到「设置」页填写真实地址' }
  }
  if (url.indexOf('localhost') !== -1 || url.indexOf('127.0.0.1') !== -1) {
    return { valid: true, type: 'localhost', hint: '使用本机地址，请确认后端服务正在运行' }
  }
  // 局域网 IP（192.168 / 10. / 172.）
  if (/https?:\/\/(192\.168|10\.|172\.(1[6-9]|2\d|3[01]))\./.test(url)) {
    return { valid: true, type: 'lan', hint: '使用局域网地址，请确认手机与电脑在同一网络，且电脑 IP 正确' }
  }
  if (url.indexOf('https://') === 0) {
    return { valid: true, type: 'cloud', hint: '使用云托管地址，请确认服务已部署' }
  }
  return { valid: true, type: 'http', hint: '使用 HTTP 地址，请确认服务可访问' }
}

// 解析 wx.request fail 的 errMsg，给出人类可读原因
function parseRequestError(err, baseUrlInfo) {
  const msg = (err && err.errMsg) || String(err || '未知错误')
  // 微信常见错误
  if (msg.indexOf('timeout') !== -1) {
    return { title: '请求超时', detail: '后端响应超过 10 秒，可能服务卡死或网络过慢', code: 'timeout' }
  }
  if (msg.indexOf('fail to connect') !== -1 || msg.indexOf('ECONNREFUSED') !== -1 || msg.indexOf('refused') !== -1) {
    if (baseUrlInfo.type === 'localhost') {
      return { title: '无法连接本机后端', detail: '后端服务未启动或端口不对，请确认已运行 python app.py', code: 'refused' }
    }
    if (baseUrlInfo.type === 'lan') {
      return { title: '无法连接后端', detail: '电脑 IP 变更、防火墙拦截或手机与电脑不在同一网络', code: 'refused' }
    }
    return { title: '无法连接后端', detail: '服务未部署或地址不可达', code: 'refused' }
  }
  if (msg.indexOf('url not in domain list') !== -1) {
    return { title: '域名未配置', detail: '请在微信开发者工具中勾选「不校验合法域名」，或在后台配置 request 合法域名', code: 'domain' }
  }
  if (msg.indexOf('net::ERR_') !== -1 || msg.indexOf('ERR_') !== -1) {
    return { title: '网络错误', detail: msg, code: 'net' }
  }
  return { title: '请求失败', detail: msg, code: 'other' }
}

Page({
  data: {
    logs: [],
    total: 0,
    page: 1,
    pageSize: 30,
    hasMore: false,
    search: '',
    loading: false,
    // 连接状态：unknown / checking / connected / failed
    connStatus: 'unknown',
    errorMsg: '',
    errorTitle: '',
    errorDetail: '',
    errorCode: '',
    baseUrl: FALLBACK_BASE_URL,
    baseUrlInfo: analyzeBaseUrl(FALLBACK_BASE_URL),
    pingDuration: null,
  },

  onLoad() {
    // 用运行时的真实地址（用户在设置页配置的优先）更新一下显示
    const realUrl = getBaseUrl()
    this.setData({ baseUrl: realUrl, baseUrlInfo: analyzeBaseUrl(realUrl) })
    // 先做连通性预检，再拉日志
    this.pingAndFetch()
  },

  onPullDownRefresh() {
    this.pingAndFetch(() => wx.stopPullDownRefresh())
  },

  // 连通性预检：用 health 接口快速探测后端是否可达（短超时 4s）
  pingAndFetch(cb) {
    if (this.data.loading) {
      cb && cb()
      return
    }
    if (!this.data.baseUrlInfo.valid) {
      this.setData({
        connStatus: 'failed',
        errorTitle: '后端地址无效',
        errorDetail: this.data.baseUrlInfo.hint,
        errorCode: 'invalid_url',
        loading: false,
      })
      cb && cb()
      return
    }
    this.setData({ connStatus: 'checking', loading: true, errorTitle: '', errorMsg: '', errorDetail: '' })
    const BASE_URL = getBaseUrl()
    // 同步更新显示的地址（用户可能刚在设置页改过）
    this.setData({ baseUrl: BASE_URL, baseUrlInfo: analyzeBaseUrl(BASE_URL) })
    const pingStart = Date.now()
    wx.request({
      url: `${BASE_URL}/api/v1/admin/health`,
      method: 'GET',
      timeout: 4000,
      success: (res) => {
        const pingMs = Date.now() - pingStart
        if (res.statusCode === 200 && res.data && res.data.success) {
          this.setData({ connStatus: 'connected', pingDuration: pingMs })
          this.fetchLogs(cb)
        } else {
          this.setData({
            connStatus: 'failed',
            loading: false,
            errorTitle: `后端响应异常 (HTTP ${res.statusCode})`,
            errorDetail: '后端可达但返回了非预期内容，可能是服务内部错误',
            errorCode: 'bad_response',
          })
          cb && cb()
        }
      },
      fail: (err) => {
        const parsed = parseRequestError(err, this.data.baseUrlInfo)
        this.setData({
          connStatus: 'failed',
          loading: false,
          errorTitle: parsed.title,
          errorDetail: parsed.detail + '\n地址: ' + BASE_URL,
          errorCode: parsed.code,
        })
        cb && cb()
      },
    })
  },

  fetchLogs(cb) {
    this.setData({ loading: true, errorMsg: '' })
    const BASE_URL = getBaseUrl()
    const { page, pageSize, search } = this.data
    let url = `${BASE_URL}/api/v1/admin/api-logs?page=${page}&page_size=${pageSize}`
    if (search) url += `&search=${encodeURIComponent(search)}`

    wx.request({
      url,
      method: 'GET',
      timeout: 10000,
      success: (res) => {
        if (res.statusCode === 200 && res.data && res.data.success) {
          const data = res.data.data || {}
          const newLogs = (data.logs || []).map(l => ({
            ...l,
            expanded: false,
            request_body_view: l.request_body || '',
            response_body_view: l.response_body || '(无响应数据)',
            truncated: !!l.truncated,
          }))
          const mergedLogs = page === 1 ? newLogs : [...this.data.logs, ...newLogs]
          this.setData({
            logs: mergedLogs,
            total: data.total || 0,
            hasMore: !!data.has_more,
          })
        } else {
          this.setData({
            errorMsg: `服务异常：HTTP ${res.statusCode}` + (res.data && res.data.error ? `，${res.data.error.message}` : ''),
          })
        }
      },
      fail: (err) => {
        console.error('获取日志失败:', err)
        const parsed = parseRequestError(err, this.data.baseUrlInfo)
        this.setData({
          connStatus: 'failed',
          errorTitle: parsed.title,
          errorDetail: parsed.detail,
          errorCode: parsed.code,
        })
      },
      complete: () => {
        this.setData({ loading: false })
        cb && cb()
      },
    })
  },

  doRefresh() {
    this.setData({ page: 1, errorMsg: '', errorTitle: '', errorDetail: '' })
    this.pingAndFetch()
  },

  loadMore() {
    if (this.data.loading || !this.data.hasMore) return
    this.setData({ page: this.data.page + 1 }, () => this.fetchLogs())
  },

  onSearchInput(e) {
    this.setData({ search: e.detail.value })
  },

  doSearch() {
    this.setData({ page: 1 }, () => this.fetchLogs())
  },

  clearSearch() {
    this.setData({ search: '', page: 1 }, () => this.fetchLogs())
  },

  toggleExpand(e) {
    const index = e.currentTarget.dataset.index
    if (typeof index !== 'number' && typeof index !== 'string') return
    const idx = Number(index)
    const logs = this.data.logs
    if (!logs[idx]) return
    const key = `logs[${idx}].expanded`
    this.setData({ [key]: !logs[idx].expanded })
  },

  clearLogs() {
    if (this.data.connStatus !== 'connected') {
      wx.showToast({ title: '后端未连接', icon: 'none' })
      return
    }
    const BASE_URL = getBaseUrl()
    wx.showModal({
      title: '确认清空',
      content: '确定要清空所有接口日志吗？',
      success: (res) => {
        if (res.confirm) {
          wx.request({
            url: `${BASE_URL}/api/v1/admin/api-logs/clear`,
            method: 'POST',
            timeout: 10000,
            success: (r) => {
              if (r.statusCode === 200 && r.data && r.data.success) {
                this.setData({ logs: [], total: 0, hasMore: false, page: 1 })
                wx.showToast({ title: '已清空', icon: 'success' })
              } else {
                wx.showToast({ title: '清空失败', icon: 'none' })
              }
            },
            fail: () => {
              wx.showToast({ title: '清空失败', icon: 'none' })
            }
          })
        }
      }
    })
  },

  copyLog(e) {
    const index = Number(e.currentTarget.dataset.index)
    const log = this.data.logs[index]
    if (!log) return
    const text = `[${log.method}] ${log.path}\n状态: ${log.status}  耗时: ${log.duration}ms  时间: ${log.time}\n\n[请求正文]\n${log.request_body_view || '(无)'}\n\n[响应数据]\n${log.response_body_view || '(无)'}`
    wx.setClipboardData({
      data: text,
      success: () => wx.showToast({ title: '已复制', icon: 'success' })
    })
  },

  goToSetting() {
    wx.navigateTo({ url: '/pages/setting/index' })
  },

  copyBaseUrl() {
    wx.setClipboardData({
      data: getBaseUrl(),
      success: () => wx.showToast({ title: '地址已复制', icon: 'success' })
    })
  },
})
