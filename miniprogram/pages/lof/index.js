const app = getApp()
const { callMarketSafe } = require('../../utils/cloudApi')
const favoriteManager = require('../../utils/favoriteManager')

Page({
  data: {
    currentTab: 'all',
    allList: [],
    currentList: [],
    filteredList: [],
    searchKeyword: '',
    showSearch: false,
    selectedLof: null,
    showLofModal: false,
    tabStats: {
      allCount: 0,
      premiumCount: 0,
      discountCount: 0,
      pausedCount: 0
    },
    marketSummary: {
      count: 0,
      premiumAvg: '--',
      topPremium: '--',
      positiveCount: 0,
      pausedCount: 0,
      arbitrageCount: 0,
      lowLiquidityCount: 0
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
    this._updateTabBar(2)
  },

  _updateTabBar(index) {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().checkDarkMode()
      this.getTabBar().setData({ selected: index })
    }
  },

  onPullDownRefresh() {
    this.loadData().then(() => {
      wx.stopPullDownRefresh()
    })
  },

  switchTab(e) {
    try {
      const tab = e.currentTarget.dataset.tab
      if (!tab) return
      const currentList = this._filterByTab(this.data.allList, tab)
      this.setData({
        currentTab: tab,
        currentList
      })
    } catch (err) {
      console.error('Switch tab failed:', err)
    }
  },

  _filterByTab(list, tab) {
    if (tab === 'all') return list
    if (tab === 'premium') return list.filter(i => i.premiumValue >= 5)
    if (tab === 'discount') return list.filter(i => i.premiumValue < 0)
    if (tab === 'paused') return list.filter(i => i.isPaused)
    return list
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
        console.error('数据加载失败')
        list = []
      }

      const sortedList = list.sort((a, b) => {
        const pa = a.premium || 0
        const pb = b.premium || 0
        return pb - pa
      })
      const formattedList = sortedList.map(item => this.formatLofItem(item))

      if (!summary) {
        const premiums = list.map(item => item.premium || 0)
        summary = {
          count: list.length,
          premiumAvg: (premiums.reduce((a, b) => a + b, 0) / premiums.length).toFixed(2),
          topPremium: Math.max(...premiums).toFixed(2),
          positiveCount: premiums.filter(p => p > 0).length,
          pausedCount: list.filter(item => item.limit_status === '暂停').length
        }
      } else {
        summary.pausedCount = list.filter(item => item.limit_status === '暂停').length
      }
      summary.arbitrageCount = formattedList.filter(i => i.canArbitrage).length
      summary.lowLiquidityCount = formattedList.filter(i => i.lowLiquidity).length

      const tabStats = {
        allCount: formattedList.length,
        premiumCount: formattedList.filter(i => i.premiumValue >= 5).length,
        discountCount: formattedList.filter(i => i.premiumValue < 0).length,
        pausedCount: formattedList.filter(i => i.isPaused).length
      }

      const now = new Date()
      const updateTime = now.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })

      this.setData({
        allList: formattedList,
        currentList: this._filterByTab(formattedList, this.data.currentTab),
        marketSummary: summary,
        tabStats,
        updateTime,
        loading: false
      })
    } catch (err) {
      console.error('Failed to load data:', err)
      this.setData({
        allList: [],
        currentList: [],
        marketSummary: {
          count: 0, premiumAvg: '--', topPremium: '--',
          positiveCount: 0, pausedCount: 0, arbitrageCount: 0, lowLiquidityCount: 0
        },
        updateTime: new Date().toLocaleString('zh-CN'),
        loading: false
      })
    }
  },

  _formatAmount(val) {
    if (!val || val <= 0) return '--'
    if (val >= 10000) return (val / 10000).toFixed(2) + '亿'
    if (val >= 1) return val.toFixed(1) + '万'
    return (val * 10000).toFixed(0) + '元'
  },

  _getAmountLevel(val) {
    if (!val || val <= 0) return ''
    if (val >= 1000) return 'safe'
    if (val >= 100) return 'warn'
    return 'danger'
  },

  formatLofItem(item) {
    const premium = item.premium || 0
    const price = item.price || 0
    const valuation = item.valuation || 0
    const consecutivePremium = item.consecutive_premium || 0
    const limitStatus = item.limit_status || '--'
    const name = item.name || '--'
    const code = item.code || '--'
    const changePct = item.change_pct || 0
    const amount = item.amount || 0
    const volume = item.volume || 0

    let exchange = ''
    if (item.exchange) {
      exchange = item.exchange === 'sh' ? '沪' : item.exchange === 'sz' ? '深' : item.exchange === 'bj' ? '京' : item.exchange
    } else if (code.startsWith('sh') || code.startsWith('5')) {
      exchange = '沪'
    } else if (code.startsWith('sz') || code.startsWith('1')) {
      exchange = '深'
    }
    const pureCode = code.replace(/^(sh|sz)/, '')

    const isFavorite = favoriteManager.isFavorite(pureCode, 'lof')

    const spread = valuation > 0 && price > 0
      ? ((price - valuation) / valuation * 100).toFixed(2) + '%'
      : '--'

    // 净溢价 = 溢价率 - 申购费率(0.15%), 暂停申购时无净溢价
    let netPremium = null
    if (limitStatus === '暂停') {
      netPremium = null
    } else if (limitStatus === '限100') {
      netPremium = premium - 0.15
    } else {
      netPremium = premium - 0.15
    }
    const netPremiumText = netPremium !== null ? (netPremium > 0 ? '+' : '') + netPremium.toFixed(2) + '%' : 'N/A'
    const netPremiumClass = netPremium !== null ? (netPremium > 3 ? 'high' : netPremium > 0 ? '' : 'negative') : ''

    // 可套利条件
    const canArbitrage = premium >= 3 && amount >= 100 && limitStatus !== '暂停'
    const lowLiquidity = amount > 0 && amount < 10
    const sustainedPremium = consecutivePremium >= 5

    const limitAmount = limitStatus === '限100' ? 100 : null

    return {
      name, code: pureCode, exchange,
      priceText: typeof price === 'number' ? price.toFixed(3) : '--',
      valuationText: typeof valuation === 'number' ? valuation.toFixed(4) : '--',
      spread, premiumText: typeof premium === 'number' ? premium.toFixed(2) + '%' : '--',
      premiumValue: premium, consecutivePremium, limitStatus, isPaused: limitStatus === '暂停',
      isHighlight: premium > 10, isHighPremium: premium > 5,
      changePctText: typeof changePct === 'number' ? (changePct > 0 ? '+' : '') + changePct.toFixed(2) + '%' : '--',
      isChangeUp: changePct > 0, isFavorite,
      // 成交额
      amountRaw: amount,
      amountText: this._formatAmount(amount),
      amountLevel: this._getAmountLevel(amount),
      volumeText: volume ? (volume >= 10000 ? (volume / 10000).toFixed(2) + '亿' : volume.toFixed(1) + '万') : '--',
      // 净溢价
      netPremium, netPremiumText, netPremiumClass,
      // 标记
      canArbitrage, lowLiquidity, sustainedPremium,
      limitAmount,
      // 弹窗数据
      detail: {
        name: name || '--', code: pureCode, exchange: exchange || '--',
        price: typeof price === 'number' ? price.toFixed(3) : '--',
        valuation: typeof valuation === 'number' ? valuation.toFixed(4) : '--',
        premium: typeof premium === 'number' ? premium.toFixed(2) + '%' : '--',
        spread, netPremium: netPremiumText, limitStatus,
        limitAmount: limitAmount ? (limitAmount >= 1000 ? (limitAmount / 10000).toFixed(2) + '万元' : limitAmount + '元') : '--',
        amountText: this._formatAmount(amount),
        volumeText: volume ? (volume >= 10000 ? (volume / 10000).toFixed(2) + '亿股' : volume.toFixed(1) + '万股') : '--',
        consecutivePremium: consecutivePremium + '天',
        isShenzhen: exchange === '深',
        advice: this._getAdvice(premium, amount, limitStatus, consecutivePremium)
      }
    }
  },

  _getAdvice(premium, amount, limitStatus, consecutivePremium) {
    if (limitStatus === '暂停') {
      return '申购暂停，无法套利。关注恢复申购后的溢价变化。'
    }
    if (premium >= 3 && amount >= 100) {
      let advice = '✅ 溢价' + premium.toFixed(2) + '%' + (consecutivePremium >= 5 ? '（已持续' + consecutivePremium + '天）' : '')
      advice += '，成交额充足，可考虑溢价套利。'
      if (amount < 1000) advice += '注意当日成交额' + this._formatAmount(amount) + '，盘中需监控流动性。'
      advice += '建议14:50后操作，申购费需一折券商(0.15%)。'
      if (limitStatus === '限100') advice += '单账户限' + this._formatAmount(100) + '，一拖六可放大。'
      return advice
    }
    if (premium > 0 && premium < 3) {
      return '溢价仅' + premium.toFixed(2) + '%' + (premium < 0.15 ? '，不足覆盖申购费(0.15%)' : '，空间有限') + '，建议观望。'
    }
    if (premium < 0) {
      const absP = Math.abs(premium)
      if (absP > 1) {
        return '折价' + absP.toFixed(2) + '%，折价套利需持有≥7天(赎回费0.5%)，注意净值波动风险。不建议新手操作。'
      }
      return '轻微折价，套利空间有限，建议观望。'
    }
    return '暂无明确套利信号。'
  },

  openLofDetail(e) {
    const { index } = e.currentTarget.dataset
    const list = this.data.currentList
    const item = list[index]
    if (!item) return
    this.setData({
      selectedLof: item.detail,
      showLofModal: true
    })
  },

  closeLofModal() {
    this.setData({ showLofModal: false, selectedLof: null })
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
    const favCodes = favoriteManager.getCodesByType('lof')
    const updateList = (list) => list.map(item => ({
      ...item,
      isFavorite: favCodes.has(item.code)
    }))
    const allList = updateList(this.data.allList)
    const currentList = updateList(this.data.currentList)
    const filteredList = this.data.showSearch
      ? currentList.filter(item =>
          item.name.toLowerCase().includes(this.data.searchKeyword.toLowerCase()) ||
          item.code.includes(this.data.searchKeyword)
        )
      : currentList
    this.setData({
      allList,
      currentList,
      filteredList
    })
  }
})
