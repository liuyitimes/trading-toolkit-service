const themeConfig = require('../utils/theme')

module.exports = Behavior({
  data: {
    isDarkMode: false,
    themeColors: {}
  },

  attached() {
    this.initTheme()
  },

  methods: {
    initTheme() {
      const app = getApp()
      const theme = app.getTheme() || 'light'
      const isDark = theme === 'dark'
      const colors = themeConfig.getThemeColors(theme)

      this.setData({
        isDarkMode: isDark,
        themeColors: colors
      })
    },

    setDarkMode(isDark) {
      const theme = isDark ? 'dark' : 'light'
      const colors = themeConfig.getThemeColors(theme)

      this.setData({
        isDarkMode: isDark,
        themeColors: colors
      })
    },

    getThemeColor(key) {
      const colors = this.data.themeColors
      return colors[key] || '#1F2328'
    },

    getThemeClass() {
      return this.data.isDarkMode ? 'dark-mode' : 'light-mode'
    }
  }
})
