const app = getApp()
const { callMarketSafe } = require('../../utils/cloudApi')
const favoriteManager = require('../../utils/favoriteManager')

Page({
  data: {
    currentTab: 'all',
    sortField: '',
    sortOrder: 'desc',
    allList: [],
    upcomingList: [],
    currentList: [],
    filteredList: [],
    searchKeyword: '',
    showSearch: false,
    loading: true,
    error: null,
    isDarkMode: false,
    darkPoolList: []
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
    this.checkStateUpdates()
    this._updateTabBar(3)
  },

  _updateTabBar(index) {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().checkDarkMode()
      this.getTabBar().setData({ selected: index })
    }
  },

  checkStateUpdates() {
    const gData = app.globalData || {}
    if ((gData.favoriteVersion || 0) > (this._lastFavVer || 0)) {
      this._lastFavVer = gData.favoriteVersion
      this.refreshFavorites()
    }
    if ((gData.ipoStatusVersion || 0) > (this._lastIpoVer || 0)) {
      this._lastIpoVer = gData.ipoStatusVersion
      this.loadIpoStatus()
    }
  },

  _lastFavVer: 0,
  _lastIpoVer: 0,

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

      let filtered = this.data.allList
      if (tab === 'all') {
        filtered = this.data.allList
      } else if (tab === 'upcoming') {
        filtered = this.data.allList.filter(i => i.status === '申购中' || i.status === '待申购')
      } else if (tab === 'pending') {
        filtered = this.data.allList.filter(i => i.status === '即将上市' || i.status === '中签公布')
      } else if (tab === 'listed') {
        filtered = this.data.allList.filter(i => i.status === '已上市')
      } else if (tab === 'darkpool') {
        filtered = this.data.allList.filter(i => i.dark_pool_status === '暗盘中')
      }

      this.setData({
        currentTab: tab,
        currentList: filtered
      })
    } catch (err) {
      console.error('Switch tab failed:', err)
    }
  },

  async loadData() {
    this.setData({ loading: true, error: null })

    try {
      const [allList, upcomingList, darkPoolList] = await Promise.all([
        callMarketSafe('hkipoList'),
        callMarketSafe('hkipoUpcoming'),
        callMarketSafe('hkipoDarkPool')
      ])

      const darkPool = (darkPoolList || []).map(item => ({
        code: item.code || '--',
        name: item.name || '--',
        dark_price: item.dark_price || null,
        ipo_price: item.ipo_price || null,
        dark_change: item.dark_change || item.dark_pool_change || null
      }))

      const all = allList || []
      const upcoming = upcomingList || []

      if (all.length === 0 && upcoming.length === 0) {
        this.setData({
          allList: [],
          upcomingList: [],
          currentList: [],
          darkPoolList: darkPool,
          loading: false
        })
        return
      }

      this.setData({
        allList: this.normalizeList(all),
        upcomingList: this.normalizeList(upcoming),
        currentList: this.normalizeList(this.data.currentTab === 'all' ? all : upcoming),
        darkPoolList: darkPool,
        loading: false
      })
    } catch (err) {
      console.error('Failed to load HK IPO data:', err)
      this.setData({
        allList: [],
        upcomingList: [],
        currentList: [],
        darkPoolList: [],
        loading: false,
        error: '数据加载失败，请下拉刷新重试'
      })
    }
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
    const applyEndDate = item.apply_end_date || ''
    const oversubscription = item.oversubscription || null
    const darkPoolChange = item.dark_pool_change || null
    const darkPoolStatus = item.dark_pool_status || ''
    
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

    let oversubscriptionText = '--'
    if (typeof oversubscription === 'number') {
      oversubscriptionText = oversubscription >= 100 ? oversubscription.toFixed(0) + '倍' : oversubscription.toFixed(1) + '倍'
    }

    let darkPoolChangeText = '--'
    let darkPoolIsUp = false
    if (typeof darkPoolChange === 'number') {
      darkPoolChangeText = (darkPoolChange >= 0 ? '+' : '') + darkPoolChange.toFixed(2) + '%'
      darkPoolIsUp = darkPoolChange >= 0
    }

    return {
      ...item,
      name,
      code,
      status,
      ipo_price: ipoPrice,
      list_date: listDate,
      lot_size: lotSize,
      apply_end_date: applyEndDate,
      change_pct: changePct,
      isUp,
      showChange,
      isFavorite,
      rawChange,
      exchange: '港',
      oversubscription: oversubscription,
      oversubscriptionText,
      isHighOversubscription: oversubscription >= 100,
      dark_pool_status: darkPoolStatus,
      darkPoolChangeText,
      darkPoolIsUp,
      showDarkPool: darkPoolStatus === '暗盘中'
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
    const favCodes = favoriteManager.getCodesByType('hkipo')
    const updateList = (list) => list.map(item => ({
      ...item,
      isFavorite: favCodes.has(item.code)
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
  },

  toggleSort(e) {
    const field = e.currentTarget.dataset.field
    if (!field) return
    let newOrder = 'desc'
    if (this.data.sortField === field && this.data.sortOrder === 'desc') {
      newOrder = 'asc'
    }
    const sorted = [...this.data.currentList].sort((a, b) => {
      let va = 0, vb = 0
      if (field === 'oversubscription') {
        va = a.oversubscription || 0
        vb = b.oversubscription || 0
      } else if (field === 'darkPool') {
        va = a.dark_pool_change || 0
        vb = b.dark_pool_change || 0
      }
      return newOrder === 'desc' ? vb - va : va - vb
    })
    this.setData({
      sortField: field,
      sortOrder: newOrder,
      currentList: sorted
    })
  },

  goToDetail(e) {
    const { code } = e.currentTarget.dataset
    if (!code) return
    wx.navigateTo({
      url: `/pages/hkipoDetail/index?code=${code}`
    })
  }
})
