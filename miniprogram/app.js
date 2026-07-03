const config = require('./config')

App({
  globalData: {
    cloudRunUrl: '',
    cloudEnv: config.cloudEnv || 'prod-1g3p1',
    isConfigured: false,
    theme: 'light',
    defaultTab: 'index'
  },

  onLaunch() {
    this.initCloud()
    this.loadCloudRunUrl()
    this.loadUserSettings()
    this.updateTabBarStyle(this.globalData.theme)
    this.navigateToDefaultTab()
  },

  navigateToDefaultTab() {
    const defaultTab = this.globalData.defaultTab
    if (defaultTab && defaultTab !== 'index') {
      const tabMap = {
        'convertible': '/pages/convertible/index',
        'lof': '/pages/lof/index',
        'hkipo': '/pages/hkipo/index'
      }
      const url = tabMap[defaultTab]
      if (url) {
        setTimeout(() => {
          wx.reLaunch({ url })
        }, 100)
      }
    }
  },

  initCloud() {
    if (!wx.cloud) {
      console.error('请使用 2.2.3 或以上的基础库以使用云能力')
      return
    }
    try {
      wx.cloud.init({
        env: config.cloudEnv || 'prod-1g3p1',
        traceUser: true
      })
      this.globalData.isConfigured = true
      console.log('云开发初始化成功')
    } catch (err) {
      console.error('云开发初始化失败:', err)
    }
  },

  loadCloudRunUrl() {
    try {
      const savedUrl = wx.getStorageSync('cloudRunUrl')
      if (savedUrl) {
        this.globalData.cloudRunUrl = savedUrl
      } else {
        this.globalData.cloudRunUrl = config.development.baseUrl
      }
    } catch (err) {
      console.error('加载云托管地址失败:', err)
      this.globalData.cloudRunUrl = config.development.baseUrl
    }
  },

  setCloudRunUrl(url) {
    try {
      this.globalData.cloudRunUrl = url || ''
      if (url) {
        wx.setStorageSync('cloudRunUrl', url)
      } else {
        wx.removeStorageSync('cloudRunUrl')
      }
      return true
    } catch (err) {
      console.error('保存云托管地址失败:', err)
      return false
    }
  },

  getCloudRunUrl() {
    return this.globalData.cloudRunUrl || config.development.baseUrl
  },

  loadUserSettings() {
    try {
      const savedTheme = wx.getStorageSync('appTheme')
      const savedDefaultTab = wx.getStorageSync('defaultTab')
      if (savedTheme) {
        this.globalData.theme = savedTheme
      }
      if (savedDefaultTab) {
        this.globalData.defaultTab = savedDefaultTab
      }
    } catch (err) {
      console.error('加载用户设置失败:', err)
    }
  },

  getTabUrl() {
    const tabMap = {
      'index': '/pages/index/index',
      'convertible': '/pages/convertible/index',
      'lof': '/pages/lof/index',
      'hkipo': '/pages/hkipo/index'
    }
    return tabMap[this.globalData.defaultTab] || tabMap['index']
  },

  setTheme(theme) {
    try {
      this.globalData.theme = theme
      wx.setStorageSync('appTheme', theme)
      // 更新 TabBar 主题
      this.updateTabBarStyle(theme)
      return true
    } catch (err) {
      console.error('保存主题失败:', err)
      return false
    }
  },

  updateTabBarStyle(theme) {
    const isDark = theme === 'dark'
    const style = {
      color: isDark ? '#8B949E' : '#818B98',
      selectedColor: isDark ? '#E6EDF3' : '#1F2328',
      backgroundColor: isDark ? '#161B22' : '#FFFFFF',
      borderStyle: isDark ? 'white' : 'black'
    }
    try {
      wx.setTabBarStyle(style)
    } catch (err) {
      console.error('设置TabBar样式失败:', err)
    }
  },

  getTheme() {
    return this.globalData.theme
  },

  setDefaultTab(tab) {
    try {
      this.globalData.defaultTab = tab
      wx.setStorageSync('defaultTab', tab)
      return true
    } catch (err) {
      console.error('保存默认菜单失败:', err)
      return false
    }
  },

  getDefaultTab() {
    return this.globalData.defaultTab
  }
})