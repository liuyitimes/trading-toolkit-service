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
      { 'bond_name': '汇车退债', 'bond_code': '404004', 'price': 55.59, 'conversion_value': 60.00, 'premium_rate': -7.35, 'double_low': 48.24, 'stock_name': '汇车5' },
      { 'bond_name': '南芯转债', 'bond_code': '118070', 'price': 100.00, 'conversion_value': 122.95, 'premium_rate': -18.66, 'double_low': 81.34, 'stock_name': '南芯科技' },
      { 'bond_name': '金帝转债', 'bond_code': '113706', 'price': 100.00, 'conversion_value': 98.63, 'premium_rate': 1.39, 'double_low': 101.39, 'stock_name': '金帝股份' },
      { 'bond_name': '春风转债', 'bond_code': '113704', 'price': 100.00, 'conversion_value': 92.66, 'premium_rate': 7.92, 'double_low': 107.92, 'stock_name': '春风动力' },
      { 'bond_name': '弘亚转债', 'bond_code': '127041', 'price': 116.00, 'conversion_value': 107.26, 'premium_rate': 8.15, 'double_low': 124.15, 'stock_name': '弘亚数控' },
      { 'bond_name': '上银转债', 'bond_code': '113042', 'price': 116.62, 'conversion_value': 107.90, 'premium_rate': 8.08, 'double_low': 124.70, 'stock_name': '上海银行' },
      { 'bond_name': '艾迪转债', 'bond_code': '113644', 'price': 129.93, 'conversion_value': 130.08, 'premium_rate': -0.12, 'double_low': 129.81, 'stock_name': '艾迪精密' },
      { 'bond_name': '镇洋转债', 'bond_code': '113681', 'price': 130.30, 'conversion_value': 129.68, 'premium_rate': 0.48, 'double_low': 130.78, 'stock_name': '镇洋发展' },
      { 'bond_name': '航新转债', 'bond_code': '123061', 'price': 129.40, 'conversion_value': 126.52, 'premium_rate': 2.28, 'double_low': 131.68, 'stock_name': '航新科技' },
      { 'bond_name': '重银转债', 'bond_code': '113056', 'price': 127.61, 'conversion_value': 118.53, 'premium_rate': 7.66, 'double_low': 135.27, 'stock_name': '重庆银行' },
      { 'bond_name': '常银转债', 'bond_code': '113062', 'price': 129.52, 'conversion_value': 122.10, 'premium_rate': 6.08, 'double_low': 135.60, 'stock_name': '常熟银行' },
      { 'bond_name': 'G三峡EB2', 'bond_code': '132026', 'price': 132.10, 'conversion_value': 122.78, 'premium_rate': 7.59, 'double_low': 139.69, 'stock_name': '长江电力' },
      { 'bond_name': '银微转债', 'bond_code': '118011', 'price': 148.44, 'conversion_value': 149.59, 'premium_rate': -0.76, 'double_low': 147.68, 'stock_name': '银河微电' },
      { 'bond_name': '鹤21转债', 'bond_code': '113632', 'price': 152.74, 'conversion_value': 153.34, 'premium_rate': -0.39, 'double_low': 152.35, 'stock_name': '仙鹤股份' },
      { 'bond_name': '正川转债', 'bond_code': '113624', 'price': 147.40, 'conversion_value': 140.04, 'premium_rate': 5.25, 'double_low': 152.65, 'stock_name': '正川股份' },
      { 'bond_name': '奕瑞转债', 'bond_code': '118025', 'price': 151.86, 'conversion_value': 148.41, 'premium_rate': 2.33, 'double_low': 154.19, 'stock_name': '奕瑞科技' },
      { 'bond_name': '水羊转债', 'bond_code': '123188', 'price': 166.20, 'conversion_value': 162.70, 'premium_rate': 2.15, 'double_low': 168.35, 'stock_name': '水羊股份' },
      { 'bond_name': '华亚转债', 'bond_code': '127079', 'price': 264.90, 'conversion_value': 265.72, 'premium_rate': -0.31, 'double_low': 264.59, 'stock_name': '华亚智能' }
    ]

    return {
      double_low: mockBonds.slice(0, 20),
      force_redeem: mockBonds.filter(b => b.premium_rate < 10 && b.price >= 105 && b.price <= 140).slice(0, 10),
      discount: mockBonds.filter(b => b.premium_rate < 0).slice(0, 10),
      down_revised: mockBonds.filter(b => b.premium_rate > 50 && b.price < 115).slice(0, 10)
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
    const priceNum = typeof item.price === 'number' ? item.price : 0
    const conversionValueNum = typeof item.conversion_value === 'number' ? item.conversion_value : 0
    const premiumRateNum = typeof item.premium_rate === 'number' ? item.premium_rate : 0
    const doubleLowNum = typeof item.double_low === 'number' ? item.double_low : 0
    const conversionPriceNum = typeof item.conversion_price === 'number' ? item.conversion_price : 0
    const stockPriceNum = typeof item.stock_price === 'number' ? item.stock_price : 0
    const pureBondValueNum = typeof item.pure_bond_value === 'number' ? item.pure_bond_value : 0
    const ytmNum = typeof item.ytm === 'number' ? item.ytm : null
    const rating = item.rating || '--'

    const price = priceNum ? priceNum.toFixed(2) : '--'
    const conversionValue = conversionValueNum ? conversionValueNum.toFixed(2) : '--'
    const premium = premiumRateNum !== 0 || item.premium_rate !== undefined
      ? premiumRateNum.toFixed(2) + '%' : '--'
    const premiumClass = premiumRateNum < 0 ? 'negative' : premiumRateNum > 30 ? 'high' : ''
    const doubleLow = doubleLowNum ? doubleLowNum.toFixed(1) : '--'
    const conversionPrice = conversionPriceNum ? conversionPriceNum.toFixed(2) : '--'
    const stockPrice = stockPriceNum ? stockPriceNum.toFixed(2) : '--'
    const pureBondValue = pureBondValueNum ? pureBondValueNum.toFixed(2) : '--'
    const ytm = ytmNum !== null ? (ytmNum > 0 ? '+' : '') + ytmNum.toFixed(2) + '%' : '--'

    const bondName = item.bond_name || '--'
    const bondCode = item.bond_code || '--'
    const stockName = item.stock_name || '--'
    const stockCode = String(item.stock_code || '')

    let exchange = ''
    if (item.exchange) {
      exchange = item.exchange === 'sh' ? '沪' : item.exchange === 'sz' ? '深' : item.exchange === 'bj' ? '京' : item.exchange
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

    const hundredRightValue = item.hundred_right || null
    const hundredRight = hundredRightValue ? hundredRightValue.toFixed(2) : '--'
    
    const lotStockCount = item.lot_stock_count || null
    const lotStock = lotStockCount ? lotStockCount + '股' : '--'
    
    const safetyPadValue = item.safety_pad || null
    const safetyPad = safetyPadValue ? safetyPadValue.toFixed(1) + '%' : '--'
    const safetyPadClass = safetyPadValue == null ? '' : (safetyPadValue > 5 ? 'positive' : safetyPadValue > 3 ? 'warning' : 'negative')

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