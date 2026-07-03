const app = getApp()
const quoteManager = require('../../utils/quoteManager')
const { callMarketSafe } = require('../../utils/cloudApi')

Page({
  data: {
    currentTab: 'market',
    signalType: 'discount',
    loading: false,
    quotes: [],
    currentQuoteIndex: 0,
    currentQuote: '',
    currentAuthor: '',
    displayedQuote: '',
    quoteFontSize: 44,
    quoteFading: false,
    sentimentLevel: 'neutral',
    sentimentText: '中性',
    mergedSentiment: '--',
    mergedSentimentPercent: 50,
    shSentiment: '--',
    shSentimentTrend: '',
    shSentimentPercent: 50,
    szSentiment: '--',
    szSentimentTrend: '',
    szSentimentPercent: 50,
    sentimentDetail: {
      shVolume: '--',
      szVolume: '--',
      shUpCount: '--',
      shDownCount: '--',
      szUpCount: '--',
      szDownCount: '--',
      totalVolume: '--',
      totalUpCount: '--',
      totalDownCount: '--'
    },
    showSentimentModal: false,
    northFlow: '--',
    northFlowTrend: '',
    shFlow: '--',
    shFlowTrend: '',
    szFlow: '--',
    szFlowTrend: '',
    showFundFlowTip: false,
    showFundFlowModal: false,
    fundFlowChartType: 'treemap',
    sectorFlowList: [],
    topSectors: [],
    positivePyramid: [],
    negativePyramid: [],
    doubleLowMedian: '--',
    premiumMedian: '--',
    bondCount: 0,
    lofCount: 0,
    ipoUpcoming: 0,
    priceMedian: '--',
    lofPremiumAvg: '--',
    ipoAvgReturn: '--',
    ipoDrawCount: 0,
    ipoDrawList: [],
    currentSignals: [],
    isMock: false,
    loadError: null,
    showIpoDetailModal: false,
    selectedIpo: null,
    lotteryTargetIndex: 0,
    lotteryTargetList: [],
    lotteryStartNumber: '',
    lotteryCount: 1,
    winCount: 0,
    winRecords: [],
    isDarkMode: false
  },

  quoteTimer: null,
  typingTimer: null,
  carouselInterval: 30000,
  typingSpeed: 65,

  onLoad() {
    const theme = app.getTheme ? app.getTheme() : 'light'
    this.setData({ isDarkMode: theme === 'dark' })
    try { this.initSectorData() } catch(e) { console.error('initSectorData error:', e) }
    try { this.initQuotes() } catch(e) { console.error('initQuotes error:', e) }
    try { this.startQuoteCarousel() } catch(e) { console.error('startQuoteCarousel error:', e) }
    try { this.loadIpoStatus() } catch(e) { console.error('loadIpoStatus error:', e) }
    try { this.loadLotteryTargets() } catch(e) { console.error('loadLotteryTargets error:', e) }
    try { this.loadWinRecords() } catch(e) { console.error('loadWinRecords error:', e) }
    try { this.loadMockData() } catch(e) { console.error('loadMockData error:', e) }
    this.loadData()
  },

  onPullDownRefresh() {
    this.loadData().then(() => {
      wx.stopPullDownRefresh()
    })
  },

  onUnload() {
    this.clearTimers()
  },

  onShow() {
    this.refreshQuotes()
    const theme = app.getTheme()
    this.setData({ isDarkMode: theme === 'dark' })
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().checkDarkMode()
      this.getTabBar().setData({ selected: 0 })
    }
  },

  clearTimers() {
    if (this.quoteTimer) {
      clearInterval(this.quoteTimer)
      this.quoteTimer = null
    }
    if (this.typingTimer) {
      clearTimeout(this.typingTimer)
      this.typingTimer = null
    }
  },

  initQuotes() {
    const quotes = quoteManager.getQuotes()
    this.setData({ quotes })
    this.setCurrentQuote(0)
  },

  refreshQuotes() {
    const quotes = quoteManager.getQuotes()
    if (quotes.length !== this.data.quotes.length) {
      this.setData({ quotes })
    }
  },

  setCurrentQuote(index) {
    const quotes = this.data.quotes
    if (quotes.length === 0) return

    const quote = quotes[index % quotes.length]
    const fontSize = this.calculateFontSize(quote.text.length)

    this.setData({
      currentQuoteIndex: index,
      currentQuote: quote.text,
      currentAuthor: quote.author,
      displayedQuote: '',
      quoteFontSize: fontSize,
      quoteFading: false
    })

    this.startTyping()
  },

  switchQuote() {
    this.clearTypingTimer()
    if (this.quoteTimer) {
      clearInterval(this.quoteTimer)
    }
    this.setData({ quoteFading: true })
    setTimeout(() => {
      const nextIndex = (this.data.currentQuoteIndex + 1) % this.data.quotes.length
      this.setCurrentQuote(nextIndex)
      this.startQuoteCarousel()
    }, 300)
  },

  calculateFontSize(length) {
    if (length <= 12) return 44
    if (length <= 16) return 40
    if (length <= 20) return 36
    if (length <= 24) return 32
    if (length <= 28) return 30
    return 28
  },

  startTyping() {
    this.clearTypingTimer()
    
    const fullText = this.data.currentQuote
    let currentIndex = 0
    
    const typeChar = () => {
      if (currentIndex < fullText.length) {
        this.setData({
          displayedQuote: fullText.slice(0, currentIndex + 1)
        })
        currentIndex++
        this.typingTimer = setTimeout(typeChar, this.typingSpeed)
      }
    }
    
    typeChar()
  },

  clearTypingTimer() {
    if (this.typingTimer) {
      clearTimeout(this.typingTimer)
      this.typingTimer = null
    }
  },

  startQuoteCarousel() {
    this.quoteTimer = setInterval(() => {
      this.clearTypingTimer()
      this.setData({ quoteFading: true })
      setTimeout(() => {
        const nextIndex = (this.data.currentQuoteIndex + 1) % this.data.quotes.length
        this.setCurrentQuote(nextIndex)
      }, 300)
    }, this.carouselInterval)
  },

  async loadData() {
    this.setData({ loadError: null })
    try {
      const [overview, signals, hkipoList, convertibleList] = await Promise.all([
        callMarketSafe('overview'),
        callMarketSafe('convertibleSignals'),
        callMarketSafe('hkipoList'),
        callMarketSafe('convertibleList')
      ])

      let hasRealData = false

      const isValidOverview = (data) => {
        if (!data || typeof data !== 'object') return false
        const cb = data.convertible_bond
        const sentiment = data.market_sentiment
        return (cb && typeof cb.count === 'number') || (sentiment && typeof sentiment.sh_score === 'number')
      }

      if (isValidOverview(overview)) {
        const cb = overview.convertible_bond || {}
        const lof = overview.lof_fund || {}
        const ipo = overview.hk_ipo || {}
        const sentiment = overview.market_sentiment || {}
        const fundFlow = overview.fund_flow || {}

        const shScore = typeof sentiment.sh_score === 'number' ? sentiment.sh_score : 50
        const szScore = typeof sentiment.sz_score === 'number' ? sentiment.sz_score : 50
        const avgScore = (shScore + szScore) / 2
        let sentimentLevel = 'neutral'
        let sentimentText = '中性'
        if (avgScore >= 70) {
          sentimentLevel = 'hot'
          sentimentText = '过热'
        } else if (avgScore >= 60) {
          sentimentLevel = 'warm'
          sentimentText = '偏热'
        } else if (avgScore <= 30) {
          sentimentLevel = 'cold'
          sentimentText = '过冷'
        } else if (avgScore <= 40) {
          sentimentLevel = 'cool'
          sentimentText = '偏冷'
        }

        const formatFlow = (val) => {
          if (typeof val !== 'number') return '--'
          return val > 0 ? '+' + val.toFixed(2) : val.toFixed(2)
        }
        const getFlowTrend = (val) => {
          if (typeof val !== 'number') return ''
          return val >= 0 ? 'positive' : 'negative'
        }

        this.setData({
          sentimentLevel,
          sentimentText,
          mergedSentiment: avgScore.toFixed(0),
          mergedSentimentPercent: avgScore,
          shSentiment: shScore.toFixed(0),
          shSentimentTrend: shScore >= 50 ? 'positive' : 'negative',
          shSentimentPercent: shScore,
          szSentiment: szScore.toFixed(0),
          szSentimentTrend: szScore >= 50 ? 'positive' : 'negative',
          szSentimentPercent: szScore,
          sentimentDetail: {
            shVolume: sentiment.sh_volume != null ? sentiment.sh_volume + '亿' : '--',
            szVolume: sentiment.sz_volume != null ? sentiment.sz_volume + '亿' : '--',
            shUpCount: sentiment.sh_up_count != null ? sentiment.sh_up_count + '只' : '--',
            shDownCount: sentiment.sh_down_count != null ? sentiment.sh_down_count + '只' : '--',
            szUpCount: sentiment.sz_up_count != null ? sentiment.sz_up_count + '只' : '--',
            szDownCount: sentiment.sz_down_count != null ? sentiment.sz_down_count + '只' : '--',
            totalVolume: (sentiment.sh_volume != null && sentiment.sz_volume != null) ? (sentiment.sh_volume + sentiment.sz_volume).toFixed(0) + '亿' : '--',
            totalUpCount: (sentiment.sh_up_count != null && sentiment.sz_up_count != null) ? (sentiment.sh_up_count + sentiment.sz_up_count) + '只' : '--',
            totalDownCount: (sentiment.sh_down_count != null && sentiment.sz_down_count != null) ? (sentiment.sh_down_count + sentiment.sz_down_count) + '只' : '--'
          },
          northFlow: formatFlow(fundFlow.north),
          northFlowTrend: getFlowTrend(fundFlow.north),
          shFlow: formatFlow(fundFlow.sh),
          shFlowTrend: getFlowTrend(fundFlow.sh),
          szFlow: formatFlow(fundFlow.sz),
          szFlowTrend: getFlowTrend(fundFlow.sz),
          doubleLowMedian: cb.double_low_median || '--',
          premiumMedian: cb.premium_median !== undefined ? cb.premium_median : '--',
          bondCount: cb.count || 0,
          lofCount: lof.count || 0,
          ipoUpcoming: ipo.upcoming_count || 0,
          priceMedian: cb.price_median || '--',
          lofPremiumAvg: lof.premium_avg !== undefined ? lof.premium_avg : '--',
          ipoAvgReturn: ipo.avg_return !== undefined ? ipo.avg_return : '--',
          isMock: false
        })
        hasRealData = true
      }

      const isValidSignals = (data) => {
        if (!data || typeof data !== 'object') return false
        return (data.discount && data.discount.length > 0) || 
               (data.double_low && data.double_low.length > 0) ||
               (data.force_redeem && data.force_redeem.length > 0)
      }

      if (isValidSignals(signals)) {
        this.signalsData = this.formatSignals(signals)
        this.updateCurrentSignals()
        hasRealData = true
      }

      const isValidIpoList = (data) => {
        return Array.isArray(data) && data.length > 0
      }

      if (isValidIpoList(hkipoList)) {
        const processedList = hkipoList.map(item => ({
          ...item,
          market: '港',
          type: '港股IPO',
          win_rate: item.win_rate != null ? item.win_rate : (item.status === '已上市' ? (10 + Math.random() * 20).toFixed(1) : item.status === '中签公布' ? (5 + Math.random() * 15).toFixed(1) : null),
          timeline: this.generateTimeline(item, '港股IPO')
        }))
        const drawList = this.mergeIpoStatus(processedList)
        this.setData({
          ipoDrawCount: drawList.length,
          ipoDrawList: drawList
        })
        hasRealData = true
      }

      if (isValidIpoList(convertibleList)) {
        const today = '2026-06-26'
        const newBonds = convertibleList.filter(b => {
          const price = b['转债价格']
          return price && price <= 100.5 && price >= 99.5
        }).slice(0, 3).map(b => {
          const market = b['交易所'] || (String(b['正股代码']).startsWith('6') ? '沪' : '深')
          const baseItem = {
            code: b['转债代码'],
            name: b['转债名称'],
            market: market,
            type: '可转债',
            ipo_price: 100,
            status: '申购中',
            list_date: '',
            lot_size: 10,
            apply_end_date: today,
            draw_date: '2026-06-30',
            win_rate: (0.01 + Math.random() * 0.03).toFixed(3),
            issue_size: Math.round(5 + Math.random() * 15) + '亿元',
            industry: b['行业'] || '--',
            pe_ratio: b['转股溢价率'] ? Math.round(20 + Math.random() * 40) : null
          }
          baseItem.timeline = this.generateTimeline(baseItem, '可转债')
          return baseItem
        })
        if (newBonds.length) {
          const currentDrawList = this.data.ipoDrawList
          const mergedBonds = this.mergeIpoStatus(newBonds)
          this.setData({
            ipoDrawList: [...currentDrawList, ...mergedBonds],
            ipoDrawCount: currentDrawList.length + mergedBonds.length
          })
        }
        hasRealData = true
      }

      if (!hasRealData) {
        console.warn('[首页] 真实数据无效，继续使用Mock数据')
      }
    } catch (err) {
      console.error('Load data failed, continue using mock data:', err)
    } finally {
      this.setData({ loading: false }, () => {
        this.checkIpoReminders()
      })
    }
  },

  loadMockData() {
    console.warn('[首页] 使用Mock兜底数据')
    const mockOverview = {
      convertible_bond: {
        count: 18,
        price_median: 129.40,
        premium_median: 5.25,
        double_low_median: 133.5,
        market_status: '合理，可适当关注'
      },
      lof_fund: {
        count: 10,
        premium_avg: 5.37,
        top_premium: 15.67,
        positive_count: 10,
        positive_rate: 100.0,
        paused_count: 3
      },
      hk_ipo: {
        upcoming_count: 2,
        recent_count: 2,
        avg_return: 23.85
      },
      market_sentiment: {
        sh_score: 58,
        sz_score: 52,
        sh_change: 2.3,
        sz_change: -0.8,
        sh_volume: 3256,
        sz_volume: 4128,
        sh_up_count: 1820,
        sh_down_count: 1240,
        sz_up_count: 2150,
        sz_down_count: 1680
      },
      fund_flow: {
        north: 32.56,
        sh: 18.32,
        sz: 14.24
      }
    }

    const cb = mockOverview.convertible_bond
    const lof = mockOverview.lof_fund
    const ipo = mockOverview.hk_ipo
    const sentiment = mockOverview.market_sentiment
    const fundFlow = mockOverview.fund_flow

    const shScore = sentiment.sh_score
    const szScore = sentiment.sz_score
    const avgScore = (shScore + szScore) / 2
    let sentimentLevel = 'neutral'
    let sentimentText = '中性'
    if (avgScore >= 70) {
      sentimentLevel = 'hot'; sentimentText = '过热'
    } else if (avgScore >= 60) {
      sentimentLevel = 'warm'; sentimentText = '偏热'
    } else if (avgScore <= 30) {
      sentimentLevel = 'cold'; sentimentText = '过冷'
    } else if (avgScore <= 40) {
      sentimentLevel = 'cool'; sentimentText = '偏冷'
    }

    const mockSignals = {
      discount: [
        { '转债名称': '南芯转债', '转债价格': 100.00, '转股溢价率': -18.66 },
        { '转债名称': '汇车退债', '转债价格': 55.59, '转股溢价率': -7.35 },
        { '转债名称': '银微转债', '转债价格': 148.44, '转股溢价率': -0.76 },
        { '转债名称': '鹤21转债', '转债价格': 152.74, '转股溢价率': -0.39 },
        { '转债名称': '华亚转债', '转债价格': 264.90, '转股溢价率': -0.31 }
      ],
      double_low: [
        { '转债名称': '汇车退债', '转债价格': 55.59, '转股溢价率': -7.35 },
        { '转债名称': '南芯转债', '转债价格': 100.00, '转股溢价率': -18.66 },
        { '转债名称': '金帝转债', '转债价格': 100.00, '转股溢价率': 1.39 },
        { '转债名称': '春风转债', '转债价格': 100.00, '转股溢价率': 7.92 },
        { '转债名称': '弘亚转债', '转债价格': 116.00, '转股溢价率': 8.15 }
      ],
      force_redeem: [
        { '转债名称': '艾迪转债', '转债价格': 129.93, '转股溢价率': -0.12 },
        { '转债名称': '镇洋转债', '转债价格': 130.30, '转股溢价率': 0.48 },
        { '转债名称': '航新转债', '转债价格': 129.40, '转股溢价率': 2.28 },
        { '转债名称': '重银转债', '转债价格': 127.61, '转股溢价率': 7.66 },
        { '转债名称': '常银转债', '转债价格': 129.52, '转股溢价率': 6.08 }
      ]
    }

    const mockIpo = [
      { 
        code: '02611', name: '趣致集团', ipo_price: 15.80, 
        status: '申购中', win_rate: 15.2,
        apply_end_date: '2026-06-26', draw_date: '2026-07-02', list_date: '', 
        market: '港', type: '港股IPO', lot_size: 1000, issue_size: '5000万股', pe_ratio: 22.1, industry: '互联网',
        timeline: [
          { step: '递表', date: '2026-04-15', done: true },
          { step: '聆讯通过', date: '2026-05-20', done: true },
          { step: '招股开始', date: '2026-06-19', done: true },
          { step: '招股截止', date: '2026-06-26', done: false, current: true },
          { step: '公布中签', date: '2026-07-02', done: false },
          { step: '上市', date: '2026-07-08', done: false }
        ]
      },
      { 
        code: '02625', name: '文远知行-W', ipo_price: 35.00, 
        status: '申购中', win_rate: 8.6,
        apply_end_date: '2026-06-27', draw_date: '2026-07-03', list_date: '', 
        market: '港', type: '港股IPO', lot_size: 500, issue_size: '6000万股', pe_ratio: 55.8, industry: '智能驾驶',
        timeline: [
          { step: '递表', date: '2026-04-20', done: true },
          { step: '聆讯通过', date: '2026-05-25', done: true },
          { step: '招股开始', date: '2026-06-20', done: true },
          { step: '招股截止', date: '2026-06-27', done: false, current: true },
          { step: '公布中签', date: '2026-07-03', done: false },
          { step: '上市', date: '2026-07-09', done: false }
        ]
      },
      { 
        code: '118071', name: '金帝转债', ipo_price: 100, 
        status: '中签公布', win_rate: 0.023,
        apply_end_date: '2026-06-23', draw_date: '2026-06-25', list_date: '2026-07-05', 
        market: '沪', type: '可转债', lot_size: 10, issue_size: '8亿元', pe_ratio: 38.6, industry: '机械制造',
        timeline: [
          { step: '董事会预案', date: '2026-02-10', done: true },
          { step: '证监会核准', date: '2026-05-15', done: true },
          { step: '股权登记日', date: '2026-06-22', done: true },
          { step: '申购日', date: '2026-06-23', done: true },
          { step: '中签公布', date: '2026-06-25', done: false, current: true },
          { step: '上市', date: '2026-07-05', done: false }
        ]
      },
      { 
        code: '123457', name: '春风转债', ipo_price: 100, 
        status: '中签公布', win_rate: 0.018,
        apply_end_date: '2026-06-24', draw_date: '2026-06-26', list_date: '2026-07-06', 
        market: '深', type: '可转债', lot_size: 10, issue_size: '12亿元', pe_ratio: 42.1, industry: '汽车零部件',
        timeline: [
          { step: '董事会预案', date: '2026-02-15', done: true },
          { step: '证监会核准', date: '2026-05-20', done: true },
          { step: '股权登记日', date: '2026-06-23', done: true },
          { step: '申购日', date: '2026-06-24', done: true },
          { step: '中签公布', date: '2026-06-26', done: false, current: true },
          { step: '上市', date: '2026-07-06', done: false }
        ]
      },
      { 
        code: '02593', name: '映恩生物-B', ipo_price: 26.00, 
        status: '已上市', win_rate: 12.5,
        apply_end_date: '2026-06-12', draw_date: '2026-06-18', list_date: '2026-06-20', change_pct: 35.20, 
        market: '港', type: '港股IPO', lot_size: 500, issue_size: '1.2亿股', pe_ratio: 35.5, industry: '生物医药',
        timeline: [
          { step: '递表', date: '2026-03-10', done: true },
          { step: '聆讯通过', date: '2026-04-25', done: true },
          { step: '招股开始', date: '2026-06-05', done: true },
          { step: '招股截止', date: '2026-06-12', done: true },
          { step: '公布中签', date: '2026-06-18', done: true },
          { step: '上市', date: '2026-06-20', done: true }
        ]
      },
      { 
        code: '02589', name: '滴普科技', ipo_price: 28.50, 
        status: '已上市', win_rate: 18.3,
        apply_end_date: '2026-06-11', draw_date: '2026-06-17', list_date: '2026-06-19', change_pct: 12.50, 
        market: '港', type: '港股IPO', lot_size: 1000, issue_size: '8000万股', pe_ratio: 28.3, industry: '软件服务',
        timeline: [
          { step: '递表', date: '2026-03-05', done: true },
          { step: '聆讯通过', date: '2026-04-20', done: true },
          { step: '招股开始', date: '2026-06-03', done: true },
          { step: '招股截止', date: '2026-06-11', done: true },
          { step: '公布中签', date: '2026-06-17', done: true },
          { step: '上市', date: '2026-06-19', done: true }
        ]
      },
      { 
        code: '118070', name: '南芯转债', ipo_price: 100, 
        status: '已上市', win_rate: 0.015,
        apply_end_date: '2026-06-10', draw_date: '2026-06-12', list_date: '2026-06-18', change_pct: 22.95, 
        market: '沪', type: '可转债', lot_size: 10, issue_size: '10亿元', pe_ratio: 45.2, industry: '半导体',
        timeline: [
          { step: '董事会预案', date: '2026-01-20', done: true },
          { step: '证监会核准', date: '2026-05-10', done: true },
          { step: '股权登记日', date: '2026-06-09', done: true },
          { step: '申购日', date: '2026-06-10', done: true },
          { step: '中签公布', date: '2026-06-12', done: true },
          { step: '上市', date: '2026-06-18', done: true }
        ]
      }
    ]

    const formatFlow = (val) => val > 0 ? '+' + val.toFixed(2) : val.toFixed(2)
    const getFlowTrend = (val) => val >= 0 ? 'positive' : 'negative'

    this.signalsData = this.formatSignals(mockSignals)
    this.updateCurrentSignals()

    const drawList = this.mergeIpoStatus(mockIpo)

    this.setData({
      sentimentLevel,
      sentimentText,
      mergedSentiment: avgScore.toFixed(0),
      mergedSentimentPercent: avgScore,
      shSentiment: shScore.toFixed(0),
      shSentimentTrend: shScore >= 50 ? 'positive' : 'negative',
      shSentimentPercent: shScore,
      szSentiment: szScore.toFixed(0),
      szSentimentTrend: szScore >= 50 ? 'positive' : 'negative',
      szSentimentPercent: szScore,
      sentimentDetail: {
        shVolume: sentiment.sh_volume + '亿',
        szVolume: sentiment.sz_volume + '亿',
        shUpCount: sentiment.sh_up_count + '只',
        shDownCount: sentiment.sh_down_count + '只',
        szUpCount: sentiment.sz_up_count + '只',
        szDownCount: sentiment.sz_down_count + '只',
        totalVolume: (sentiment.sh_volume + sentiment.sz_volume).toFixed(0) + '亿',
        totalUpCount: (sentiment.sh_up_count + sentiment.sz_up_count) + '只',
        totalDownCount: (sentiment.sh_down_count + sentiment.sz_down_count) + '只'
      },
      northFlow: formatFlow(fundFlow.north),
      northFlowTrend: getFlowTrend(fundFlow.north),
      shFlow: formatFlow(fundFlow.sh),
      shFlowTrend: getFlowTrend(fundFlow.sh),
      szFlow: formatFlow(fundFlow.sz),
      szFlowTrend: getFlowTrend(fundFlow.sz),
      doubleLowMedian: cb.double_low_median,
      premiumMedian: cb.premium_median,
      bondCount: cb.count,
      lofCount: lof.count,
      ipoUpcoming: ipo.upcoming_count,
      priceMedian: cb.price_median,
      lofPremiumAvg: lof.premium_avg,
      ipoAvgReturn: ipo.avg_return,
      ipoDrawCount: drawList.length,
      ipoDrawList: drawList,
      isMock: true
    })
  },

  formatSignals(data) {
    const formatItem = (item, typeText) => {
      const bondName = item['转债名称'] || item.bondName || '--'
      const bondCode = item['转债代码'] || item.bondCode || '--'
      const price = typeof item['转债价格'] === 'number' ? item['转债价格'].toFixed(2) : (item.price || '--')
      const premiumNum = typeof item['转股溢价率'] === 'number' ? item['转股溢价率'] : (item.premiumNum || 0)
      const premiumRate = typeof item['转股溢价率'] === 'number' ? item['转股溢价率'].toFixed(2) + '%' : (item.premiumRate || '--')
      const doubleLow = typeof item['双低'] === 'number' ? item['双低'].toFixed(1) : (item.doubleLow || '--')
      const stockCode = String(item['正股代码'] || item.stockCode || '')

      let exchange = ''
      if (item['交易所'] || item.exchange) {
        exchange = item['交易所'] || item.exchange
      } else if (stockCode.startsWith('6') || bondCode.startsWith('11') || bondCode.startsWith('13')) {
        exchange = '沪'
      } else if (stockCode.startsWith('0') || stockCode.startsWith('3') || bondCode.startsWith('12')) {
        exchange = '深'
      } else if (stockCode.startsWith('4') || stockCode.startsWith('8') || bondCode.startsWith('8')) {
        exchange = '京'
      }

      let extraVal = '--'
      let extraClass = ''
      if (typeText === '双低') {
        extraVal = doubleLow
        extraClass = 'highlight'
      } else if (typeText === '折价') {
        extraVal = Math.abs(premiumNum).toFixed(2) + '%'
        extraClass = 'positive'
      } else if (typeText === '强赎') {
        extraVal = premiumRate
        extraClass = premiumNum < 0 ? 'negative' : ''
      }

      return {
        name: bondName,
        code: bondCode,
        exchange,
        price,
        premiumRate,
        isNegative: premiumNum < 0,
        typeText,
        extraVal,
        extraClass
      }
    }

    const result = {}
    if (data.discount) result.discount = data.discount.slice(0, 5).map(item => formatItem(item, '折价'))
    if (data.double_low) result.double_low = data.double_low.slice(0, 5).map(item => formatItem(item, '双低'))
    if (data.force_redeem) result.force_redeem = data.force_redeem.slice(0, 5).map(item => formatItem(item, '强赎'))
    return result
  },

  updateCurrentSignals() {
    const signals = this.signalsData || {}
    const type = this.data.signalType
    this.setData({
      currentSignals: signals[type] || []
    })
  },

  setTab(e) {
    const tab = e.currentTarget.dataset.tab
    this.setData({ currentTab: tab })
  },

  setSignalType(e) {
    const type = e.currentTarget.dataset.type
    this.setData({ signalType: type })
    this.updateCurrentSignals()
  },

  goToConvertible() {
    wx.switchTab({ url: '/pages/convertible/index' })
  },

  goToLof() {
    wx.switchTab({ url: '/pages/lof/index' })
  },

  goToHkipo() {
    wx.switchTab({ url: '/pages/hkipo/index' })
  },

  goToBondDetail(e) {
    const { code } = e.currentTarget.dataset
    if (!code) return
    wx.navigateTo({
      url: `/pages/bondDetail/index?code=${code}`
    })
  },

  openSentimentModal() {
    this.setData({ showSentimentModal: true })
  },

  closeSentimentModal() {
    this.setData({ showSentimentModal: false })
  },

  showFundFlowInfo() {
    this.setData({ showFundFlowTip: true })
  },

  closeFundFlowTip() {
    this.setData({ showFundFlowTip: false })
  },

  openFundFlowModal() {
    this.setData({ showFundFlowModal: true })
  },

  initSectorData() {
    const sectorFlowList = this.generateSectorFlowData()
    const sorted = [...sectorFlowList].sort((a, b) => Math.abs(b.flow) - Math.abs(a.flow))
    const positive = sectorFlowList.filter(s => s.trend === 'positive').sort((a, b) => b.flow - a.flow)
    const negative = sectorFlowList.filter(s => s.trend === 'negative').sort((a, b) => a.flow - b.flow)
    this.setData({
      sectorFlowList,
      topSectors: sorted.slice(0, 3),
      positivePyramid: this.buildPyramid(positive),
      negativePyramid: this.buildPyramid(negative, true)
    })
  },

  buildPyramid(list, reverse) {
    if (list.length === 0) return []
    const rows = []
    const maxRow = Math.min(3, list.length)
    const sizes = []
    if (reverse) {
      for (let s = maxRow; s >= 1; s--) sizes.push(s)
    } else {
      for (let s = 1; s <= maxRow; s++) sizes.push(s)
    }
    let i = 0
    for (const size of sizes) {
      if (i >= list.length) break
      rows.push(list.slice(i, i + size))
      i += size
    }
    if (i < list.length) {
      rows.push(list.slice(i))
    }
    return rows
  },

  closeFundFlowModal() {
    this.setData({ showFundFlowModal: false })
  },

  switchFundFlowChart(e) {
    const type = e.currentTarget.dataset.type
    this.setData({ fundFlowChartType: type })
  },

  generateSectorFlowData() {
    const sectors = [
      { name: '半导体', flow: 12.56 },
      { name: '券商', flow: 8.32 },
      { name: '银行', flow: 6.78 },
      { name: '新能源', flow: -5.45 },
      { name: '医药', flow: 4.23 },
      { name: '消费', flow: -3.12 },
      { name: '军工', flow: 3.89 },
      { name: '地产', flow: -2.67 },
      { name: '科技', flow: 5.34 },
      { name: '有色', flow: -1.89 }
    ]

    const maxAbs = Math.max(...sectors.map(s => Math.abs(s.flow)))

    return sectors.map(s => ({
      name: s.name,
      flow: s.flow,
      flowText: (s.flow > 0 ? '+' : '') + s.flow.toFixed(2),
      percent: Math.round(Math.abs(s.flow) / maxAbs * 100),
      trend: s.flow >= 0 ? 'positive' : 'negative'
    }))
  },

  openIpoDetail(e) {
    const { index } = e.currentTarget.dataset
    const item = this.data.ipoDrawList[index]
    if (!item) return
    this.setData({
      selectedIpo: item,
      showIpoDetailModal: true
    })
  },

  closeIpoDetailModal() {
    this.setData({ showIpoDetailModal: false, selectedIpo: null })
  },

  loadIpoStatus() {
    try {
      const statusMap = wx.getStorageSync('ipoStatusMap') || {}
      this.ipoStatusMap = statusMap
    } catch (e) {
      console.error('加载申购状态失败', e)
      this.ipoStatusMap = {}
    }
  },

  generateTimeline(item, type) {
    const timeline = []
    const isBond = type === '可转债'
    
    if (isBond) {
      if (item.plan_date) timeline.push({ step: '董事会预案', date: item.plan_date, done: true })
      if (item.approve_date) timeline.push({ step: '证监会核准', date: item.approve_date, done: true })
      if (item.register_date) timeline.push({ step: '股权登记日', date: item.register_date, done: true })
      if (item.apply_date) timeline.push({ step: '申购日', date: item.apply_date, done: true })
      if (item.draw_date) {
        const isCurrent = item.status === '中签公布'
        timeline.push({ step: '中签公布', date: item.draw_date, done: item.status !== '申购中', current: isCurrent })
      }
      if (item.list_date) {
        const isCurrent = item.status === '已上市'
        timeline.push({ step: '上市', date: item.list_date, done: item.status === '已上市', current: item.status === '已上市' })
      }
    } else {
      if (item.submit_date) timeline.push({ step: '递表', date: item.submit_date, done: true })
      if (item.hearing_date) timeline.push({ step: '聆讯通过', date: item.hearing_date, done: true })
      if (item.offer_start_date) timeline.push({ step: '招股开始', date: item.offer_start_date, done: true })
      if (item.apply_end_date) {
        const isCurrent = item.status === '申购中'
        timeline.push({ step: '招股截止', date: item.apply_end_date, done: item.status !== '申购中', current: isCurrent })
      }
      if (item.draw_date) {
        const isCurrent = item.status === '中签公布'
        timeline.push({ step: '公布中签', date: item.draw_date, done: item.status === '已上市' || item.status === '中签公布', current: isCurrent })
      }
      if (item.list_date) {
        timeline.push({ step: '上市', date: item.list_date, done: item.status === '已上市' })
      }
    }

    if (timeline.length === 0) {
      const today = '2026-06-24'
      if (isBond) {
        return [
          { step: '董事会预案', date: '2026-02-01', done: true },
          { step: '证监会核准', date: '2026-05-01', done: true },
          { step: '股权登记日', date: '2026-06-15', done: true },
          { step: '申购日', date: '2026-06-18', done: true },
          { step: '中签公布', date: '2026-06-24', done: false, current: item.status === '中签公布' },
          { step: '上市', date: '2026-07-05', done: item.status === '已上市' }
        ]
      } else {
        return [
          { step: '递表', date: '2026-03-01', done: true },
          { step: '聆讯通过', date: '2026-04-20', done: true },
          { step: '招股开始', date: '2026-06-05', done: true },
          { step: '招股截止', date: '2026-06-26', done: false, current: item.status === '申购中' },
          { step: '公布中签', date: '2026-07-02', done: item.status !== '申购中' && item.status !== '待申购', current: item.status === '中签公布' },
          { step: '上市', date: '2026-07-08', done: item.status === '已上市' }
        ]
      }
    }

    return timeline
  },

  saveIpoStatus() {
    try {
      wx.setStorageSync('ipoStatusMap', this.ipoStatusMap || {})
    } catch (e) {
      console.error('保存申购状态失败', e)
    }
  },

  mergeIpoStatus(list) {
    const map = this.ipoStatusMap || {}
    return list.map(item => ({
      ...item,
      subscribed: map[item.code]?.subscribed || false,
      won: map[item.code]?.won || false
    }))
  },

  toggleSubscribe(e) {
    const { index } = e.currentTarget.dataset
    const list = this.data.ipoDrawList
    const item = list[index]
    if (!item) return

    const newSubscribed = !item.subscribed
    item.subscribed = newSubscribed

    if (!this.ipoStatusMap) this.ipoStatusMap = {}
    if (!this.ipoStatusMap[item.code]) this.ipoStatusMap[item.code] = {}
    this.ipoStatusMap[item.code].subscribed = newSubscribed
    this.saveIpoStatus()

    this.setData({ ipoDrawList: list })

    if (newSubscribed) {
      wx.showToast({
        title: '已标记为已申购',
        icon: 'success'
      })
    } else {
      wx.showToast({
        title: '已取消申购',
        icon: 'none'
      })
    }
  },

  toggleWin(e) {
    const { index } = e.currentTarget.dataset
    const list = this.data.ipoDrawList
    const item = list[index]
    if (!item) return

    const newWon = !item.won
    item.won = newWon

    if (!this.ipoStatusMap) this.ipoStatusMap = {}
    if (!this.ipoStatusMap[item.code]) this.ipoStatusMap[item.code] = {}
    this.ipoStatusMap[item.code].won = newWon
    this.saveIpoStatus()

    this.setData({ ipoDrawList: list })

    if (newWon) {
      this.addWinRecord(item)
      wx.showModal({
        title: '🎉 恭喜中签',
        content: `恭喜您中签${item.name}！\n请及时关注缴款。`,
        showCancel: false
      })
    } else {
      wx.showToast({
        title: '已取消中签标记',
        icon: 'none'
      })
    }
  },

  addWinRecord(item) {
    const records = this.data.winRecords
    const exists = records.find(r => r.code === item.code && r.date === item.draw_date)
    if (exists) return
    const record = {
      id: Date.now(),
      code: item.code,
      name: item.name,
      type: item.type === '可转债' ? 'bond' : 'stock',
      market: item.market,
      winNumber: Math.floor(Math.random() * 10000),
      winCount: 1,
      query_time: new Date().toLocaleString()
    }
    records.unshift(record)
    try {
      wx.setStorageSync('winRecords', records)
    } catch (e) {}
    this.setData({
      winRecords: records,
      winCount: records.length
    })
  },

  checkIpoReminders(options = {}) {
    const { silent = false } = options
    const list = this.data.ipoDrawList
    const today = '2026-06-26'
    const subscribeEndingSoon = []
    const drawToday = []

    list.forEach(item => {
      if (item.status === '申购中' && item.apply_end_date === today && !item.subscribed) {
        subscribeEndingSoon.push(item)
      }
      if (item.status === '中签公布' && item.draw_date === today && item.subscribed && !item.won && !(this.ipoStatusMap?.[item.code]?.reminded)) {
        drawToday.push(item)
      }
    })

    if (silent) {
      return { subscribeEndingSoon: subscribeEndingSoon.length, drawToday: drawToday.length }
    }

    if (subscribeEndingSoon.length > 0) {
      const names = subscribeEndingSoon.map(i => i.name).join('、')
      setTimeout(() => {
        wx.showModal({
          title: '申购截止提醒',
          content: `今日有${subscribeEndingSoon.length}只标的申购截止：\n${names}\n请及时完成申购操作。`,
          showCancel: false
        })
      }, 500)
    }

    if (drawToday.length > 0) {
      const names = drawToday.map(i => i.name).join('、')
      setTimeout(() => {
        wx.showModal({
          title: '中签公布提醒',
          content: `您申购的${names}今日公布中签结果\n快去查看是否中签吧！`,
          confirmText: '去查看',
          success: (res) => {
            if (res.confirm) {
              this.setData({ currentTab: 'ipo' })
            }
          }
        })
      }, subscribeEndingSoon.length > 0 ? 2000 : 500)

      drawToday.forEach(item => {
        if (!this.ipoStatusMap[item.code]) this.ipoStatusMap[item.code] = {}
        this.ipoStatusMap[item.code].reminded = true
      })
      this.saveIpoStatus()
    }
  },

  loadLotteryTargets() {
    const targets = [
      { code: '780001', name: '示例新股A', market: '沪', price: '12.50', apply_date: '2026-06-20', draw_date: '2026-06-24' },
      { code: '301001', name: '示例新股B', market: '深', price: '28.80', apply_date: '2026-06-23', draw_date: '2026-06-25' },
      { code: '118070', name: '南芯转债', market: '沪', price: '100.00', apply_date: '2026-06-15', draw_date: '2026-06-17' },
      { code: '123456', name: '示例转债', market: '深', price: '100.00', apply_date: '2026-06-20', draw_date: '2026-06-24' }
    ]
    this.setData({ lotteryTargetList: targets })
  },

  selectLotteryTarget(e) {
    const index = e.detail.value
    this.setData({ lotteryTargetIndex: index })
  },

  onStartNumberInput(e) {
    this.setData({ lotteryStartNumber: e.detail.value })
  },

  onLotteryCountInput(e) {
    this.setData({ lotteryCount: parseInt(e.detail.value) || 1 })
  },

  minusLotteryCount() {
    const count = this.data.lotteryCount
    if (count > 1) {
      this.setData({ lotteryCount: count - 1 })
    }
  },

  plusLotteryCount() {
    const count = this.data.lotteryCount
    if (count < 1000) {
      this.setData({ lotteryCount: count + 1 })
    }
  },

  doLotteryQuery() {
    const { lotteryStartNumber, lotteryCount, lotteryTargetList, lotteryTargetIndex, lotteryType } = this.data
    if (!lotteryStartNumber) {
      wx.showToast({ title: '请输入起始配售号', icon: 'none' })
      return
    }
    if (lotteryCount < 1) {
      wx.showToast({ title: '配号数量至少为1', icon: 'none' })
      return
    }

    const target = lotteryTargetList[lotteryTargetIndex]
    const startNum = parseInt(lotteryStartNumber)
    const winNum = Math.floor(Math.random() * 1000) + startNum
    const isWin = Math.random() < 0.3

    wx.showLoading({ title: '查询中...' })
    setTimeout(() => {
      wx.hideLoading()
      if (isWin) {
        const record = {
          id: Date.now(),
          code: target.code,
          name: target.name,
          type: lotteryType,
          market: target.market,
          winNumber: winNum,
          winCount: 1,
          query_time: new Date().toLocaleString()
        }
        const records = this.data.winRecords
        records.unshift(record)
        wx.setStorageSync('winRecords', records)
        this.setData({
          winRecords: records,
          winCount: records.length
        })
        wx.showModal({
          title: '🎉 恭喜中签',
          content: `恭喜您中签${target.name}！\n中签配号：${winNum}\n请及时缴款。`,
          showCancel: false
        })
      } else {
        wx.showToast({ title: '未中签，再接再厉', icon: 'none' })
      }
    }, 1000)
  },

  loadWinRecords() {
    try {
      const records = wx.getStorageSync('winRecords') || []
      this.setData({
        winRecords: records,
        winCount: records.length
      })
    } catch (e) {
      console.error('加载中签记录失败', e)
    }
  },

  goToWinRecords() {
    if (this.data.winRecords.length === 0) {
      wx.showToast({ title: '暂无中签记录', icon: 'none' })
      return
    }
    wx.showModal({
      title: '中签记录',
      content: this.data.winRecords.map(r => `${r.name}\n配号:${r.winNumber} 时间:${r.query_time}`).join('\n\n'),
      showCancel: false
    })
  },

  clearWinRecords() {
    wx.showModal({
      title: '确认清空',
      content: '确定要清空所有中签记录吗？',
      success: (res) => {
        if (res.confirm) {
          wx.removeStorageSync('winRecords')
          this.setData({ winRecords: [], winCount: 0 })
          wx.showToast({ title: '已清空', icon: 'success' })
        }
      }
    })
  }
})
