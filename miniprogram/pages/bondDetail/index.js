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

      if (!data) {
        const app = getApp()
        if (app.globalData.bondListCache) {
          data = app.globalData.bondListCache.find(b => b.bondCode === this.data.bondCode)
        }
      }

      if (data) {
        this.setData({
          bondInfo: this.formatBondInfo(data),
          loading: false
        })
      } else {
        this.setData({
          bondInfo: this.getMockDetail(),
          loading: false
        })
      }
    } catch (err) {
      console.error('加载转债详情失败:', err)
      this.setData({
        bondInfo: this.getMockDetail(),
        loading: false
      })
    }
  },

  getMockDetail() {
    return {
      bondName: '南芯转债',
      bondCode: '118070',
      stockName: '南芯科技',
      stockCode: '688484',
      exchange: '沪',
      price: 100.00,
      conversionValue: 122.95,
      premiumRate: -18.66,
      doubleLow: 81.34,
      pureBondValue: 95.50,
      conversionPrice: 83.28,
      conversionRatio: 12.008,
      issueSize: 10.00,
      remainingSize: 9.85,
      listingDate: '2026-05-20',
      maturityDate: '2030-05-20',
      remainingYears: 4.25,
      couponRate: '第一年0.30%，第二年0.50%，第三年1.00%，第四年1.80%，第五年2.50%，第六年3.00%',
      putPrice: 108.00,
      callPrice: 130.00,
      downRevisePrice: 58.30,
      creditRating: 'A+',
      guarantee: '连带责任保证',
      issuer: '上海南芯半导体科技股份有限公司',
      industry: '半导体',
      ytm: '3.25%',
      turnoverRate: 15.6
    }
  },

  formatBondInfo(data) {
    const price = data.price || data['转债价格'] || 0
    const conversionValue = data.conversionValue || data['转股价值'] || 0
    const premiumRate = data.premiumRate || data['转股溢价率'] || 0

    return {
      bondName: data.bondName || data['转债名称'] || '--',
      bondCode: data.bondCode || data['转债代码'] || '--',
      stockName: data.stockName || data['正股名称'] || '--',
      stockCode: data.stockCode || data['正股代码'] || '--',
      exchange: data.exchange || '沪',
      price: formatNumber(price),
      conversionValue: formatNumber(conversionValue),
      premiumRate: formatPercent(premiumRate),
      premiumValue: premiumRate,
      premiumClass: premiumRate < 0 ? 'negative' : '',
      doubleLow: formatNumber(data.doubleLow || data['双低'] || 0, 1),
      pureBondValue: formatNumber(data.pureBondValue || data['纯债价值'] || 0),
      conversionPrice: formatNumber(data.conversionPrice || data['转股价'] || 0),
      conversionRatio: formatNumber(data.conversionRatio || data['转股比例'] || 0, 3),
      issueSize: formatNumber(data.issueSize || data['发行规模'] || 0) + '亿',
      remainingSize: formatNumber(data.remainingSize || data['剩余规模'] || 0) + '亿',
      listingDate: data.listingDate || data['上市日期'] || '--',
      maturityDate: data.maturityDate || data['到期日期'] || '--',
      remainingYears: data.remainingYears ? data.remainingYears.toFixed(2) + '年' : '--',
      couponRate: data.couponRate || data['票面利率'] || '--',
      putPrice: data.putPrice ? formatNumber(data.putPrice) : '--',
      callPrice: data.callPrice ? formatNumber(data.callPrice) : '--',
      downRevisePrice: data.downRevisePrice ? formatNumber(data.downRevisePrice) : '--',
      creditRating: data.creditRating || data['信用评级'] || '--',
      guarantee: data.guarantee || data['担保方式'] || '--',
      issuer: data.issuer || data['发行人'] || '--',
      industry: data.industry || data['所属行业'] || '--',
      ytm: data.ytm || data['到期收益率'] || '--',
      turnoverRate: data.turnoverRate ? formatPercent(data.turnoverRate) : '--'
    }
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
