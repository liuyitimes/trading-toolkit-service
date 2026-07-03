const app = getApp()
const { callMarketSafe } = require('../../utils/cloudApi')
const favoriteManager = require('../../utils/favoriteManager')
const { formatNumber, formatPercent, formatMoney } = require('../../utils/format')

Page({
  data: {
    bondCode: '',
    bondInfo: null,
    loading: true,
    isFavorite: false,
    klineData: []
  },

  onLoad(options) {
    const { code } = options
    this.setData({ bondCode: code })
    this.loadBondDetail()
    this.checkFavorite()
  },

  onShareAppMessage() {
    const { bondInfo } = this.data
    return {
      title: bondInfo ? `${bondInfo.bondName} - 旺财百宝箱` : '旺财百宝箱',
      path: `/pages/bondDetail/index?code=${this.data.bondCode}`
    }
  },

  async loadBondDetail() {
    this.setData({ loading: true })
    try {
      let data = await callMarketSafe('convertibleDetail', { code: this.data.bondCode })

      if (!data || Object.keys(data).length === 0) {
        // fallback 到模拟数据
        data = this.getMockDetail()
      }

      this.setData({
        bondInfo: this.formatBondInfo(data),
        loading: false
      })
    } catch (err) {
      console.error('加载转债详情失败:', err)
      this.setData({
        bondInfo: this.formatBondInfo(this.getMockDetail()),
        loading: false
      })
    }
  },

  getMockDetail() {
    return {
      bond_code: '118070',
      bond_name: '南芯转债',
      stock_code: '688484',
      stock_name: '南芯科技',
      exchange: 'sh',
      price: 100.00,
      conversion_value: 122.95,
      premium_rate: -18.66,
      double_low: 81.34,
      pure_bond_value: 95.50,
      conversion_price: 83.28,
      rating: 'A+',
      maturity_date: '2030-05-20',
      listing_date: '2026-05-20',
      issue_size: 10.00,
      remaining_size: 9.85,
      issuer: '上海南芯半导体科技股份有限公司',
      industry: '半导体',
      ytm: 3.25,
      turnover_rate: 15.6
    }
  },

  _val(data, keys, fallback = '--') {
    for (const k of keys) {
      const v = data[k]
      if (v !== undefined && v !== null && v !== '') return v
    }
    return fallback
  },

  formatBondInfo(data) {
    const price = parseFloat(this._val(data, ['price', '转债价格', 0]))
    const premiumRate = parseFloat(this._val(data, ['premium_rate', '转股溢价率', 0]))
    const listingDate = this._val(data, ['listing_date', 'listingDate', 'list_date', '上市日期', ''])
    const maturityDate = this._val(data, ['maturity_date', 'maturityDate', '到期日期', ''])

    let remainingYears = '--'
    if (listingDate && listingDate !== '--' && listingDate !== '') {
      try {
        const listY = parseInt(listingDate.slice(0, 4))
        remainingYears = (listY + 6 - new Date().getFullYear()).toFixed(2) + '年'
      } catch (e) {}
    }

    const timeline = this.buildTimeline(data, listingDate)

    return {
      bondName: this._val(data, ['bond_name', 'bondName', '转债名称', '债券名称']),
      bondCode: this._val(data, ['bond_code', 'bondCode', '转债代码', '债券代码']),
      stockName: this._val(data, ['stock_name', 'stockName', '正股名称']),
      stockCode: this._val(data, ['stock_code', 'stockCode', '正股代码']),
      exchange: this._val(data, ['exchange', '交易所'], 'sh'),
      price: formatNumber(price),
      conversionValue: formatNumber(parseFloat(this._val(data, ['conversion_value', 'conversionValue', '转股价值', 0]))),
      premiumRate: formatPercent(premiumRate),
      premiumValue: premiumRate,
      premiumClass: premiumRate < 0 ? 'negative' : '',
      doubleLow: formatNumber(parseFloat(this._val(data, ['double_low', 'doubleLow', '双低', 0])), 1),
      pureBondValue: formatNumber(parseFloat(this._val(data, ['pure_bond_value', 'pureBondValue', '纯债价值', 0]))),
      conversionPrice: formatNumber(parseFloat(this._val(data, ['conversion_price', 'conversionPrice', '转股价', 0]))),
      issueSize: this._val(data, ['issue_size', 'issueSize', '发行规模', 0]) + '亿',
      remainingSize: this._val(data, ['remaining_size', 'remainingSize', '剩余规模', 0]) + '亿',
      listingDate: listingDate,
      maturityDate: maturityDate,
      remainingYears: remainingYears,
      couponRate: this._val(data, ['coupon_rate', 'couponRate', '票面利率', '']),
      creditRating: this._val(data, ['credit_rating', 'creditRating', 'rating', '评级', '信用评级']),
      issuer: this._val(data, ['issuer', '发行人']),
      industry: this._val(data, ['industry', '所属行业']),
      ytm: this._val(data, ['ytm', '到期收益率']),
      turnoverRate: this._val(data, ['turnover_rate', 'turnoverRate', '换手率']),
      // 时间线
      timeline,
      hasTimeline: timeline.length > 0,
      currentTimelineIdx: timeline.findIndex(t => t.current)
    }
  },

  buildTimeline(data, listingDate) {
    const today = new Date().toISOString().slice(0, 10)
    const steps = [
      { key: ['register_date', 'plan_date', 'board_date'], label: '董事会预案' },
      { key: ['approve_date', 'approval_date', 'csrc_date'], label: '证监会核准' },
      { key: ['equity_date', 'register_date'], label: '股权登记日' },
      { key: ['apply_date', 'subscribe_date', 'apply_start_date'], label: '申购日' },
      { key: ['draw_date', 'lottery_date'], label: '中签公布' },
      { key: ['list_date', 'listing_date', 'listingDate'], label: '上市' }
    ]

    const timeline = []
    let foundCurrent = false

    steps.forEach(s => {
      const date = this._val(data, s.key, '')
      if (date && date !== '--' && date !== '') {
        const isPast = date < today
        const isCurrent = !isPast && !foundCurrent
        if (isCurrent) foundCurrent = true
        timeline.push({
          step: s.label,
          date,
          done: isPast,
          current: isCurrent && !isPast
        })
      }
    })

    // 如果有上市日期但没有前面的日期，补一个简化版时间线
    if (timeline.length === 0 && listingDate && listingDate !== '--') {
      const isPast = listingDate < today
      timeline.push({
        step: '上市',
        date: listingDate,
        done: isPast,
        current: isPast
      })
    }

    return timeline
  },

  checkFavorite() {
    const isFav = favoriteManager.isFavorite(this.data.bondCode, 'bond')
    this.setData({ isFavorite: isFav })
  },

  toggleFavorite() {
    const { bondInfo, bondCode } = this.data
    if (!bondInfo) return

    const item = {
      code: bondCode,
      name: bondInfo.bondName,
      price: bondInfo.price,
      premiumRate: bondInfo.premiumValue
    }

    const isNowFav = favoriteManager.toggle(item, 'bond')
    this.setData({ isFavorite: isNowFav })

    wx.showToast({
      title: isNowFav ? '已添加自选' : '已取消自选',
      icon: 'success'
    })
  },

  copyCode() {
    wx.setClipboardData({
      data: this.data.bondCode,
      success: () => {
        wx.showToast({ title: '代码已复制', icon: 'success' })
      }
    })
  },

  goToStock() {
    const { bondInfo } = this.data
    if (!bondInfo || !bondInfo.stockCode) return
    wx.showToast({
      title: '正股详情开发中',
      icon: 'none'
    })
  }
})
