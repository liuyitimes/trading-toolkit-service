module.exports = {
  themes: {
    light: {
      name: '白色主题',
      colors: {
        primary: '#0969DA',
        background: '#F6F8FA',
        cardBackground: '#FFFFFF',
        textPrimary: '#1F2328',
        textSecondary: '#656D76',
        textTertiary: '#818B98',
        border: '#D0D7DE',
        borderLight: '#EAEef2',
        danger: '#CF222E',
        success: '#1A7F37',
        warning: '#9A6700',
        info: '#0969DA',
        highlight: '#0969DA',
        tagGreen: '#DAFBE1',
        tagGreenBorder: '#4AC26B',
        tagRed: '#FFEBE9',
        tagRedBorder: '#FFCECB',
        tabBarBg: '#FFFFFF',
        tabBarColor: '#6B7280',
        tabBarSelected: '#1E3A5F',
        navBarBg: '#1E3A5F'
      }
    },
    dark: {
      name: '暗夜主题',
      colors: {
        primary: '#58A6FF',
        background: '#0D1117',
        cardBackground: '#161B22',
        textPrimary: '#E6EDF3',
        textSecondary: '#8B949E',
        textTertiary: '#6E7681',
        border: '#30363D',
        borderLight: '#21262D',
        danger: '#F85149',
        success: '#3FB950',
        warning: '#D29922',
        info: '#58A6FF',
        highlight: '#58A6FF',
        tagGreen: '#1A4D2E',
        tagGreenBorder: '#238636',
        tagRed: '#4D1F1F',
        tagRedBorder: '#DA3633',
        tabBarBg: '#161B22',
        tabBarColor: '#8B949E',
        tabBarSelected: '#58A6FF',
        navBarBg: '#0D1117'
      }
    }
  },

  getThemeColors(theme) {
    return this.themes[theme]?.colors || this.themes.light.colors
  }
}
