const app = getApp()
const { callMarketSafe } = require('../../utils/cloudApi')
const favoriteManager = require('../../utils/favoriteManager')

Page({
  data: {
    code: '',
    detail: null,
    loading: true,
    isFavorite: false,
    subscribed: false,
    won: false,
    isDarkMode: false
  },

  onLoad(options) {
    const { code } = options
    if (!code) {
      wx.showToast({ title: '参数错误', icon: 'none' })
      return
    }
    const theme = app.getTheme ? app.getTheme() : 'light'
    this.setData({ code, isDarkMode: theme === 'dark' })
    this.loadData(code)
    this.loadIpoStatus(code)
  },

  onShow() {
    const theme = app.getTheme ? app.getTheme() : 'light'
    this.setData({ isDarkMode: theme === 'dark' })
    this.checkFavorite()
  },

  onShareAppMessage() {
    const { detail } = this.data
    return {
      title: detail ? detail.name + ' - 港股打新' : '港股打新',
      path: '/pages/hkipoDetail/index?code=' + this.data.code
    }
  },

  async loadData(code) {
    this.setData({ loading: true })
    try {
      const data = await callMarketSafe('hkipoDetail', { code })
      if (data) {
        this.setData({
          detail: this.formatDetail(data),
          loading: false
        })
      } else {
        this.setData({
          detail: null,
          loading: false
        })
      }
    } catch (err) {
      console.error('Failed to load HK IPO detail:', err)
      this.setData({
        detail: null,
        loading: false
      })
    }
  },

  formatDetail(item) {
    const name = item.name || '--'
    const code = item.code || '--'
    const status = item.status || '--'
    const industry = item.industry || '--'
    const ipoPrice = item.ipo_price || '--'
    const lotSize = item.lot_size || '--'
    const issueSize = item.issue_size || '--'
    const peRatio = item.pe_ratio || '--'
    const listDate = item.list_date || '--'
    const applyEndDate = item.apply_end_date || '--'

    const oversubscription = item.oversubscription || null
    const marginTotal = item.margin_total || null
    const publicOversub = item.public_oversubscription || null
    const intlOversub = item.international_oversubscription || null

    const winRate = item.win_rate || null
    const applyMultiple = item.apply_multiple || null
    const clawbackRatio = item.clawback_ratio || null

    const openPrice = item.open_price || null
    const closePrice = item.close_price || null
    const changePct = item.change_pct || null
    const totalChange = item.total_change || null

    const darkPrice = item.dark_price || null
    const darkChange = item.dark_change || item.dark_pool_change || null
    const darkTime = item.dark_time || null

    const marginList = item.margin_list || []
    const marginTotalAmount = marginList.reduce((sum, m) => sum + (m.amount || 0), 0)
    const marginMultiple = item.margin_multiple || (marginTotalAmount > 0 && ipoPrice && lotSize ? (marginTotalAmount / (ipoPrice * lotSize / 10000)).toFixed(1) : null)

    const timeline = this.buildTimeline(item)

    return {
      name,
      code,
      status,
      industry,
      ipoPrice,
      lotSize,
      issueSize,
      peRatio,
      listDate,
      applyEndDate,
      oversubscription,
      oversubscriptionText: oversubscription ? (oversubscription >= 100 ? oversubscription.toFixed(0) + '倍' : oversubscription.toFixed(1) + '倍') : '--',
      isHighOversubscription: oversubscription >= 100,
      marginTotal: marginTotal ? marginTotal.toFixed(2) + '亿' : '--',
      publicOversub: publicOversub ? publicOversub.toFixed(1) + '倍' : '--',
      intlOversub: intlOversub ? intlOversub.toFixed(1) + '倍' : '--',
      winRate: winRate ? winRate.toFixed(2) + '%' : '--',
      applyMultiple: applyMultiple ? applyMultiple.toFixed(1) + '倍' : '--',
      clawbackRatio: clawbackRatio ? clawbackRatio.toFixed(1) + '%' : '--',
      openPrice: openPrice ? openPrice.toFixed(2) : '--',
      closePrice: closePrice ? closePrice.toFixed(2) : '--',
      changePct: changePct != null ? (changePct >= 0 ? '+' : '') + changePct.toFixed(2) + '%' : '--',
      changePctNum: changePct,
      totalChange: totalChange != null ? (totalChange >= 0 ? '+' : '') + totalChange.toFixed(2) + '%' : '--',
      totalChangeNum: totalChange,
      darkPrice: darkPrice ? darkPrice.toFixed(2) : '--',
      darkChange: darkChange != null ? (darkChange >= 0 ? '+' : '') + darkChange.toFixed(2) + '%' : '--',
      darkChangeNum: darkChange,
      darkTime: darkTime || '--',
      marginList: marginList.sort((a, b) => (b.amount || 0) - (a.amount || 0)),
      marginTotalAmount: marginTotalAmount ? marginTotalAmount.toFixed(2) + '亿' : '--',
      marginMultiple: marginMultiple ? marginMultiple + '倍' : '--',
      timeline,
      hasTimeline: timeline.length > 0,
      currentTimelineIdx: timeline.findIndex(t => t.current),
      hasMargin: marginList.length > 0,
      hasDark: darkPrice != null,
      hasOversub: oversubscription != null,
      hasWinRate: winRate != null,
      hasListPerf: openPrice != null
    }
  },

  buildTimeline(item) {
    const steps = [
      { key: 'submit_date', step: '递表' },
      { key: 'hearing_date', step: '聆讯通过' },
      { key: 'offer_start_date', step: '招股开始' },
      { key: 'apply_end_date', step: '招股截止' },
      { key: 'draw_date', step: '公布中签' },
      { key: 'list_date', step: '上市' }
    ]

    const timeline = []
    const today = new Date().toISOString().slice(0, 10)
    let foundCurrent = false

    steps.forEach(s => {
      const date = item[s.key] || ''
      if (date) {
        const isPast = date < today
        const isCurrent = !isPast && !foundCurrent
        if (isCurrent) foundCurrent = true
        timeline.push({
          step: s.step,
          date,
          done: isPast,
          current: isCurrent && !isPast
        })
      }
    })

    return timeline
  },

  checkFavorite() {
    const isFav = favoriteManager.isFavorite(this.data.code, 'hkipo')
    this.setData({ isFavorite: isFav })
  },

  toggleFavorite() {
    const { detail, code } = this.data
    const isNowFav = favoriteManager.toggle({
      code,
      name: detail ? detail.name : code,
      price: detail ? detail.ipoPrice : null,
      changePct: detail ? detail.changePctNum : null
    }, 'hkipo')
    this.setData({ isFavorite: isNowFav })
    wx.showToast({
      title: isNowFav ? '已添加自选' : '已取消自选',
      icon: 'success',
      duration: 1000
    })
  },

  loadIpoStatus(code) {
    try {
      const statusMap = wx.getStorageSync('ipoStatusMap') || {}
      const status = statusMap[code] || {}
      this.setData({
        subscribed: status.subscribed || false,
        won: status.won || false
      })
    } catch (e) {
      console.error('加载申购状态失败', e)
    }
  },

  toggleSubscribe() {
    const newSubscribed = !this.data.subscribed
    this.setData({ subscribed: newSubscribed })
    try {
      const statusMap = wx.getStorageSync('ipoStatusMap') || {}
      if (!statusMap[this.data.code]) statusMap[this.data.code] = {}
      statusMap[this.data.code].subscribed = newSubscribed
      wx.setStorageSync('ipoStatusMap', statusMap)
      app.globalData.ipoStatusVersion = (app.globalData.ipoStatusVersion || 0) + 1
    } catch (e) {}
    wx.showToast({
      title: newSubscribed ? '已标记为已申购' : '已取消申购',
      icon: newSubscribed ? 'success' : 'none'
    })
  },

  toggleWin() {
    const newWon = !this.data.won
    this.setData({ won: newWon })
    try {
      const statusMap = wx.getStorageSync('ipoStatusMap') || {}
      if (!statusMap[this.data.code]) statusMap[this.data.code] = {}
      statusMap[this.data.code].won = newWon
      wx.setStorageSync('ipoStatusMap', statusMap)
      app.globalData.ipoStatusVersion = (app.globalData.ipoStatusVersion || 0) + 1
    } catch (e) {}
    if (newWon) {
      wx.showModal({
        title: '恭喜中签',
        content: '恭喜您中签' + (this.data.detail ? this.data.detail.name : '') + '！请及时关注缴款。',
        showCancel: false
      })
    } else {
      wx.showToast({ title: '已取消中签标记', icon: 'none' })
    }
  },

  goBack() {
    wx.navigateBack()
  }
})
