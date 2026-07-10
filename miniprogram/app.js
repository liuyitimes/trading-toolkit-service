const config = require('./config')

App({
  globalData: {
    cloudRunUrl: '',
    cloudEnv: '',
    currentEnv: '',
    isConfigured: false,
    theme: 'light',
    defaultTab: 'index',
    favoriteVersion: 0,
    ipoStatusVersion: 0
  },

  onLaunch() {
    // 初始化环境
    this.initEnv()
    this.initCloud()
    this.loadCloudRunUrl()
    this.loadUserSettings()
    this.updateTabBarStyle(this.globalData.theme)
    this.navigateToDefaultTab()
  },

  /**
   * 获取当前环境
   * autoSwitch: true 时根据小程序版本自动切换
   * autoSwitch: false 时使用 config.currentEnv
   */
  getEnv() {
    if (config.autoSwitch) {
      // 根据小程序版本自动切换
      // __wxConfig.envVersion: 'develop' | 'trial' | 'release'
      try {
        const envVersion = __wxConfig.envVersion
        if (envVersion === 'develop') {
          return 'development'
        }
        // trial（体验版）和 release（正式版）都用 production
        return 'production'
      } catch (e) {
        // 本地开发工具可能没有 __wxConfig，默认用 development
        console.warn('无法获取小程序版本，使用 development 环境')
        return 'development'
      }
    }
    // 手动指定环境
    return config.currentEnv || 'development'
  },

  /**
   * 初始化环境配置
   */
  initEnv() {
    const env = this.getEnv()
    this.globalData.currentEnv = env
    this.globalData.cloudEnv = config.cloudEnv[env] || 'prod-1g3p1'
    console.log(`[Env] 当前环境: ${env}, 云环境: ${this.globalData.cloudEnv}`)
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
        env: this.globalData.cloudEnv,
        traceUser: true
      })
      this.globalData.isConfigured = true
      console.log('云开发初始化成功, 环境:', this.globalData.cloudEnv)
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
        // 根据当前环境选择对应的 baseUrl
        const envConfig = config[this.globalData.currentEnv] || config.development
        this.globalData.cloudRunUrl = envConfig.baseUrl
      }
    } catch (err) {
      console.error('加载云托管地址失败:', err)
      const envConfig = config[this.globalData.currentEnv] || config.development
      this.globalData.cloudRunUrl = envConfig.baseUrl
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
    if (this.globalData.cloudRunUrl) {
      return this.globalData.cloudRunUrl
    }
    const envConfig = config[this.globalData.currentEnv] || config.development
    return envConfig.baseUrl
  },

  /**
   * 获取当前环境信息（调试用）
   */
  getEnvInfo() {
    return {
      env: this.globalData.currentEnv,
      cloudEnv: this.globalData.cloudEnv,
      cloudRunUrl: this.globalData.cloudRunUrl,
      autoSwitch: config.autoSwitch
    }
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