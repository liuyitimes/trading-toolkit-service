const app = getApp()
const { callMarketSafe } = require('../../utils/cloudApi')
const favoriteManager = require('../../utils/favoriteManager')

Page({
  data: {
    currentTab: 'all',
    allList: [],
    upcomingList: [],
    currentList: [],
    filteredList: [],
    searchKeyword: '',
    showSearch: false,
    loading: true,
    error: null,
    isDarkMode: false
  },

  onLoad() {
    const theme = app.getTheme ? app.getTheme() : 'light'
    this.setData({ isDarkMode: theme === 'dark' })
    this.loadData()
  },

  onShow() {
    const theme = app.getTheme ? app.getTheme() : 'light'
    this.setData({ isDarkMode: theme === 'dark' })
    this.refreshFavorites()
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().checkDarkMode()
      this.getTabBar().setData({ selected: 3 })
    }
  },

  onPullDownRefresh() {
    this.setData({ error: null })
    this.loadData().then(() => {
      wx.stopPullDownRefresh()
    })
  },

  switchTab(e) {
    try {
      const tab = e.currentTarget.dataset.tab
      if (!tab) {
        console.warn('Invalid tab value')
        return
      }

      this.setData({
        currentTab: tab,
        currentList: tab === 'all' ? this.data.allList : this.data.upcomingList
      })
    } catch (err) {
      console.error('Switch tab failed:', err)
    }
  },

  async loadData() {
    this.setData({ loading: true, error: null })

    try {
      const [allList, upcomingList] = await Promise.all([
        callMarketSafe('hkipoList'),
        callMarketSafe('hkipoUpcoming')
      ])

      const all = allList || []
      const upcoming = upcomingList || []

      if (all.length === 0 && upcoming.length === 0) {
        const mockData = this.getMockData()
        const formatted = this.normalizeList(mockData)
        this.setData({
          allList: formatted,
          upcomingList: this.normalizeList(mockData.filter(i => i.status !== '已上市')),
          currentList: formatted,
          loading: false
        })
        return
      }

      this.setData({
        allList: this.normalizeList(all),
        upcomingList: this.normalizeList(upcoming),
        currentList: this.normalizeList(this.data.currentTab === 'all' ? all : upcoming),
        loading: false
      })
    } catch (err) {
      console.error('Failed to load HK IPO data:', err)
      const mockData = this.getMockData()
      const formatted = this.normalizeList(mockData)
      this.setData({
        allList: formatted,
        upcomingList: this.normalizeList(mockData.filter(i => i.status !== '已上市')),
        currentList: formatted,
        loading: false
      })
    }
  },

  getMockData() {
    return [
      { name: '美的集团', code: 'HK03690', status: '已上市', ipo_price: 52.00, list_date: '2026-06-18', lot_size: 100, change_pct: 5.23 },
      { name: '小鹏汽车', code: 'HK09868', status: '申购中', ipo_price: 68.50, lot_size: 100 },
      { name: '京东健康', code: 'HK06618', status: '即将上市', ipo_price: 72.80, list_date: '2026-06-25', lot_size: 100 },
      { name: '哔哩哔哩', code: 'HK09626', status: '已上市', ipo_price: 988.00, list_date: '2026-06-10', lot_size: 20, change_pct: -2.15 },
      { name: '蚂蚁集团', code: 'HK06688', status: '申购中', ipo_price: 88.00, lot_size: 50 },
      { name: '海底捞', code: 'HK06862', status: '已上市', ipo_price: 28.60, list_date: '2026-05-20', lot_size: 1000, change_pct: 1.78 },
      { name: '腾讯音乐', code: 'HK01698', status: '即将上市', ipo_price: 28.00, list_date: '2026-06-28', lot_size: 100 },
      { name: '快手科技', code: 'HK01024', status: '已上市', ipo_price: 68.35, list_date: '2026-04-15', lot_size: 100, change_pct: 0.45 }
    ]
  },

  normalizeList(list) {
    if (!Array.isArray(list)) {
      return []
    }

    return list.map(item => this.formatIpoItem(item))
  },

  formatIpoItem(item) {
    const name = item.name || '--'
    const code = item.code || '--'
    const status = item.status || '--'
    const ipoPrice = item.ipo_price || '--'
    const listDate = item.list_date || ''
    const lotSize = item.lot_size || '--'
    
    let changePct = '--'
    let isUp = true
    let showChange = false
    let rawChange = 0
    
    if (typeof item.change_pct === 'number') {
      changePct = (item.change_pct >= 0 ? '+' : '') + item.change_pct.toFixed(2) + '%'
      isUp = item.change_pct >= 0
      showChange = true
      rawChange = item.change_pct
    }

    const isFavorite = favoriteManager.isFavorite(code, 'hkipo')

    return {
      ...item,
      name,
      code,
      status,
      ipo_price: ipoPrice,
      list_date: listDate,
      lot_size: lotSize,
      change_pct: changePct,
      isUp,
      showChange,
      isFavorite,
      rawChange,
      exchange: '港'
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
      item.code.toLowerCase().includes(keyword)
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
      price: item.ipo_price,
      changePct: item.rawChange
    }, 'hkipo')

    const key = `${listKey}[${index}].isFavorite`
    this.setData({ [key]: isNowFav })

    wx.showToast({
      title: isNowFav ? '已添加自选' : '已取消自选',
      icon: 'success',
      duration: 1000
    })
  },

  refreshFavorites() {
    const updateList = (list) => list.map(item => ({
      ...item,
      isFavorite: favoriteManager.isFavorite(item.code, 'hkipo')
    }))

    const allList = updateList(this.data.allList)
    const upcomingList = updateList(this.data.upcomingList)
    const currentList = this.data.currentTab === 'all' ? allList : upcomingList
    const filteredList = this.data.showSearch
      ? currentList.filter(item =>
          item.name.toLowerCase().includes(this.data.searchKeyword.toLowerCase()) ||
          item.code.toLowerCase().includes(this.data.searchKeyword)
        )
      : currentList

    this.setData({
      allList,
      upcomingList,
      currentList,
      filteredList
    })
  }
})
