const app = getApp()
const { callMarketSafe } = require('../../utils/cloudApi')
const favoriteManager = require('../../utils/favoriteManager')

Page({
  data: {
    currentTab: 'placement',
    placementSubTab: 'all',
    placementSortBy: '',
    placementSortAsc: false,
    signals: {
      placement: [],
      double_low: [],
      force_redeem: [],
      discount: [],
      down_revised: []
    },
    pendingList: [],
    currentList: [],
    filteredList: [],
    searchKeyword: '',
    showSearch: false,
    selectedPending: null,
    showPendingModal: false,
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
    placementTabStats: {
      allCount: 0,
      subscribingCount: 0,
      pendingListCount: 0,
      approvedCount: 0
    },
    loading: true,
    error: null,
    isDarkMode: false
  },

  onLoad() {
    console.time('convertible-load')
    this.loadSignals()
  },

  onShow() {
    console.time('convertible-onShow')
    this.refreshFavorites()
    const theme = app.getTheme()
    this.setData({ isDarkMode: theme === 'dark' })
    this._updateTabBar(1)
    console.timeEnd('convertible-onShow')
  },

  _updateTabBar(index) {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().checkDarkMode()
      this.getTabBar().setData({ selected: index })
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

      if (tab === 'placement') {
        this.setData({
          currentTab: tab,
          placementSubTab: 'all',
          placementSortBy: 'composite',
          placementSortAsc: false,
          currentList: this._sortPendingBy(this.pendingList || [], 'composite', false)
        })
        return
      } else if (tab === 'placement-sub') {
        const sub = e.currentTarget.dataset.sub
        const filtered = this._filterPendingBySub(this.pendingList, sub)
        const sorted = this._sortPendingBy(filtered, this.data.placementSortBy, this.data.placementSortAsc)
        this.setData({
          placementSubTab: sub,
          currentList: sorted
        })
        return
      } else if (tab === 'placement-sort') {
        const field = e.currentTarget.dataset.field
        const asc = this.data.placementSortBy === field ? !this.data.placementSortAsc : false
        const filtered = this._filterPendingBySub(this.pendingList, this.data.placementSubTab)
        const sorted = this._sortPendingBy(filtered, field, asc)
        this.setData({
          placementSortBy: field,
          placementSortAsc: asc,
          currentList: sorted
        })
        return
      }

      let key = tab
      if (tab === 'double-low') key = 'double_low'
      else if (tab === 'force-redeem') key = 'force_redeem'
      else if (tab === 'down-revised') key = 'down_revised'

      this.setData({
        currentTab: tab,
        currentList: (this.data.signals[key] || []).slice(0, 15)
      })
    } catch (err) {
      console.error('Switch tab failed:', err)
    }
  },

  _filterPendingBySub(list, sub) {
    if (sub === 'all') return list
    if (sub === 'subscribing') return list.filter(i => i._status === '申购中')
    if (sub === 'pending') return list.filter(i => i._status === '待上市')
    if (sub === 'approved') return list.filter(i => i._status === '同意注册' || i._status === '上市委通过')
    return list
  },

  _sortPendingBy(list, field, asc) {
    if (!field) return list
    const sorted = [...list].sort((a, b) => {
      let va = 0, vb = 0
      if (field === 'cashRatio') { va = a._cashRatioRaw || 0; vb = b._cashRatioRaw || 0 }
      else if (field === 'safetyPad') { va = a._safetyPadRaw || 0; vb = b._safetyPadRaw || 0 }
      else if (field === 'issueSize') { va = a._issueSizeRaw || 0; vb = b._issueSizeRaw || 0 }
      else if (field === 'sharesFor10') { va = a._sharesFor10Raw || 999999; vb = b._sharesFor10Raw || 999999 }
      else if (field === 'stockChange') { va = a._stockChangeRaw || 0; vb = b._stockChangeRaw || 0 }
      else if (field === 'composite') { va = a._compositeRankRaw || 0; vb = b._compositeRankRaw || 0 }
      return asc ? va - vb : vb - va
    })
    return sorted
  },

  _sortByBest(list, tabKey) {
    if (!list || list.length <= 1) return list || []
    const sorted = [...list].sort((a, b) => {
      if (tabKey === 'double_low') {
        return (a.doubleLowNum || 9999) - (b.doubleLowNum || 9999)
      }
      if (tabKey === 'force_redeem') {
        return Math.abs(a._forcePriceGap || 9999) - Math.abs(b._forcePriceGap || 9999)
      }
      if (tabKey === 'discount') {
        return (a.premiumNum || 999) - (b.premiumNum || 999)
      }
      if (tabKey === 'down_revised') {
        return Math.abs(a._revisePriceGap || 9999) - Math.abs(b._revisePriceGap || 9999)
      }
      return 0
    })
    return sorted
  },

  async loadSignals() {
    this.setData({ loading: true, error: null })
    console.time('convertible-fetch')

    try {
      const [signals, overview, pendingData] = await Promise.all([
        callMarketSafe('convertibleSignals'),
        callMarketSafe('overview'),
        callMarketSafe('convertiblePending')
      ])

      console.timeEnd('convertible-fetch')

      // 格式化待发/配售列表
      const pendingList = Array.isArray(pendingData) ? pendingData.map(item => this.formatPendingItem(item)) : []
      this.pendingList = pendingList

      // Tab分类计数
      const placementTabStats = {
        allCount: pendingList.length,
        subscribingCount: pendingList.filter(i => i._status === '申购中').length,
        pendingListCount: pendingList.filter(i => i._status === '待上市').length,
        approvedCount: pendingList.filter(i => i._status === '同意注册' || i._status === '上市委通过').length
      }

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
            placementCount: pendingList.length,
            doubleLowCount: normalized.double_low.length,
            forceRedeemCount: normalized.force_redeem.length,
            discountCount: normalized.discount.length,
            downRevisedCount: normalized.down_revised.length
          }
        }

        this.applyData(normalized, marketTemp, pendingList, placementTabStats)
      } else {
        console.error('数据加载失败')
        this.setData({ loading: false, pendingList })
        return
      }
    } catch (err) {
      console.error('Failed to load signals:', err)
      this.setData({ loading: false })
    }
  },

  applyData(signals, marketTemp, pendingList, placementTabStats) {
    let key = this.data.currentTab
    let currentList = []
    if (key === 'placement') {
      currentList = this._sortPendingBy(pendingList || [], 'composite', false)
    } else {
      if (key === 'double-low') key = 'double_low'
      else if (key === 'force-redeem') key = 'force_redeem'
      else if (key === 'down-revised') key = 'down_revised'
      currentList = (signals[key] || []).slice(0, 15)
    }

    if (!marketTemp) {
      marketTemp = this.calculateMarketTemp(signals)
    }

    // 若调用方未传入 placementTabStats，则按 pendingList 重新计算，避免 ReferenceError
    if (!placementTabStats) {
      const list = pendingList || []
      placementTabStats = {
        allCount: list.length,
        subscribingCount: list.filter(i => i._status === '申购中').length,
        pendingListCount: list.filter(i => i._status === '待上市').length,
        approvedCount: list.filter(i => i._status === '同意注册' || i._status === '上市委通过').length
      }
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
      pendingList: pendingList || [],
      placementTabStats,
      currentList,
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

  normalizeSignals(data) {
    const result = {
      placement: [],
      double_low: [],
      force_redeem: [],
      discount: [],
      down_revised: []
    }

    // 批量预计算收藏状态
    const allItems = []
    const fields = ['placement', 'double_low', 'force_redeem', 'discount', 'down_revised']
    fields.forEach(field => {
      if (data[field] && Array.isArray(data[field])) {
        data[field].forEach(item => allItems.push({ code: item.bond_code || item.bondCode, type: 'bond' }))
      }
    })
    const favSet = favoriteManager.batchIsFavorite(allItems)

    fields.forEach(field => {
      if (data[field] && Array.isArray(data[field])) {
        result[field] = data[field].map(item => this.formatBondItem(item, favSet))
        result[field] = this._sortByBest(result[field], field)
      }
    })

    if (!result.placement || result.placement.length === 0) {
      result.placement = (data.double_low || []).slice(0, 10).map(item => this.formatBondItem(item))
    }

    return result
  },

  formatBondItem(item, favSet) {
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

    const isFavorite = favSet ? favSet.has(bondCode + ':bond') : favoriteManager.isFavorite(bondCode, 'bond')

    let forceRedemptionGap = '--'
    let forceRedemptionClass = ''
    let _forcePriceGap = 9999
    if (conversionPriceNum > 0 && stockPriceNum > 0) {
      const forcePrice = conversionPriceNum * 1.3
      const gap = (stockPriceNum - forcePrice) / forcePrice * 100
      _forcePriceGap = gap
      forceRedemptionGap = (gap > 0 ? '+' : '') + gap.toFixed(1) + '%'
      forceRedemptionClass = gap >= 0 ? 'warning' : ''
    }

    let downReviseGap = '--'
    let downReviseClass = ''
    let _revisePriceGap = 9999
    if (conversionPriceNum > 0 && stockPriceNum > 0) {
      const revisePrice = conversionPriceNum * 0.85
      const gap = (stockPriceNum - revisePrice) / revisePrice * 100
      _revisePriceGap = gap
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
      _forcePriceGap,
      downReviseGap,
      downReviseClass,
      _revisePriceGap,
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

  _computeSafetyPad(perShareAlloc, stockPriceVal, sharesFor10Val, premiumRate) {
    const safeSharesFor10 = sharesFor10Val || 0
    const safePrice = stockPriceVal || 0
    if (safeSharesFor10 <= 0 || safePrice <= 0) return { value: 0, profit: 0 }
    const expectedProfit = 1000 * (premiumRate || 0.2)
    return {
      value: expectedProfit / (safeSharesFor10 * safePrice) * 100,
      profit: expectedProfit
    }
  },

  formatPendingItem(item) {
    const stockName = item.stock_name || '--'
    const stockCode = item.stock_code || '--'
    const bondCode = item.bond_code || ''
    const bondName = item.bond_name || ''
    const progress = item.progress || item.status || '--'
    const issueSize = item.issue_size || 0
    const rating = item.rating || ''
    const shareholderRatio = item.shareholder_ratio || 0
    const stockPrice = item.stock_price || 0
    const stockChange = item.stock_change || 0
    const conversionPrice = item.conversion_price || 0
    const pb = item.pb || 0
    const perShare = item.per_share_allocation || 0
    const sharesFor10 = item.shares_for_10_lots || 0
    const regDate = item.registration_date || ''
    const status = item.status || '--'
    const onlineIssueSize = item.online_issue_size || 0
    const winRate = item.win_rate || 0

    // 百元含权：优先后端透传的 cb_amount，兜底自算
    const cashRatio = item.stock_cash_ratio || (perShare && stockPrice ? Math.round(perShare / stockPrice * 10000) / 100 : 0)

    // 后端字段
    const riskLevel = item.risk_level || 'mid'
    const recordPrice = item.record_price || 0
    const ma20Price = item.ma20_price || 0

    // 安全垫：优先用后端补算的 safety_pad，兜底自算
    const _safetyPadValue = item.safety_pad > 0
      ? item.safety_pad
      : this._computeSafetyPad(perShare, stockPrice, sharesFor10, 0.2).value
    const expectedProfit = item.expected_profit > 0
      ? item.expected_profit
      : this._computeSafetyPad(perShare, stockPrice, sharesFor10, 0.2).profit

    // 正股趋势（相对20日均价偏离）
    const stockTrend = ma20Price > 0 ? Math.round((stockPrice - ma20Price) / ma20Price * 10000) / 100 : 0

    let exchange = ''
    if (stockCode.startsWith('6') || stockCode.startsWith('5') || stockCode.startsWith('9')) {
      exchange = '沪'
    } else if (stockCode.startsWith('0') || stockCode.startsWith('1') || stockCode.startsWith('2') || stockCode.startsWith('3')) {
      exchange = '深'
    } else if (stockCode.startsWith('4') || stockCode.startsWith('8')) {
      exchange = '京'
    }

    const today = new Date().toISOString().slice(0, 10)
    let regBadge = ''
    let regBadgeClass = ''
    if (regDate) {
      if (regDate === today) { regBadge = '今日登记'; regBadgeClass = 'hot' }
      else if (regDate > today) {
        const diff = Math.ceil((new Date(regDate) - new Date()) / 86400000)
        if (diff === 1) { regBadge = '明日登记'; regBadgeClass = 'warm' }
        else if (diff <= 3) { regBadge = diff + '天后登记'; regBadgeClass = 'warm' }
      }
    }

    // 一手党标记（沪市+配10张市值<10000元）
    const oneHandParty = exchange === '沪' && sharesFor10 > 0 && stockPrice > 0
      && (sharesFor10 * stockPrice) < 10000

    // 一手资金 + 一手党最低手数
    const _costFor10LotsRaw = sharesFor10 > 0 && stockPrice > 0 ? sharesFor10 * stockPrice : 0
    const costFor10Lots = _costFor10LotsRaw > 0 ? Math.round(_costFor10LotsRaw) + '元' : '--'
    const _oneHandMinShares = exchange === '沪' && sharesFor10 > 0 && stockPrice > 0 ? Math.ceil(sharesFor10 * 0.6) : 0
    const oneHandMinCost = _oneHandMinShares > 0 ? Math.round(_oneHandMinShares * stockPrice) + '元' : ''

    // 风险等级标签颜色
    const riskLabel = riskLevel === 'high' ? '高风险' : riskLevel === 'low' ? '低风险' : '中风险'
    const riskClass = riskLevel

    // 综合排序分（百元含权50% + 安全垫30% + 发行规模20%，不展示）
    const _compositeRankRaw = Math.round(
      Math.min(cashRatio / 30, 1) * 50 +
      Math.min(_safetyPadValue / 10, 1) * 30 +
      Math.max(0, Math.min((10 - issueSize) / 8, 1)) * 20
    )

    // 发行时间轴
    const ALL_STAGES = ['董事会预案', '股东大会批准', '交易所受理', '上市委通过', '同意注册', '申购中', '待上市']
    let currentStageIndex = 0
    if (status && status !== '--') {
      const idx = ALL_STAGES.indexOf(status)
      if (idx >= 0) currentStageIndex = idx
    }
    const stageList = ALL_STAGES.map((name, i) => ({
      name: name,
      status: i < currentStageIndex ? 'done' : i === currentStageIndex ? 'current' : 'pending'
    }))

    // 板块检测（关键词匹配正股名称）
    const SECTOR_KEYWORDS = [
      { sector: 'AI/人工智能', keywords: ['智能', '科技', '信息', '数据', '软件', 'AI', '数字'], hot: true },
      { sector: '新能源', keywords: ['新能源', '光伏', '风电', '电池', '锂电'], hot: true },
      { sector: '半导体/芯片', keywords: ['半导', '芯片', '微电', '电子'], hot: true },
      { sector: '医药生物', keywords: ['医药', '生物', '医疗', '药'], hot: true },
      { sector: '低空经济', keywords: ['低空', '无人机', '航空'], hot: true },
      { sector: '消费', keywords: ['消费', '食品', '饮料', '家电'], hot: false },
      { sector: '金融', keywords: ['银行', '证券', '保险', '金融'], hot: false },
      { sector: '汽车', keywords: ['汽车', '车', '电动'], hot: false },
      { sector: '机械/制造', keywords: ['机械', '装备', '制造', '精密'], hot: false },
      { sector: '化工/材料', keywords: ['化工', '材料', '化学', '化纤'], hot: false },
    ]
    let sectorTag = '--'
    let isHotSector = false
    for (const entry of SECTOR_KEYWORDS) {
      if (entry.keywords.some(kw => stockName.includes(kw))) {
        sectorTag = entry.sector
        isHotSector = entry.hot
        break
      }
    }

    return {
      stockName, stockCode, exchange,
      stockPrice: stockPrice ? stockPrice.toFixed(2) : '--',
      stockChange: stockChange ? (stockChange >= 0 ? '+' : '') + stockChange.toFixed(2) + '%' : '--',
      stockChangeUp: stockChange >= 0,
      _stockChangeRaw: stockChange,
      bondName: bondName || '--',
      bondCode: bondCode || '--',
      progress, _status: status,
      issueSize: issueSize ? issueSize.toFixed(2) + '亿' : '--',
      _issueSizeRaw: issueSize,
      rating: rating || '--',
      shareholderRatio: shareholderRatio ? shareholderRatio.toFixed(1) + '%' : '--',
      conversionPrice: conversionPrice ? conversionPrice.toFixed(2) : '--',
      pb: pb ? pb.toFixed(2) : '--',
      cashRatio: cashRatio ? cashRatio.toFixed(2) + '元' : '--',
      _cashRatioRaw: cashRatio,
      perShare: perShare ? perShare.toFixed(4) + '元' : '--',
      sharesFor10: sharesFor10 ? sharesFor10 + '股' : '--',
      _sharesFor10Raw: sharesFor10,
      costFor10Lots: costFor10Lots,
      _costFor10LotsRaw: _costFor10LotsRaw,
      _oneHandMinShares: _oneHandMinShares,
      oneHandMinCost: oneHandMinCost,
      regDate: regDate || '--',
      regBadge, regBadgeClass,
      onlineIssueSize: onlineIssueSize ? onlineIssueSize.toFixed(2) + '亿' : '--',
      winRate: winRate ? (winRate * 100).toFixed(3) + '%' : '--',
      riskLevel: riskLevel,
      riskLabel: riskLabel,
      riskClass: riskClass,
      expectedProfit: Math.round(expectedProfit) + '元',
      _expectedProfitRaw: expectedProfit,
      stockTrend: stockTrend !== 0 ? (stockTrend >= 0 ? '+' : '') + stockTrend.toFixed(2) + '%' : '--',
      _stockTrendRaw: stockTrend,
      recordPrice: recordPrice ? recordPrice.toFixed(2) : '--',
      oneHandParty: oneHandParty,
      safetyPad: _safetyPadValue > 0 ? _safetyPadValue.toFixed(2) + '%' : '--',
      _safetyPadRaw: _safetyPadValue,
      _compositeRankRaw: _compositeRankRaw,
      progressClass: progress.includes('申购') || progress.includes('上市') ? 'hot' : 'warm',
      stageDot: status === '申购中' || status === '待上市' ? 'dot-final' : status === '同意注册' || status === '上市委通过' ? 'dot-mid' : status === '交易所受理' ? 'dot-early' : 'dot-first',
      detail: {
        stockName, stockCode,
        bondName: bondName || '暂无', bondCode: bondCode || '暂无',
        progress, status,
        regDate: regDate || '暂无',
        issueSize: issueSize ? issueSize.toFixed(2) + '亿元' : '暂无',
        rating: rating || '暂无',
        shareholderRatio: shareholderRatio ? shareholderRatio.toFixed(1) + '%' : '暂无',
        conversionPrice: conversionPrice ? conversionPrice.toFixed(2) + '元' : '暂无',
        stockPrice: stockPrice ? stockPrice.toFixed(2) + '元' : '暂无',
        stockChange: stockChange ? (stockChange >= 0 ? '+' : '') + stockChange.toFixed(2) + '%' : '暂无',
        pb: pb ? pb.toFixed(2) : '暂无',
        cashRatio: cashRatio ? cashRatio.toFixed(2) + '元/百元' : '暂无',
        perShare: perShare ? perShare.toFixed(4) + '元' : '暂无',
        sharesFor10: sharesFor10 ? sharesFor10 + '股' : '暂无',
        onlineIssueSize: onlineIssueSize ? onlineIssueSize.toFixed(2) + '亿元' : '暂无',
        winRate: winRate ? (winRate * 100).toFixed(3) + '%' : '暂无',
        riskLevel: riskLevel,
        riskLabel: riskLabel,
        riskClass: riskClass,
        safetyPad: _safetyPadValue > 0 ? _safetyPadValue.toFixed(2) + '%' : '暂无',
        _safetyPadRaw: _safetyPadValue,
        expectedProfit: expectedProfit > 0 ? Math.round(expectedProfit) + '元' : '暂无',
        _expectedProfitRaw: expectedProfit,
        stockTrend: stockTrend !== 0 ? (stockTrend >= 0 ? '+' : '') + stockTrend.toFixed(2) + '%' : '暂无',
        recordPrice: recordPrice ? recordPrice.toFixed(2) + '元' : '暂无',
        ma20Price: ma20Price ? ma20Price.toFixed(2) + '元' : '暂无',
        stageList: stageList,
        sectorTag: sectorTag,
        isHotSector: isHotSector,
      }
    }
  },

  openPendingDetail(e) {
    const { index } = e.currentTarget.dataset
    const item = this.data.currentList[index]
    if (!item) return
    this.setData({
      selectedPending: {
        ...item.detail,
        _premiumRate: 20,
      },
      showPendingModal: true
    })
  },

  closePendingModal() {
    this.setData({ showPendingModal: false, selectedPending: null })
  },

  onPremiumRateChange(e) {
    const rate = e.detail.value
    const detail = this.data.selectedPending
    if (!detail) return
    const sp = detail._safetyPadRaw || 0
    const profit = detail._expectedProfitRaw || 0
    // rate is in percentage (10-50), convert to decimal
    const premiumDecimal = rate / 100
    // 用原数据(未格式化)重新计算
    const spRaw = detail._safetyPadRaw || 0
    if (spRaw > 0) {
      // safety pad scales linearly with premium rate
      const newPad = spRaw * (premiumDecimal / 0.2)
      const newProfit = 1000 * premiumDecimal
      this.setData({
        'selectedPending._premiumRate': rate,
        'selectedPending.safetyPad': newPad.toFixed(2) + '%',
        'selectedPending.expectedProfit': Math.round(newProfit) + '元'
      })
    }
  },

  copyText(e) {
    const { text } = e.currentTarget.dataset
    wx.setClipboardData({
      data: text,
      success: () => wx.showToast({ title: '已复制', icon: 'success' })
    })
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
    const favCodes = favoriteManager.getCodesByType('bond')
    const newSignals = {}

    const fields = ['double_low', 'force_redeem', 'discount', 'down_revised']

    fields.forEach(field => {
      newSignals[field] = (this.data.signals[field] || []).map(item => ({
        ...item,
        isFavorite: favCodes.has(item.bondCode)
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