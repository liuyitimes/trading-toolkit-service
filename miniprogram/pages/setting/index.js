const app = getApp()

Page({
  data: {
    cloudRunUrl: '',
    inputError: '',
    currentTheme: 'light',
    currentDefaultTab: 'index',
    currentDefaultTabName: '首页',
    tabOptions: [
      { id: 'index', name: '首页' },
      { id: 'convertible', name: '可转债' },
      { id: 'lof', name: 'LOF基金' },
      { id: 'hkipo', name: '港股打新' }
    ],
    isDarkMode: false,
    subscribeEnabled: true,
    subscribeDeadlineEnabled: true,
    reminderOptions: [
      { id: 1, name: 'T-1日 18:00' },
      { id: 2, name: 'T-1日 12:00' },
      { id: 3, name: 'T-1日 09:00' },
      { id: 0, name: 'T日 09:00' }
    ],
    currentReminderTime: 1,
    currentReminderTimeName: 'T-1日 18:00'
  },

  onLoad() {
    this.loadConfig()
    this.loadUserSettings()
    this.loadReminderSettings()
  },

  onShow() {
    this.loadUserSettings()
    this.updateDarkMode()
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().checkDarkMode()
      this.getTabBar().setData({ selected: 4 })
    }
  },

  updateDarkMode() {
    const theme = app.getTheme()
    const isDark = theme === 'dark'
    this.setData({ isDarkMode: isDark })
  },

  loadConfig() {
    try {
      const cloudRunUrl = wx.getStorageSync('cloudRunUrl') || ''
      this.setData({ cloudRunUrl })
    } catch (err) {
      console.error('Failed to load config:', err)
    }
  },

  loadUserSettings() {
    const theme = app.getTheme()
    const defaultTab = app.getDefaultTab()
    const tabOptions = this.data.tabOptions
    const tabName = tabOptions.find(t => t.id === defaultTab)?.name || '首页'
    this.setData({
      currentTheme: theme,
      currentDefaultTab: defaultTab,
      currentDefaultTabName: tabName
    })
  },

  loadReminderSettings() {
    try {
      const subscribeEnabled = wx.getStorageSync('subscribeEnabled')
      const subscribeDeadlineEnabled = wx.getStorageSync('subscribeDeadlineEnabled')
      const reminderTime = wx.getStorageSync('reminderTime') || 1

      const reminderOptions = this.data.reminderOptions
      const reminderName = reminderOptions.find(r => r.id === reminderTime)?.name || 'T-1日 18:00'

      this.setData({
        subscribeEnabled: subscribeEnabled !== false,
        subscribeDeadlineEnabled: subscribeDeadlineEnabled !== false,
        currentReminderTime: reminderTime,
        currentReminderTimeName: reminderName
      })
    } catch (err) {
      console.error('Failed to load reminder settings:', err)
    }
  },

  onUrlInput(e) {
    const value = e.detail.value
    this.setData({
      cloudRunUrl: value,
      inputError: ''
    })
  },

  validateUrl(url) {
    if (!url || url.trim() === '') {
      return '请输入云托管地址'
    }

    try {
      const urlObj = new URL(url)
      if (!['http:', 'https:'].includes(urlObj.protocol)) {
        return '请输入有效的 HTTP/HTTPS 地址'
      }
      if (!urlObj.hostname) {
        return '请输入有效的域名'
      }
    } catch {
      return '请输入有效的 URL 格式'
    }

    return ''
  },

  goToTest() {
    wx.navigateTo({ url: '/pages/test/index' })
  },

  goToQuoteManage() {
    wx.navigateTo({ url: '/pages/quoteManage/index' })
  },

  goToApiLog() {
    wx.navigateTo({ url: '/pages/apiLog/index' })
  },

  setTheme(e) {
    const theme = e.currentTarget.dataset.theme
    if (!theme) return

    app.setTheme(theme)
    this.setData({
      currentTheme: theme,
      isDarkMode: theme === 'dark'
    })

    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().checkDarkMode()
    }

    wx.showToast({
      title: '主题已切换',
      icon: 'success',
      duration: 1500
    })
  },

  onDefaultTabChange(e) {
    const index = e.detail.value
    const tab = this.data.tabOptions[index]
    if (!tab) return

    app.setDefaultTab(tab.id)
    this.setData({
      currentDefaultTab: tab.id,
      currentDefaultTabName: tab.name
    })

    wx.showToast({
      title: '已设置默认页',
      icon: 'success',
      duration: 1500
    })
  },

  onSubscribeEnabledChange(e) {
    const enabled = e.detail.value
    this.setData({ subscribeEnabled: enabled })
    try {
      wx.setStorageSync('subscribeEnabled', enabled)
      wx.showToast({
        title: enabled ? '提醒已开启' : '提醒已关闭',
        icon: 'success',
        duration: 1500
      })
    } catch (err) {
      console.error('Failed to save subscribe setting:', err)
    }
  },

  onSubscribeDeadlineChange(e) {
    const enabled = e.detail.value
    this.setData({ subscribeDeadlineEnabled: enabled })
    try {
      wx.setStorageSync('subscribeDeadlineEnabled', enabled)
      wx.showToast({
        title: enabled ? '截止提醒已开启' : '截止提醒已关闭',
        icon: 'success',
        duration: 1500
      })
    } catch (err) {
      console.error('Failed to save deadline setting:', err)
    }
  },

  onReminderTimeChange(e) {
    const index = e.detail.value
    const option = this.data.reminderOptions[index]
    if (!option) return

    this.setData({
      currentReminderTime: option.id,
      currentReminderTimeName: option.name
    })
    try {
      wx.setStorageSync('reminderTime', option.id)
      wx.showToast({
        title: '提醒时间已设置',
        icon: 'success',
        duration: 1500
      })
    } catch (err) {
      console.error('Failed to save reminder time:', err)
    }
  },

  saveConfig() {
    const { cloudRunUrl } = this.data

    const error = this.validateUrl(cloudRunUrl)
    if (error) {
      this.setData({ inputError: error })
      return
    }

    try {
      app.setCloudRunUrl(cloudRunUrl)

      wx.showToast({
        title: '配置已保存',
        icon: 'success',
        duration: 2000
      })
    } catch (err) {
      console.error('Failed to save config:', err)
      wx.showToast({
        title: '保存失败',
        icon: 'none'
      })
    }
  },

  clearConfig() {
    wx.showModal({
      title: '确认清除',
      content: '确定要清除云托管地址配置吗？',
      success: (res) => {
        if (res.confirm) {
          try {
            wx.removeStorageSync('cloudRunUrl')
            app.setCloudRunUrl('')
            this.setData({ cloudRunUrl: '', inputError: '' })

            wx.showToast({
              title: '已清除',
              icon: 'success'
            })
          } catch (err) {
            console.error('Failed to clear config:', err)
            wx.showToast({
              title: '清除失败',
              icon: 'none'
            })
          }
        }
      }
    })
  }
})
