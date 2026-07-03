const app = getApp()
const { callMarketSafe } = require('../../utils/cloudApi')
const favoriteManager = require('../../utils/favoriteManager')

Page({
  data: {
    currentList: [],
    filteredList: [],
    searchKeyword: '',
    showSearch: false,
    marketSummary: {
      count: 0,
      premiumAvg: '--',
      topPremium: '--',
      positiveCount: 0,
      pausedCount: 0
    },
    loading: true,
    updateTime: ''
  },

  onLoad() {
    this.loadData()
  },

  onShow() {
    this.refreshFavorites()
    const theme = app.getTheme()
    this.setData({ isDarkMode: theme === 'dark' })
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().checkDarkMode()
      this.getTabBar().setData({ selected: 2 })
    }
  },

  onPullDownRefresh() {
    this.loadData().then(() => {
      wx.stopPullDownRefresh()
    })
  },

  async loadData() {
    this.setData({ loading: true })

    try {
      const [lofList, overview] = await Promise.all([
        callMarketSafe('lofList'),
        callMarketSafe('overview')
      ])

      let list = lofList || []
      let summary = null

      if (overview && overview.lof_fund) {
        summary = overview.lof_fund
      }

      if (!list.length) {
        list = this.getMockData()
      }

      const sortedList = list.sort((a, b) => {
        const pa = a.premium || a['溢价率'] || 0
        const pb = b.premium || b['溢价率'] || 0
        return pb - pa
      })
      const formattedList = sortedList.map(item => this.formatLofItem(item))

      if (!summary) {
        const premiums = list.map(item => item.premium || item['溢价率'] || 0)
        summary = {
          count: list.length,
          premiumAvg: (premiums.reduce((a, b) => a + b, 0) / premiums.length).toFixed(2),
          topPremium: Math.max(...premiums).toFixed(2),
          positiveCount: premiums.filter(p => p > 0).length,
          pausedCount: list.filter(item => (item.limit_status || item['申购状态']) === '暂停').length
        }
      } else {
        summary.pausedCount = list.filter(item => (item.limit_status || item['申购状态']) === '暂停').length
      }

      const now = new Date()
      const updateTime = now.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })

      this.setData({
        currentList: formattedList,
        marketSummary: summary,
        updateTime,
        loading: false
      })
    } catch (err) {
      console.error('Failed to load data:', err)
      const mockList = this.getMockData()
      const premiums = mockList.map(item => item.premium || 0)
      const formattedList = mockList.sort((a, b) => b.premium - a.premium).map(item => this.formatLofItem(item))
      this.setData({
        currentList: formattedList,
        marketSummary: {
          count: mockList.length,
          premiumAvg: (premiums.reduce((a, b) => a + b, 0) / premiums.length).toFixed(2),
          topPremium: Math.max(...premiums).toFixed(2),
          positiveCount: premiums.filter(p => p > 0).length,
          pausedCount: mockList.filter(item => item.limit_status === '暂停').length
        },
        updateTime: new Date().toLocaleString('zh-CN'),
        loading: false
      })
    }
  },

  getMockData() {
    return [
      { code: 'sh501015', name: '财通升级混合LOF', price: 4.714, valuation: 4.0755, change_pct: 2.35, premium: 15.67, consecutive_premium: 3, limit_status: '不限' },
      { code: 'sh501026', name: '财通福享混合LOF', price: 3.502, valuation: 3.0992, change_pct: 1.89, premium: 13.00, consecutive_premium: 3, limit_status: '不限' },
      { code: 'sh501085', name: '财通科创LOF', price: 4.548, valuation: 4.0829, change_pct: 3.21, premium: 11.39, consecutive_premium: 3, limit_status: '不限' },
      { code: 'sz161128', name: '标普信息科技LOF', price: 7.059, valuation: 6.598, change_pct: 0.45, premium: 6.99, consecutive_premium: 19, limit_status: '暂停' },
      { code: 'sh501096', name: '国联安科创LOF', price: 2.169, valuation: 2.0585, change_pct: 1.56, premium: 5.37, consecutive_premium: 1, limit_status: '不限' },
      { code: 'sh501079', name: '科创大成LOF', price: 6.376, valuation: 6.0716, change_pct: 2.87, premium: 5.01, consecutive_premium: 3, limit_status: '不限' },
      { code: 'sz161130', name: '纳斯达克100LOF', price: 4.79, valuation: 4.564, change_pct: 0.32, premium: 4.95, consecutive_premium: 19, limit_status: '暂停' },
      { code: 'sz161125', name: '标普500LOF', price: 3.176, valuation: 3.0777, change_pct: 0.18, premium: 3.19, consecutive_premium: 19, limit_status: '暂停' },
      { code: 'sz167301', name: '保险主题LOF', price: 0.983, valuation: 0.9662, change_pct: 0.65, premium: 1.74, consecutive_premium: 3, limit_status: '不限' },
      { code: 'sh501312', name: '海外科技LOF', price: 2.39, valuation: 2.3495, change_pct: 0.88, premium: 1.72, consecutive_premium: 3, limit_status: '限100' }
    ]
  },

  formatLofItem(item) {
    const premium = item.premium || item['溢价率'] || 0
    const price = item.price || item['最新价'] || 0
    const valuation = item.valuation || item['估值'] || 0
    const consecutivePremium = item.consecutive_premium || item['连续溢价'] || 0
    const limitStatus = item.limit_status || item['申购状态'] || '--'
    const name = item.name || item['名称'] || '--'
    const code = item.code || item['代码'] || '--'
    const changePct = item.change_pct || item['涨跌幅'] || 0

    let exchange = ''
    if (item['交易所']) {
      exchange = item['交易所']
    } else if (code.startsWith('sh') || code.startsWith('5')) {
      exchange = '沪'
    } else if (code.startsWith('sz') || code.startsWith('1')) {
      exchange = '深'
    }
    const pureCode = code.replace(/^(sh|sz)/, '')

    const isFavorite = favoriteManager.isFavorite(pureCode, 'lof')

    return {
      name,
      code: pureCode,
      exchange,
      priceText: typeof price === 'number' ? price.toFixed(3) : '--',
      valuationText: typeof valuation === 'number' ? valuation.toFixed(4) : '--',
      premiumText: typeof premium === 'number' ? premium.toFixed(2) + '%' : '--',
      premiumValue: premium,
      consecutivePremium,
      limitStatus,
      isHighlight: premium > 10,
      isHighPremium: premium > 5,
      isPaused: limitStatus === '暂停',
      changePctText: typeof changePct === 'number' ? (changePct > 0 ? '+' : '') + changePct.toFixed(2) + '%' : '--',
      isChangeUp: changePct > 0,
      isFavorite
    }
  },

  toggleSearch() {
    this.setData({
      showSearch: !this.data.showSearch,
      searchKeyword: '',
      filteredList: this.data.currentList
    })
  },

  onSearchInput(e) {
    const keyword = e.detail.value.trim().toLowerCase()
    this.setData({ searchKeyword: keyword })
    if (!keyword) {
      this.setData({ filteredList: this.data.currentList })
      return
    }
    const filtered = this.data.currentList.filter(item =>
      item.name.toLowerCase().includes(keyword) ||
      item.code.includes(keyword)
    )
    this.setData({ filteredList: filtered })
  },

  toggleFavorite(e) {
    const { code, index } = e.currentTarget.dataset
    const listKey = this.data.showSearch ? 'filteredList' : 'currentList'
    const list = this.data[listKey]
    const item = list[index]
    if (!item) return

    const isNowFav = favoriteManager.toggle({
      code: item.code,
      name: item.name,
      price: item.priceText,
      premiumRate: item.premiumValue
    }, 'lof')

    const key = `${listKey}[${index}].isFavorite`
    this.setData({ [key]: isNowFav })

    wx.showToast({
      title: isNowFav ? '已添加自选' : '已取消自选',
      icon: 'success',
      duration: 1000
    })
  },

  refreshFavorites() {
    const updatedList = this.data.currentList.map(item => ({
      ...item,
      isFavorite: favoriteManager.isFavorite(item.code, 'lof')
    }))
    const filteredList = this.data.showSearch
      ? updatedList.filter(item =>
          item.name.toLowerCase().includes(this.data.searchKeyword.toLowerCase()) ||
          item.code.includes(this.data.searchKeyword)
        )
      : updatedList
    this.setData({
      currentList: updatedList,
      filteredList
    })
  }
})