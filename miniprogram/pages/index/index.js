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
    sentimentFormula: {
      ratioScore: '--',
      volTrendScore: '--',
      prevVolume: '--',
      volumeChangePct: '--',
      vol5dAvg: '--',
      vol5dChangePct: '--',
    },
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
    showFormulaModal: false,
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
    isDarkMode: false,
    calendarYear: 0,
    calendarMonth: 0,
    calendarMonthLabel: '',
    calendarDays: [],
    selectedDayEvents: [],
    showDayEvents: false
  },

  quoteTimer: null,
  typingTimer: null,
  carouselInterval: 30000,
  typingSpeed: 65,

  onLoad() {
    const theme = app.getTheme ? app.getTheme() : 'light'
    // 首屏关键数据：主题 + 语录 + IPO 状态
    this.setData({ isDarkMode: theme === 'dark' })
    try { this.initQuotes() } catch(e) { console.error('initQuotes error:', e) }
    try { this.startQuoteCarousel() } catch(e) { console.error('startQuoteCarousel error:', e) }
    try { this.loadIpoStatus() } catch(e) { console.error('loadIpoStatus error:', e) }
    // 加载真实数据（失败时才使用 Mock）
    this.loadData()
    // 非关键数据延迟加载，避免阻塞首屏
    setTimeout(() => {
      try { this.initSectorData() } catch(e) { console.error('initSectorData error:', e) }
      try { this.loadLotteryTargets() } catch(e) { console.error('loadLotteryTargets error:', e) }
      try { this.loadWinRecords() } catch(e) { console.error('loadWinRecords error:', e) }
      try { this.initCalendar() } catch(e) { console.error('initCalendar error:', e) }
    }, 100)
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
    this.checkStateUpdates()
  },

  checkStateUpdates() {
    const gData = app.globalData || {}
    const currentFavVer = gData._lastFavVersion || 0
    const currentIpoVer = gData._lastIpoVersion || 0
    if ((gData.favoriteVersion || 0) > currentFavVer) {
      gData._lastFavVersion = gData.favoriteVersion
    }
    if ((gData.ipoStatusVersion || 0) > currentIpoVer) {
      gData._lastIpoVersion = gData.ipoStatusVersion
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
    const chunkSize = 3  // 每次渲染 3 个字符，减少 setData 次数
    let currentIndex = 0
    
    const typeChars = () => {
      if (currentIndex < fullText.length) {
        currentIndex = Math.min(currentIndex + chunkSize, fullText.length)
        this.setData({
          displayedQuote: fullText.slice(0, currentIndex)
        })
        this.typingTimer = setTimeout(typeChars, this.typingSpeed)
      }
    }
    
    typeChars()
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
    this.setData({ loading: true, loadError: null })
    let hasRealData = false
    try {
      // 先发起所有请求，overview 到达后立即渲染首屏
      const overviewPromise = callMarketSafe('overview')
      const signalsPromise = callMarketSafe('convertibleSignals')
      const hkipoPromise = callMarketSafe('hkipoList')
      const convertiblePromise = callMarketSafe('convertibleList')

      // overview 最关键，到达即渲染
      const overview = await overviewPromise

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

        const score = typeof sentiment.sentiment_score === 'number' ? sentiment.sentiment_score : 50
        let sentimentLevel = 'neutral'
        let sentimentText = '中性'
        if (score >= 70) {
          sentimentLevel = 'hot'
          sentimentText = '过热'
        } else if (score >= 55) {
          sentimentLevel = 'warm'
          sentimentText = '偏热'
        } else if (score <= 25) {
          sentimentLevel = 'cold'
          sentimentText = '过冷'
        } else if (score <= 35) {
          sentimentLevel = 'cool'
          sentimentText = '偏冷'
        }

        this.setData({
          sentimentLevel,
          sentimentText,
          mergedSentiment: score.toFixed(0),
          mergedSentimentPercent: score,
          sentimentFormula: {
            ratioScore: sentiment.sh_score != null ? sentiment.sh_score.toFixed(1) : '--',
            volTrendScore: sentiment.vol_trend_score != null ? sentiment.vol_trend_score.toFixed(1) : '--',
            prevVolume: sentiment.prev_volume != null ? sentiment.prev_volume.toFixed(0) : '--',
            volumeChangePct: sentiment.volume_change_pct != null ? (sentiment.volume_change_pct > 0 ? '+' : '') + sentiment.volume_change_pct.toFixed(1) : '--',
            vol5dAvg: sentiment.volume_5d_avg != null ? sentiment.volume_5d_avg.toFixed(0) : '--',
            vol5dChangePct: sentiment.volume_5d_change_pct != null ? (sentiment.volume_5d_change_pct > 0 ? '+' : '') + sentiment.volume_5d_change_pct.toFixed(1) : '--',
          },
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

        if (fundFlow && fundFlow.sectors && fundFlow.sectors.length > 0) {
          this.initRealSectorData(fundFlow)
        }

        hasRealData = true
      }

      // 其余数据到达后追加渲染
      const signals = await signalsPromise
      const hkipoList = await hkipoPromise
      const convertibleList = await convertiblePromise

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
          win_rate: item.win_rate != null ? item.win_rate : null,
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
        const today = new Date().toISOString().slice(0, 10)
        const newBonds = convertibleList.filter(b => {
          // 支持中文 key 和英文 snake_case key
          const price = b['转债价格'] || b.price
          return price && price <= 100.5 && price >= 99.5
        }).slice(0, 3).map(b => {
          const rawMarket = b['交易所'] || b.exchange || (String(b['正股代码'] || b.stock_code || '').startsWith('6') ? '沪' : '深')
          const market = rawMarket === 'sh' ? '沪' : rawMarket === 'sz' ? '深' : rawMarket
          const baseItem = {
            code: b['转债代码'] || b.bond_code,
            name: b['转债名称'] || b.bond_name,
            market: market,
            type: '可转债',
            ipo_price: 100,
            status: '申购中',
            list_date: '',
            lot_size: 10,
            apply_end_date: today,
            draw_date: '2026-06-30',
            win_rate: null,
            issue_size: null,
            industry: b['行业'] || b.industry || '--',
            pe_ratio: null
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
        console.warn('[首页] 真实数据无效，使用Mock兜底')
        this.loadMockData()
      }
    } catch (err) {
      console.error('Load data failed, using mock data:', err)
      this.loadMockData()
    } finally {
      this.setData({ loading: false }, () => {
        this.checkIpoReminders()
        this.fillCalendarEvents()
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
        sh_price: 3150.28,
        sh_change: 1.23,
        sh_change_amount: 38.25,
        sz_price: 10234.56,
        sz_change: 0.85,
        sz_change_amount: 86.32,
        cyb_price: 2156.78,
        cyb_change: 2.15,
        cyb_change_amount: 45.32,
        sentiment_score: 50,
        sh_volume: 3256,
        sz_volume: 4128,
        sh_up_count: 1820,
        sh_down_count: 1240,
        sz_up_count: 2150,
        sz_down_count: 1680
      },
      fund_flow: {
        sectors: [
          { name: '半导体', flow: 80.68, change_pct: 2.21, leader: '北京君正', leader_change: 20.00 },
          { name: '证券', flow: 57.78, change_pct: 3.06, leader: '长江证券', leader_change: 9.97 },
          { name: '元件', flow: 112.24, change_pct: 3.14, leader: '三环集团', leader_change: 12.64 },
          { name: '白酒', flow: 6.09, change_pct: 1.64, leader: '酒鬼酒', leader_change: 7.20 },
          { name: '银行', flow: -5.45, change_pct: -0.23, leader: '招商银行', leader_change: 1.20 },
          { name: '医药', flow: -12.34, change_pct: -0.85, leader: '恒瑞医药', leader_change: 2.10 },
          { name: '新能源', flow: -25.67, change_pct: -1.25, leader: '宁德时代', leader_change: -0.80 },
          { name: '消费', flow: -8.90, change_pct: -0.45, leader: '贵州茅台', leader_change: 0.50 },
          { name: '军工', flow: 3.89, change_pct: 0.80, leader: '中航沈飞', leader_change: 3.20 },
          { name: '地产', flow: -2.67, change_pct: -0.60, leader: '万科A', leader_change: -1.20 },
        ],
        total_count: 10
      }
    }

    const cb = mockOverview.convertible_bond
    const lof = mockOverview.lof_fund
    const ipo = mockOverview.hk_ipo
    const sentiment = mockOverview.market_sentiment
    const fundFlow = mockOverview.fund_flow

    const score = typeof sentiment.sentiment_score === 'number' ? sentiment.sentiment_score : 50
    let sentimentLevel = 'neutral'
    let sentimentText = '中性'
    if (score >= 70) {
      sentimentLevel = 'hot'; sentimentText = '过热'
    } else if (score >= 55) {
      sentimentLevel = 'warm'; sentimentText = '偏热'
    } else if (score <= 25) {
      sentimentLevel = 'cold'; sentimentText = '过冷'
    } else if (score <= 35) {
      sentimentLevel = 'cool'; sentimentText = '偏冷'
    }

    const mockSignals = {
      discount: [
        { bond_name: '南芯转债', price: 100.00, premium_rate: -18.66 },
        { bond_name: '汇车退债', price: 55.59, premium_rate: -7.35 },
        { bond_name: '银微转债', price: 148.44, premium_rate: -0.76 },
        { bond_name: '鹤21转债', price: 152.74, premium_rate: -0.39 },
        { bond_name: '华亚转债', price: 264.90, premium_rate: -0.31 }
      ],
      double_low: [
        { bond_name: '汇车退债', price: 55.59, premium_rate: -7.35 },
        { bond_name: '南芯转债', price: 100.00, premium_rate: -18.66 },
        { bond_name: '金帝转债', price: 100.00, premium_rate: 1.39 },
        { bond_name: '春风转债', price: 100.00, premium_rate: 7.92 },
        { bond_name: '弘亚转债', price: 116.00, premium_rate: 8.15 }
      ],
      force_redeem: [
        { bond_name: '艾迪转债', price: 129.93, premium_rate: -0.12 },
        { bond_name: '镇洋转债', price: 130.30, premium_rate: 0.48 },
        { bond_name: '航新转债', price: 129.40, premium_rate: 2.28 },
        { bond_name: '重银转债', price: 127.61, premium_rate: 7.66 },
        { bond_name: '常银转债', price: 129.52, premium_rate: 6.08 }
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

    this.signalsData = this.formatSignals(mockSignals)
    this.updateCurrentSignals()

    const drawList = this.mergeIpoStatus(mockIpo)

    this.setData({
      sentimentLevel,
      sentimentText,
      mergedSentiment: score.toFixed(0),
      mergedSentimentPercent: score,
      sentimentFormula: {
        ratioScore: sentiment.sh_score != null ? sentiment.sh_score.toFixed(1) : '--',
        volTrendScore: sentiment.vol_trend_score != null ? sentiment.vol_trend_score.toFixed(1) : '--',
        prevVolume: sentiment.prev_volume != null ? sentiment.prev_volume.toFixed(0) : '--',
        volumeChangePct: sentiment.volume_change_pct != null ? (sentiment.volume_change_pct > 0 ? '+' : '') + sentiment.volume_change_pct.toFixed(1) : '--',
        vol5dAvg: sentiment.volume_5d_avg != null ? sentiment.volume_5d_avg.toFixed(0) : '--',
        vol5dChangePct: sentiment.volume_5d_change_pct != null ? (sentiment.volume_5d_change_pct > 0 ? '+' : '') + sentiment.volume_5d_change_pct.toFixed(1) : '--',
      },
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
      const bondName = item.bond_name || '--'
      const bondCode = item.bond_code || '--'
      const priceVal = item.price
      const price = typeof priceVal === 'number' ? priceVal.toFixed(2) : (item.price || '--')
      const premiumVal = item.premium_rate
      const premiumNum = typeof premiumVal === 'number' ? premiumVal : (item.premiumNum || 0)
      const premiumRate = typeof premiumVal === 'number' ? premiumVal.toFixed(2) + '%' : (item.premiumRate || '--')
      const dlVal = item.double_low
      const doubleLow = typeof dlVal === 'number' ? dlVal.toFixed(1) : (item.doubleLow || '--')
      const stockCode = String(item.stock_code || '')

      let exchange = ''
      if (item.exchange) {
        exchange = item.exchange === 'sh' ? '沪' : item.exchange === 'sz' ? '深' : item.exchange === 'bj' ? '京' : item.exchange
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

  openFormulaModal() {
    this.setData({ showFormulaModal: true })
  },

  closeFormulaModal() {
    this.setData({ showFormulaModal: false })
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

  initRealSectorData(fundFlow) {
    const sectors = fundFlow.sectors || []
    if (sectors.length === 0) return

    const maxAbs = Math.max(...sectors.map(s => Math.abs(s.flow)))
    const sectorFlowList = sectors.map(s => ({
      name: s.name,
      flow: s.flow,
      flowText: (s.flow > 0 ? '+' : '') + s.flow.toFixed(2),
      percent: Math.round(Math.abs(s.flow) / maxAbs * 100),
      trend: s.flow >= 0 ? 'positive' : 'negative',
      change_pct: s.change_pct || 0,
      leader: s.leader || '',
      leader_change: s.leader_change || 0,
    }))

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
      return timeline
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
    app.globalData.ipoStatusVersion = (app.globalData.ipoStatusVersion || 0) + 1

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
    app.globalData.ipoStatusVersion = (app.globalData.ipoStatusVersion || 0) + 1

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
    const today = new Date().toISOString().slice(0, 10)
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

  initCalendar() {
    const now = new Date()
    this.generateCalendar(now.getFullYear(), now.getMonth() + 1)
  },

  generateCalendar(year, month) {
    const today = new Date()
    const todayStr = today.toISOString().slice(0, 10)
    const firstDay = new Date(year, month - 1, 1)
    const lastDay = new Date(year, month, 0)
    const startWeekday = firstDay.getDay()
    const totalDays = lastDay.getDate()

    const blanks = []
    for (let i = 0; i < startWeekday; i++) {
      blanks.push({ day: 0, date: '', events: [], isEmpty: true })
    }

    const days = []
    for (let d = 1; d <= totalDays; d++) {
      const dateStr = year + '-' + String(month).padStart(2, '0') + '-' + String(d).padStart(2, '0')
      days.push({
        day: d,
        date: dateStr,
        events: [],
        isEmpty: false,
        isToday: dateStr === todayStr,
        isActive: false
      })
    }

    const calendarDays = [...blanks, ...days]
    this.setData({
      calendarYear: year,
      calendarMonth: month,
      calendarMonthLabel: year + '年' + month + '月',
      calendarDays
    })

    this.fillCalendarEvents()
  },

  fillCalendarEvents() {
    const list = this.data.ipoDrawList || []
    const days = [...this.data.calendarDays]

    days.forEach(d => {
      if (d.isEmpty) return
      d.events = []
    })

    list.forEach(item => {
      if (item.apply_end_date) {
        const dayObj = days.find(d => d.date === item.apply_end_date)
        if (dayObj) {
          dayObj.events.push({ type: 'subscribe', name: item.name, code: item.code })
        }
      }
      if (item.draw_date) {
        const dayObj = days.find(d => d.date === item.draw_date)
        if (dayObj) {
          dayObj.events.push({ type: 'draw', name: item.name, code: item.code })
        }
      }
      if (item.list_date) {
        const dayObj = days.find(d => d.date === item.list_date)
        if (dayObj) {
          dayObj.events.push({ type: 'list', name: item.name, code: item.code })
        }
      }
    })

    days.forEach(d => {
      if (d.isEmpty) return
      d.hasEvents = d.events.length > 0
      d.markerTypes = [...new Set(d.events.map(e => e.type))]
    })

    this.setData({ calendarDays: days })
  },

  prevMonth() {
    let { calendarYear, calendarMonth } = this.data
    calendarMonth--
    if (calendarMonth < 1) {
      calendarMonth = 12
      calendarYear--
    }
    this.generateCalendar(calendarYear, calendarMonth)
  },

  nextMonth() {
    let { calendarYear, calendarMonth } = this.data
    calendarMonth++
    if (calendarMonth > 12) {
      calendarMonth = 1
      calendarYear++
    }
    this.generateCalendar(calendarYear, calendarMonth)
  },

  onDayTap(e) {
    const { index } = e.currentTarget.dataset
    const day = this.data.calendarDays[index]
    if (!day || day.isEmpty || !day.hasEvents) return
    this.setData({
      selectedDayEvents: day.events,
      showDayEvents: true
    })
  },

  closeDayEvents() {
    this.setData({ showDayEvents: false, selectedDayEvents: [] })
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
