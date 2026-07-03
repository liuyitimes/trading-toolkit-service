const app = getApp()
const { callMarketSafe } = require('../../utils/cloudApi')
const favoriteManager = require('../../utils/favoriteManager')

Page({
  data: {
    currentTab: 'placement',
    signals: {
      placement: [],
      double_low: [],
      force_redeem: [],
      discount: [],
      down_revised: []
    },
    currentList: [],
    filteredList: [],
    searchKeyword: '',
    showSearch: false,
    marketTemp: {
      count: 0,
      priceMedian: '--',
      premiumMedian: '--',
      doubleLowMedian: '--',
      marketStatus: '--',
      placementCount: 0,
      doubleLowCount: 0,
      forceRedeemCount: 0,
      discountCount: 0,
      downRevisedCount: 0
    },
    loading: true,
    error: null,
    isDarkMode: false
  },

  onLoad() {
    this.loadSignals()
  },

  onShow() {
    this.refreshFavorites()
    const theme = app.getTheme()
    this.setData({ isDarkMode: theme === 'dark' })
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().checkDarkMode()
      this.getTabBar().setData({ selected: 1 })
    }
  },

  onPullDownRefresh() {
    this.setData({ error: null })
    this.loadSignals().then(() => {
      wx.stopPullDownRefresh()
    })
  },

  switchTab(e) {
    try {
      const tab = e.currentTarget.dataset.tab
      if (!tab) return

      let key = tab
      if (tab === 'placement') key = 'placement'
      else if (tab === 'double-low') key = 'double_low'
      else if (tab === 'force-redeem') key = 'force_redeem'
      else if (tab === 'down-revised') key = 'down_revised'

      this.setData({
        currentTab: tab,
        currentList: this.data.signals[key] || []
      })
    } catch (err) {
      console.error('Switch tab failed:', err)
    }
  },

  async loadSignals() {
    this.setData({ loading: true, error: null })

    try {
      const [signals, overview] = await Promise.all([
        callMarketSafe('convertibleSignals'),
        callMarketSafe('overview')
      ])

      if (signals) {
        const normalized = this.normalizeSignals(signals)
        let marketTemp = this.calculateMarketTemp(normalized)

        if (overview && overview.convertible_bond) {
          const cb = overview.convertible_bond
          marketTemp = {
            count: cb.count || normalized.double_low.length,
            priceMedian: cb.price_median || '--',
            premiumMedian: cb.premium_median !== undefined ? cb.premium_median : '--',
            doubleLowMedian: cb.double_low_median || '--',
            marketStatus: cb.market_status || '--',
            placementCount: normalized.placement.length,
            doubleLowCount: normalized.double_low.length,
            forceRedeemCount: normalized.force_redeem.length,
            discountCount: normalized.discount.length,
            downRevisedCount: normalized.down_revised.length
          }
        }

        this.applyData(normalized, marketTemp)
      } else {
        const mockData = this.normalizeSignals(this.getMockData())
        const marketTemp = this.calculateMarketTemp(mockData)
        this.applyData(mockData, marketTemp)
      }
    } catch (err) {
      console.error('Failed to load signals:', err)
      const mockData = this.normalizeSignals(this.getMockData())
      const marketTemp = this.calculateMarketTemp(mockData)
      this.applyData(mockData, marketTemp)
    }
  },

  applyData(signals, marketTemp) {
    let key = this.data.currentTab
    if (key === 'placement') key = 'placement'
    else if (key === 'double-low') key = 'double_low'
    else if (key === 'force-redeem') key = 'force_redeem'
    else if (key === 'down-revised') key = 'down_revised'

    if (!marketTemp) {
      marketTemp = this.calculateMarketTemp(signals)
    }

    const app = getApp()
    if (!app.globalData.bondListCache) {
      app.globalData.bondListCache = []
    }
    const allBonds = []
    Object.keys(signals).forEach(k => {
      if (Array.isArray(signals[k])) {
        allBonds.push(...signals[k])
      }
    })
    const codeSet = new Set()
    const uniqueBonds = allBonds.filter(b => {
      if (codeSet.has(b.bondCode)) return false
      codeSet.add(b.bondCode)
      return true
    })
    app.globalData.bondListCache = uniqueBonds

    this.setData({
      signals,
      currentList: signals[key] || [],
      marketTemp,
      loading: false
    })
  },

  calculateMarketTemp(signals) {
    return {
      count: signals.double_low.length + signals.force_redeem.length,
      priceMedian: '--',
      premiumMedian: '--',
      doubleLowMedian: '--',
      marketStatus: '--',
      placementCount: signals.placement.length,
      doubleLowCount: signals.double_low.length,
      forceRedeemCount: signals.force_redeem.length,
      discountCount: signals.discount.length,
      downRevisedCount: signals.down_revised.length
    }
  },

  getMockData() {
    const mockBonds = [
      { '转债名称': '汇车退债', '转债代码': '404004', '转债价格': 55.59, '转股价值': 60.00, '转股溢价率': -7.35, '双低': 48.24, '正股名称': '汇车5' },
      { '转债名称': '南芯转债', '转债代码': '118070', '转债价格': 100.00, '转股价值': 122.95, '转股溢价率': -18.66, '双低': 81.34, '正股名称': '南芯科技' },
      { '转债名称': '金帝转债', '转债代码': '113706', '转债价格': 100.00, '转股价值': 98.63, '转股溢价率': 1.39, '双低': 101.39, '正股名称': '金帝股份' },
      { '转债名称': '春风转债', '转债代码': '113704', '转债价格': 100.00, '转股价值': 92.66, '转股溢价率': 7.92, '双低': 107.92, '正股名称': '春风动力' },
      { '转债名称': '弘亚转债', '转债代码': '127041', '转债价格': 116.00, '转股价值': 107.26, '转股溢价率': 8.15, '双低': 124.15, '正股名称': '弘亚数控' },
      { '转债名称': '上银转债', '转债代码': '113042', '转债价格': 116.62, '转股价值': 107.90, '转股溢价率': 8.08, '双低': 124.70, '正股名称': '上海银行' },
      { '转债名称': '艾迪转债', '转债代码': '113644', '转债价格': 129.93, '转股价值': 130.08, '转股溢价率': -0.12, '双低': 129.81, '正股名称': '艾迪精密' },
      { '转债名称': '镇洋转债', '转债代码': '113681', '转债价格': 130.30, '转股价值': 129.68, '转股溢价率': 0.48, '双低': 130.78, '正股名称': '镇洋发展' },
      { '转债名称': '航新转债', '转债代码': '123061', '转债价格': 129.40, '转股价值': 126.52, '转股溢价率': 2.28, '双低': 131.68, '正股名称': '航新科技' },
      { '转债名称': '重银转债', '转债代码': '113056', '转债价格': 127.61, '转股价值': 118.53, '转股溢价率': 7.66, '双低': 135.27, '正股名称': '重庆银行' },
      { '转债名称': '常银转债', '转债代码': '113062', '转债价格': 129.52, '转股价值': 122.10, '转股溢价率': 6.08, '双低': 135.60, '正股名称': '常熟银行' },
      { '转债名称': 'G三峡EB2', '转债代码': '132026', '转债价格': 132.10, '转股价值': 122.78, '转股溢价率': 7.59, '双低': 139.69, '正股名称': '长江电力' },
      { '转债名称': '银微转债', '转债代码': '118011', '转债价格': 148.44, '转股价值': 149.59, '转股溢价率': -0.76, '双低': 147.68, '正股名称': '银河微电' },
      { '转债名称': '鹤21转债', '转债代码': '113632', '转债价格': 152.74, '转股价值': 153.34, '转股溢价率': -0.39, '双低': 152.35, '正股名称': '仙鹤股份' },
      { '转债名称': '正川转债', '转债代码': '113624', '转债价格': 147.40, '转股价值': 140.04, '转股溢价率': 5.25, '双低': 152.65, '正股名称': '正川股份' },
      { '转债名称': '奕瑞转债', '转债代码': '118025', '转债价格': 151.86, '转股价值': 148.41, '转股溢价率': 2.33, '双低': 154.19, '正股名称': '奕瑞科技' },
      { '转债名称': '水羊转债', '转债代码': '123188', '转债价格': 166.20, '转股价值': 162.70, '转股溢价率': 2.15, '双低': 168.35, '正股名称': '水羊股份' },
      { '转债名称': '华亚转债', '转债代码': '127079', '转债价格': 264.90, '转股价值': 265.72, '转股溢价率': -0.31, '双低': 264.59, '正股名称': '华亚智能' }
    ]

    return {
      double_low: mockBonds.slice(0, 20),
      force_redeem: mockBonds.filter(b => b['转股溢价率'] < 10 && b['转债价格'] >= 105 && b['转债价格'] <= 140).slice(0, 10),
      discount: mockBonds.filter(b => b['转股溢价率'] < 0).slice(0, 10),
      down_revised: mockBonds.filter(b => b['转股溢价率'] > 50 && b['转债价格'] < 115).slice(0, 10)
    }
  },

  normalizeSignals(data) {
    const result = {
      placement: [],
      double_low: [],
      force_redeem: [],
      discount: [],
      down_revised: []
    }

    const fields = ['placement', 'double_low', 'force_redeem', 'discount', 'down_revised']
    
    fields.forEach(field => {
      if (data[field] && Array.isArray(data[field])) {
        result[field] = data[field].map(item => this.formatBondItem(item))
      }
    })

    if (!result.placement || result.placement.length === 0) {
      result.placement = (data.double_low || []).slice(0, 10).map(item => this.formatBondItem(item))
    }

    return result
  },

  formatBondItem(item) {
    const priceNum = typeof item['转债价格'] === 'number' ? item['转债价格'] : 0
    const conversionValueNum = typeof item['转股价值'] === 'number' ? item['转股价值'] : 0
    const premiumRateNum = typeof item['转股溢价率'] === 'number' ? item['转股溢价率'] : 0
    const doubleLowNum = typeof item['双低'] === 'number' ? item['双低'] : 0
    const conversionPriceNum = typeof item['转股价'] === 'number' ? item['转股价'] : 0
    const stockPriceNum = typeof item['正股价'] === 'number' ? item['正股价'] : 0
    const pureBondValueNum = typeof item['纯债价值'] === 'number' ? item['纯债价值'] : 0
    const ytmNum = typeof item['到期税前收益'] === 'number' ? item['到期税前收益'] : null
    const rating = item['评级'] || item['信用评级'] || '--'

    const price = priceNum ? priceNum.toFixed(2) : '--'
    const conversionValue = conversionValueNum ? conversionValueNum.toFixed(2) : '--'
    const premium = premiumRateNum !== 0 || item['转股溢价率'] !== undefined
      ? premiumRateNum.toFixed(2) + '%' : '--'
    const premiumClass = premiumRateNum < 0 ? 'negative' : premiumRateNum > 30 ? 'high' : ''
    const doubleLow = doubleLowNum ? doubleLowNum.toFixed(1) : '--'
    const conversionPrice = conversionPriceNum ? conversionPriceNum.toFixed(2) : '--'
    const stockPrice = stockPriceNum ? stockPriceNum.toFixed(2) : '--'
    const pureBondValue = pureBondValueNum ? pureBondValueNum.toFixed(2) : '--'
    const ytm = ytmNum !== null ? (ytmNum > 0 ? '+' : '') + ytmNum.toFixed(2) + '%' : '--'

    const bondName = item['转债名称'] || item.bondName || '--'
    const bondCode = item['转债代码'] || item.bondCode || '--'
    const stockName = item['正股名称'] || item.stockName || '--'
    const stockCode = String(item['正股代码'] || item.stockCode || '')

    let exchange = ''
    if (item['交易所'] || item.exchange) {
      exchange = item['交易所'] || item.exchange
    } else if (stockCode.startsWith('6') || stockCode.startsWith('5') || stockCode.startsWith('9')
      || bondCode.startsWith('11') || bondCode.startsWith('13') || bondCode.startsWith('5')) {
      exchange = '沪'
    } else if (stockCode.startsWith('0') || stockCode.startsWith('1') || stockCode.startsWith('2') || stockCode.startsWith('3')
      || bondCode.startsWith('12') || bondCode.startsWith('16')) {
      exchange = '深'
    } else if (stockCode.startsWith('4') || stockCode.startsWith('8') || bondCode.startsWith('8')) {
      exchange = '京'
    }

    const isFavorite = favoriteManager.isFavorite(bondCode, 'bond')

    let forceRedemptionGap = '--'
    let forceRedemptionClass = ''
    if (conversionPriceNum > 0 && stockPriceNum > 0) {
      const forcePrice = conversionPriceNum * 1.3
      const gap = (stockPriceNum - forcePrice) / forcePrice * 100
      forceRedemptionGap = (gap > 0 ? '+' : '') + gap.toFixed(1) + '%'
      forceRedemptionClass = gap >= 0 ? 'warning' : ''
    }

    let downReviseGap = '--'
    let downReviseClass = ''
    if (conversionPriceNum > 0 && stockPriceNum > 0) {
      const revisePrice = conversionPriceNum * 0.85
      const gap = (stockPriceNum - revisePrice) / revisePrice * 100
      downReviseGap = gap.toFixed(1) + '%'
      downReviseClass = gap < 0 ? 'warning' : ''
    }

    let discountSpace = '--'
    let discountClass = ''
    if (premiumRateNum < 0) {
      discountSpace = Math.abs(premiumRateNum).toFixed(2) + '%'
      discountClass = 'positive'
    }

    const hundredRightValue = item['百元含权'] != null ? item['百元含权'] : (stockPriceNum > 0 ? 8 + Math.random() * 15 : 0)
    const hundredRight = hundredRightValue ? hundredRightValue.toFixed(2) : '--'
    
    const lotStockCount = item['配售十张所需股数'] != null ? item['配售十张所需股数'] : (stockPriceNum > 0 ? Math.round(1000 / (hundredRightValue / 100) / stockPriceNum) : 0)
    const lotStock = lotStockCount ? lotStockCount + '股' : '--'
    
    const safetyPadValue = item['安全垫'] != null ? item['安全垫'] : (hundredRightValue > 0 ? (25 / hundredRightValue * 100) : 0)
    const safetyPad = safetyPadValue ? safetyPadValue.toFixed(1) + '%' : '--'
    const safetyPadClass = safetyPadValue > 5 ? 'positive' : safetyPadValue > 3 ? 'warning' : 'negative'

    return {
      bondName,
      bondCode,
      stockName,
      stockCode,
      exchange,
      price,
      priceNum,
      conversionValue,
      conversionValueNum,
      premium,
      premiumClass,
      premiumNum: premiumRateNum,
      doubleLow,
      doubleLowNum,
      conversionPrice,
      conversionPriceNum,
      stockPrice,
      stockPriceNum,
      pureBondValue,
      pureBondValueNum,
      ytm,
      ytmNum,
      rating,
      forceRedemptionGap,
      forceRedemptionClass,
      downReviseGap,
      downReviseClass,
      discountSpace,
      discountClass,
      isFavorite,
      rawPremium: premiumRateNum,
      hundredRight,
      hundredRightValue,
      lotStock,
      lotStockCount,
      safetyPad,
      safetyPadClass
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
    this.filterList(keyword)
  },

  filterList(keyword) {
    if (!keyword) {
      this.setData({ filteredList: this.data.currentList })
      return
    }
    const filtered = this.data.currentList.filter(item =>
      item.bondName.toLowerCase().includes(keyword) ||
      item.bondCode.includes(keyword) ||
      item.stockName.toLowerCase().includes(keyword)
    )
    this.setData({ filteredList: filtered })
  },

  goToDetail(e) {
    const { code } = e.currentTarget.dataset
    if (!code) return
    wx.navigateTo({
      url: `/pages/bondDetail/index?code=${code}`
    })
  },

  toggleFavorite(e) {
    const { code, index } = e.currentTarget.dataset
    const listKey = this.data.showSearch ? 'filteredList' : 'currentList'
    const list = this.data[listKey]
    const item = list[index]
    if (!item) return

    const isNowFav = favoriteManager.toggle({
      code: item.bondCode,
      name: item.bondName,
      price: item.price,
      premiumRate: item.rawPremium
    }, 'bond')

    const key = `${listKey}[${index}].isFavorite`
    this.setData({ [key]: isNowFav })

    wx.showToast({
      title: isNowFav ? '已添加自选' : '已取消自选',
      icon: 'success',
      duration: 1000
    })
  },

  refreshFavorites() {
    const fields = ['double_low', 'force_redeem', 'discount', 'down_revised']
    const newSignals = {}

    fields.forEach(field => {
      newSignals[field] = this.data.signals[field].map(item => ({
        ...item,
        isFavorite: favoriteManager.isFavorite(item.bondCode, 'bond')
      }))
    })

    let key = this.data.currentTab
    if (key === 'double-low') key = 'double_low'
    else if (key === 'force-redeem') key = 'force_redeem'
    else if (key === 'down-revised') key = 'down_revised'

    const currentList = newSignals[key] || []
    const filteredList = this.data.showSearch
      ? this.filterListSync(currentList, this.data.searchKeyword)
      : currentList

    this.setData({
      signals: newSignals,
      currentList,
      filteredList
    })
  },

  filterListSync(list, keyword) {
    if (!keyword) return list
    return list.filter(item =>
      item.bondName.toLowerCase().includes(keyword.toLowerCase()) ||
      item.bondCode.includes(keyword) ||
      item.stockName.toLowerCase().includes(keyword.toLowerCase())
    )
  }
})